#!/usr/bin/env python3
"""
supabase_sync.py — Daemon de sincronização de projetos Supabase.

Sprint 28 fix: usa mcp.servers.<name> via `openclaw config set` (caminho canônico).
NUNCA escreve openclaw.json diretamente — usa somente o CLI do OpenClaw.

Loop a cada SUPABASE_SYNC_INTERVAL_MIN (default: 5 min):
  1. GET /supabase-projects-vps-list (X-Panel-Token + X-Hooks-Token)
  2. Compara projetos ativos com o que está registrado em mcp.servers
  3. Registra novos (via mcp_manager.register_mcp)
  4. Remove os que foram desativados/removidos do painel
  5. Reinicia gateway somente se houve mudança real

Logs: ~/.agente-cfo/logs/supabase-sync.log
      ~/.agente-cfo/logs/mcp-sync.log (via mcp_manager)
Env:  PANEL_BASE_URL, PANEL_TOKEN, HOOKS_TOKEN, SUPABASE_SYNC_INTERVAL_MIN
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE = Path.home() / ".agente-cfo" / ".env"
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "supabase-sync.log"

INTERVAL_MINUTES = int(os.environ.get("SUPABASE_SYNC_INTERVAL_MIN", "5"))
INTERVAL_SECONDS = INTERVAL_MINUTES * 60

SUPABASE_KEY_PREFIX = "supabase_"

# Adiciona scripts/ de agente-cfo ao path pra importar mcp_manager
_lib_dir = str(Path(__file__).parent.parent.parent / "agente-cfo" / "scripts")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)

from mcp_manager import (  # type: ignore
    register_mcp,
    unregister_mcp,
    list_registered_mcps,
    restart_gateway_if_needed,
)


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
        for raw in f:
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                k, _, v = raw.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ── Fetch projetos ────────────────────────────────────────────────────────────

def fetch_projects() -> list:
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
            log(f"[fetch] {len(projects)} projeto(s) recebido(s)")
            return projects
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"[fetch] HTTP {e.code}: {body}")
        return []
    except Exception as e:
        log(f"[fetch] Erro: {e}")
        return []


# ── Sync ──────────────────────────────────────────────────────────────────────

def sync() -> None:
    from render_mcp_config import desired_mcp_map, project_mcp_name  # type: ignore

    projects = fetch_projects()
    desired = desired_mcp_map(projects)      # { "supabase_xxx": entry }

    # MCPs supabase já registrados no OpenClaw
    current_all = list_registered_mcps()
    current_supabase = {k for k in current_all if k.startswith(SUPABASE_KEY_PREFIX)}

    any_change = False

    # 1. Registra / atualiza novos
    for mcp_name, entry in desired.items():
        changed = register_mcp(
            name=mcp_name,
            command=entry["command"],
            args=entry.get("args", []),
            env=entry.get("env", {}),
            log_fn=log,
        )
        if changed:
            any_change = True

    # 2. Remove os que sumiram do painel (inativados ou deletados)
    to_remove = current_supabase - set(desired.keys())
    for mcp_name in to_remove:
        removed = unregister_mcp(mcp_name, log_fn=log)
        if removed:
            log(f"[sync] Removeu MCP '{mcp_name}' (projeto inativado/deletado)")
            any_change = True

    if not any_change:
        log("[sync] Nenhuma mudança nos MCP servers Supabase")

    restart_gateway_if_needed(any_change, log_fn=log)


# ── Main loop ─────────────────────────────────────────────────────────────────

# Adiciona scripts/ local ao path pra importar render_mcp_config
_local_dir = str(Path(__file__).parent)
if _local_dir not in sys.path:
    sys.path.insert(0, _local_dir)


def run_loop() -> None:
    load_env()

    missing = [k for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN") if not os.environ.get(k)]
    if missing:
        log(f"[startup] ERRO: {', '.join(missing)} não configurados")
        sys.exit(1)

    log("supabase_sync.py started (Sprint 28 — mcp.servers canônico)")
    log(f"Intervalo: {INTERVAL_MINUTES} min | Panel: {os.environ['PANEL_BASE_URL']}")

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
