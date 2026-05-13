#!/usr/bin/env python3
"""
supabase_sync.py — Daemon de sincronização de projetos Supabase.

Loop a cada SUPABASE_SYNC_INTERVAL_MIN (default: 5 min):
  1. Busca projetos ativos via edge function supabase-projects-vps-list
     (que descriptografa a service_role_key em runtime).
  2. Gera bloco mcpServers para cada projeto.
  3. Diff com o estado atual de ~/.openclaw/openclaw.json.
  4. Aplica mudanças via `openclaw config set/unset mcpServers.<slug>`.
  5. Se houve mudança, reinicia o openclaw-gateway.

Logs: ~/.agente-cfo/logs/supabase-sync.log
Env:  PANEL_BASE_URL, PANEL_TOKEN, HOOKS_TOKEN, SUPABASE_SYNC_INTERVAL_MIN
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE = Path.home() / ".agente-cfo" / ".env"
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "supabase-sync.log"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

INTERVAL_MINUTES = int(os.environ.get("SUPABASE_SYNC_INTERVAL_MIN", "5"))
INTERVAL_SECONDS = INTERVAL_MINUTES * 60

# Prefixo das chaves gerenciadas por este daemon (não apaga outras entradas)
SUPABASE_KEY_PREFIX = "supabase_"


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── Env loader ────────────────────────────────────────────────────────────────

def load_env() -> None:
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ── Edge function call ────────────────────────────────────────────────────────

def fetch_projects() -> list[dict]:
    """
    GET /supabase-projects-vps-list
    Auth: X-Panel-Token + X-Hooks-Token
    Returns: list of { id, name, slug?, project_url, service_role_key, active }
    """
    panel_base = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    hooks_token = os.environ.get("HOOKS_TOKEN", "")

    if not panel_base or not panel_token or not hooks_token:
        log("[fetch] ERRO: PANEL_BASE_URL, PANEL_TOKEN ou HOOKS_TOKEN não configurados")
        return []

    url = f"{panel_base}/supabase-projects-vps-list"
    headers = {
        "X-Panel-Token": panel_token,
        "X-Hooks-Token": hooks_token,
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            projects = data if isinstance(data, list) else data.get("projects", [])
            log(f"[fetch] {len(projects)} projeto(s) recebido(s) do painel")
            return projects
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"[fetch] HTTP {e.code}: {body}")
        return []
    except Exception as e:
        log(f"[fetch] Erro: {e}")
        return []


# ── openclaw.json manipulation ────────────────────────────────────────────────

def read_openclaw_config() -> dict:
    """Lê ~/.openclaw/openclaw.json. Retorna {} se não existir ou for inválido."""
    if not OPENCLAW_CONFIG.exists():
        return {}
    try:
        return json.loads(OPENCLAW_CONFIG.read_text())
    except Exception as e:
        log(f"[config] Erro ao ler openclaw.json: {e}")
        return {}


def write_openclaw_config(config: dict) -> None:
    """Escreve ~/.openclaw/openclaw.json atomicamente."""
    OPENCLAW_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    tmp = OPENCLAW_CONFIG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    tmp.replace(OPENCLAW_CONFIG)


def get_current_supabase_entries(config: dict) -> dict:
    """Extrai as entradas supabase_* do mcpServers."""
    mcp_servers = config.get("mcpServers", {})
    return {
        k: v
        for k, v in mcp_servers.items()
        if k.startswith(SUPABASE_KEY_PREFIX)
    }


# ── MCP config rendering ──────────────────────────────────────────────────────

# Importa render_mcp_block do módulo irmão
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from render_mcp_config import render_mcp_block  # type: ignore


# ── Gateway restart ───────────────────────────────────────────────────────────

def restart_gateway() -> None:
    """Reinicia o openclaw-gateway via systemctl (se disponível) ou openclaw CLI."""
    # Tenta systemctl primeiro (VPS Linux)
    try:
        result = subprocess.run(
            ["systemctl", "restart", "openclaw-gateway"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            log("[gateway] openclaw-gateway reiniciado via systemctl")
            return
        log(f"[gateway] systemctl restart saiu com {result.returncode}: {result.stderr[:100]}")
    except FileNotFoundError:
        pass  # Não tem systemctl (macOS dev)
    except Exception as e:
        log(f"[gateway] Erro systemctl: {e}")

    # Fallback: openclaw gateway restart
    try:
        result = subprocess.run(
            ["openclaw", "gateway", "restart"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            log("[gateway] openclaw-gateway reiniciado via CLI")
        else:
            log(f"[gateway] openclaw gateway restart falhou: {result.stderr[:100]}")
    except FileNotFoundError:
        log("[gateway] openclaw não encontrado no PATH — restart manual necessário")
    except Exception as e:
        log(f"[gateway] Erro CLI: {e}")


# ── Main sync logic ───────────────────────────────────────────────────────────

def sync() -> bool:
    """
    Executa um ciclo de sync.
    Returns: True se houve mudança e o gateway foi reiniciado.
    """
    # 1. Busca projetos
    projects = fetch_projects()

    # 2. Gera bloco desejado (só ativos)
    desired: dict = render_mcp_block(projects)

    # 3. Lê config atual
    config = read_openclaw_config()
    current_supabase = get_current_supabase_entries(config)

    # 4. Diff
    added = {k: v for k, v in desired.items() if k not in current_supabase or current_supabase[k] != v}
    removed = {k for k in current_supabase if k not in desired}

    if not added and not removed:
        log("[sync] Nenhuma mudança — mcpServers Supabase já atualizados")
        return False

    # 5. Aplica mudanças no config
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    for key, entry in added.items():
        config["mcpServers"][key] = entry
        log(f"[sync] + {key} ({entry['env']['SUPABASE_URL']})")

    for key in removed:
        del config["mcpServers"][key]
        log(f"[sync] - {key} (projeto removido/inativado)")

    write_openclaw_config(config)
    log(f"[sync] openclaw.json atualizado (+{len(added)} -{len(removed)} projetos Supabase)")

    # 6. Restart gateway
    restart_gateway()
    return True


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()

    # Valida envs obrigatórias
    missing = [k for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN") if not os.environ.get(k)]
    if missing:
        log(f"[startup] ERRO: variáveis obrigatórias não configuradas: {', '.join(missing)}")
        log("[startup] Configure em ~/.agente-cfo/.env e reinicie.")
        sys.exit(1)

    log("supabase_sync.py started (Sprint 25)")
    log(f"Intervalo de sync: {INTERVAL_MINUTES} minutos")
    log(f"Panel base URL: {os.environ['PANEL_BASE_URL']}")

    while True:
        log("--- Início do ciclo supabase-sync ---")
        try:
            sync()
        except Exception as e:
            log(f"[main] Erro no ciclo: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_loop()
