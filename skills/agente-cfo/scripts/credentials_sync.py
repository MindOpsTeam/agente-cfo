#!/usr/bin/env python3
"""
credentials_sync.py — Daemon que materializa credenciais E registra MCP servers.

Sprint 28 — Zero SSH + Plug-and-play MCP:
  1. GET /integration-credentials-vps-list  → lista de skills com credenciais
  2. Materializa ~/.openclaw/secrets/<skill>.env  (já fazia)
  3. Registra MCP server em mcp.servers.<skill> via `openclaw config set` (novo)
  4. Pra skill desativada: mantém .env, REMOVE MCP
  5. Restart gateway somente se houve mudança real

Skills com OAuth gerenciado pelo painel (push-tokens) → ignoradas para .env:
  bling, contaazul, mercado-livre, nuvemshop
  (mas ainda gerencia o MCP delas se a skill existir)

MCP server path: ~/.openclaw/workspace/skills/<skill>/mcp_server.py
Secrets path:    ~/.openclaw/secrets/<skill>.env

Logs: ~/.agente-cfo/logs/credentials-sync.log
      ~/.agente-cfo/logs/mcp-sync.log (via mcp_manager)
Env:  PANEL_BASE_URL, PANEL_TOKEN, HOOKS_TOKEN, CREDENTIALS_SYNC_INTERVAL_MIN
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE    = Path.home() / ".agente-cfo" / ".env"
LOG_FILE    = Path.home() / ".agente-cfo" / "logs" / "credentials-sync.log"
SECRETS_DIR = Path.home() / ".openclaw" / "secrets"
WORKSPACE   = Path.home() / ".openclaw" / "workspace" / "skills"

INTERVAL_MINUTES = int(os.environ.get("CREDENTIALS_SYNC_INTERVAL_MIN", "3"))
INTERVAL_SECONDS = INTERVAL_MINUTES * 60

# Skills com OAuth gerenciado por push-tokens → não materializa .env (mas gerencia MCP)
OAUTH_MANAGED_SKILLS = {"bling", "contaazul", "mercado-livre", "nuvemshop"}

# Daemons que recarregam credenciais
DAEMONS_TO_RELOAD = ["cfo-proactive", "cfo-automation-engine"]

# Adiciona este diretório ao path pra importar mcp_manager
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

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


# ── Edge function ─────────────────────────────────────────────────────────────

def fetch_credentials() -> list:
    panel_base = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    hooks_token = os.environ.get("HOOKS_TOKEN", "")

    if not panel_base or not panel_token or not hooks_token:
        log("[fetch] ERRO: PANEL_BASE_URL, PANEL_TOKEN ou HOOKS_TOKEN não configurados")
        return []

    url = f"{panel_base}/integration-credentials-vps-list"
    headers = {
        "X-Panel-Token": panel_token,
        "X-Hooks-Token": hooks_token,
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            items = data if isinstance(data, list) else data.get("credentials", [])
            log(f"[fetch] {len(items)} skill(s) recebida(s)")
            return items
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"[fetch] HTTP {e.code}: {body}")
        return []
    except Exception as e:
        log(f"[fetch] Erro: {e}")
        return []


# ── Secrets file helpers ──────────────────────────────────────────────────────

def render_env_file(credentials: dict) -> str:
    lines = []
    for key, val in sorted(credentials.items()):
        safe_val = str(val).replace("'", "'\\''")
        lines.append(f"{key}={safe_val}")
    return "\n".join(lines) + "\n"


def file_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def materialize_secrets(skill_name: str, credentials: dict) -> bool:
    """Escreve ~/.openclaw/secrets/<skill>.env. Retorna True se mudou."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    target = SECRETS_DIR / f"{skill_name}.env"
    content = render_env_file(credentials)
    new_hash = file_hash(content)
    old_hash = None
    if target.exists():
        try:
            old_hash = file_hash(target.read_text())
        except Exception:
            pass
    if old_hash == new_hash:
        return False
    tmp = target.with_suffix(".env.tmp")
    tmp.write_text(content)
    tmp.chmod(0o600)
    tmp.replace(target)
    target.chmod(0o600)
    action = "atualizado" if old_hash else "criado"
    log(f"[secrets] {skill_name}.env {action}")
    return True


def load_env_file(skill_name: str) -> dict:
    """Lê ~/.openclaw/secrets/<skill>.env → dict de KEY:VALUE."""
    path = SECRETS_DIR / f"{skill_name}.env"
    env = {}
    if not path.exists():
        return env
    try:
        with open(path) as f:
            for raw in f:
                raw = raw.strip()
                if raw and not raw.startswith("#") and "=" in raw:
                    k, _, v = raw.partition("=")
                    env[k.strip()] = v.strip()
    except Exception:
        pass
    return env


# ── Daemon reload ─────────────────────────────────────────────────────────────

import subprocess

def reload_daemons() -> None:
    for daemon in DAEMONS_TO_RELOAD:
        try:
            result = subprocess.run(
                ["systemctl", "restart", daemon],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                log(f"[reload] {daemon} reiniciado")
            else:
                log(f"[reload] {daemon} retornou {result.returncode}: {result.stderr[:60]}")
        except FileNotFoundError:
            log(f"[reload] systemctl não disponível — {daemon} não reiniciado")
        except Exception as e:
            log(f"[reload] Erro ao reiniciar {daemon}: {e}")


# ── MCP server path ───────────────────────────────────────────────────────────

def mcp_server_path(skill_name: str) -> str:
    return str(WORKSPACE / skill_name / "mcp_server.py")


def mcp_server_exists(skill_name: str) -> bool:
    return Path(mcp_server_path(skill_name)).exists()


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync() -> None:
    items = fetch_credentials()
    if not items:
        return

    secrets_changed_skills: list = []
    mcp_gateway_changed = False

    # Conjunto de skills ativas neste ciclo (pra saber quais remover do MCP)
    active_skills: set = set()

    for item in items:
        skill_name = item.get("skill_name", "")
        credentials = item.get("credentials", {})
        active = item.get("active", True)

        if not skill_name:
            continue

        if not active:
            log(f"[sync] {skill_name}: inativo — mantendo .env, removendo MCP se existir")
            # Remove MCP da skill desativada
            if mcp_server_exists(skill_name):
                removed = unregister_mcp(skill_name, log_fn=log)
                if removed:
                    mcp_gateway_changed = True
            continue

        active_skills.add(skill_name)

        # ── 1. Materializa .env (exceto OAuth-managed) ─────────────────────
        if skill_name not in OAUTH_MANAGED_SKILLS:
            if isinstance(credentials, dict) and credentials:
                changed = materialize_secrets(skill_name, credentials)
                if changed:
                    secrets_changed_skills.append(skill_name)
            else:
                log(f"[sync] {skill_name}: credenciais vazias — .env não atualizado")

        # ── 2. Registra MCP server se existir mcp_server.py ───────────────
        if not mcp_server_exists(skill_name):
            log(f"[sync] {skill_name}: sem mcp_server.py em {mcp_server_path(skill_name)} — pulando MCP")
            continue

        # Env para o MCP = o que está no .env (já materializado ou existente de OAuth)
        mcp_env = load_env_file(skill_name)
        if not mcp_env and skill_name not in OAUTH_MANAGED_SKILLS:
            # Sem .env e sem OAuth → usa credenciais recebidas diretamente
            mcp_env = credentials if isinstance(credentials, dict) else {}

        changed = register_mcp(
            name=skill_name,
            command="python3",
            args=[mcp_server_path(skill_name)],
            env=mcp_env,
            log_fn=log,
        )
        if changed:
            mcp_gateway_changed = True

    # ── 3. Remove MCPs de skills que não vieram no payload (foram deletadas) ─
    # Mantém supabase_* (gerenciado pelo supabase_sync) e outros fora do nosso escopo
    current_mcps = list_registered_mcps()
    skills_from_credentials = {
        k for k in current_mcps
        if not k.startswith("supabase_")          # supabase_sync cuida desses
        and not k.startswith("evolution_")        # futuro
    }
    for mcp_name in skills_from_credentials:
        if mcp_name not in active_skills:
            # Skill sumiu da lista ativa → remove MCP
            removed = unregister_mcp(mcp_name, log_fn=log)
            if removed:
                log(f"[sync] MCP '{mcp_name}' removido (skill desativada/deletada)")
                mcp_gateway_changed = True

    # ── 4. Reload daemons se secrets mudaram ──────────────────────────────
    if secrets_changed_skills:
        log(f"[sync] {len(secrets_changed_skills)} .env(s) atualizado(s): {', '.join(secrets_changed_skills)}")
        reload_daemons()

    if not secrets_changed_skills and not mcp_gateway_changed:
        log("[sync] Nenhuma mudança")

    # ── 5. Restart gateway se MCP mudou ───────────────────────────────────
    restart_gateway_if_needed(mcp_gateway_changed, log_fn=log)


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()

    missing = [k for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN") if not os.environ.get(k)]
    if missing:
        log(f"[startup] ERRO: {', '.join(missing)} não configurados")
        sys.exit(1)

    log("credentials_sync.py started (Sprint 28 — MCP plug-and-play)")
    log(f"Intervalo: {INTERVAL_MINUTES} min | Workspace: {WORKSPACE}")
    log(f"OAuth-managed (sem .env): {', '.join(sorted(OAUTH_MANAGED_SKILLS))}")

    while True:
        log("--- Início do ciclo credentials-sync ---")
        try:
            sync()
        except Exception as e:
            log(f"[main] Erro no ciclo: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_loop()
