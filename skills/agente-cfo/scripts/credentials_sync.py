#!/usr/bin/env python3
"""
credentials_sync.py — Daemon que materializa credenciais de integrações
na VPS a partir do painel web.

Sprint 26 — Zero SSH: toda integração configurada no painel.

Loop a cada CREDENTIALS_SYNC_INTERVAL_MIN (default: 3 min):
  1. GET ${PANEL_BASE_URL}/integration-credentials-vps-list
     (X-Panel-Token + X-Hooks-Token)
  2. Resposta: [{ skill_name, credentials: {KEY: val, ...}, active }]
  3. Materializa ~/.openclaw/secrets/<skill>.env com chmod 600
  4. Se houve mudança real (hash diferente), sinaliza daemons relevantes

Skills com OAuth gerenciado pelo painel (push-tokens):
  bling, contaazul, mercado-livre, nuvemshop
  → estas são IGNORADAS (já têm fluxo próprio)

Logs: ~/.agente-cfo/logs/credentials-sync.log
Env:  PANEL_BASE_URL, PANEL_TOKEN, HOOKS_TOKEN, CREDENTIALS_SYNC_INTERVAL_MIN
"""
import hashlib
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
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "credentials-sync.log"
SECRETS_DIR = Path.home() / ".openclaw" / "secrets"
STATE_FILE = Path.home() / ".agente-cfo" / "state" / "credentials_sync.json"

INTERVAL_MINUTES = int(os.environ.get("CREDENTIALS_SYNC_INTERVAL_MIN", "3"))
INTERVAL_SECONDS = INTERVAL_MINUTES * 60

# Skills gerenciadas por OAuth flow (push-tokens edge functions) → ignorar
OAUTH_MANAGED_SKILLS = {"bling", "contaazul", "mercado-livre", "nuvemshop"}

# Daemons que recarregam quando as credenciais mudam
DAEMONS_TO_RELOAD = ["cfo-proactive", "cfo-automation-engine"]


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


# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"hashes": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ── Edge function ─────────────────────────────────────────────────────────────

def fetch_credentials() -> list[dict]:
    """
    GET /integration-credentials-vps-list
    Returns: [{ skill_name, credentials: {KEY: val}, active }]
    """
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
            log(f"[fetch] {len(items)} skill(s) recebida(s) do painel")
            return items
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"[fetch] HTTP {e.code}: {body}")
        return []
    except Exception as e:
        log(f"[fetch] Erro: {e}")
        return []


# ── Secrets file ──────────────────────────────────────────────────────────────

def render_env_file(credentials: dict) -> str:
    """Converte dict de credenciais para formato KEY=VALUE (env file)."""
    lines = []
    for key, val in sorted(credentials.items()):
        # Escapa aspas simples e aspas duplas no valor
        safe_val = str(val).replace("'", "'\\''")
        lines.append(f"{key}={safe_val}")
    return "\n".join(lines) + "\n"


def file_hash(content: str) -> str:
    """SHA-256 do conteúdo (pra detectar mudanças sem logar as chaves)."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def materialize_secrets(skill_name: str, credentials: dict) -> bool:
    """
    Escreve ~/.openclaw/secrets/<skill>.env com as credenciais.
    Retorna True se o arquivo mudou (novo ou conteúdo diferente).
    """
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    target = SECRETS_DIR / f"{skill_name}.env"
    content = render_env_file(credentials)
    new_hash = file_hash(content)

    # Verifica se mudou
    old_hash = None
    if target.exists():
        try:
            old_hash = file_hash(target.read_text())
        except Exception:
            pass

    if old_hash == new_hash:
        return False  # sem mudança

    # Escreve atomicamente
    tmp = target.with_suffix(".env.tmp")
    tmp.write_text(content)
    tmp.chmod(0o600)
    tmp.replace(target)
    target.chmod(0o600)

    action = "atualizado" if old_hash else "criado"
    log(f"[secrets] {skill_name}.env {action} (hash={new_hash})")
    return True


# ── Daemon reload ─────────────────────────────────────────────────────────────

def reload_daemons() -> None:
    """Reinicia daemons que carregam credenciais, pra aplicar novas secrets."""
    for daemon in DAEMONS_TO_RELOAD:
        try:
            result = subprocess.run(
                ["systemctl", "restart", daemon],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                log(f"[reload] {daemon} reiniciado")
            else:
                log(f"[reload] {daemon} restart retornou {result.returncode}: {result.stderr[:80]}")
        except FileNotFoundError:
            log(f"[reload] systemctl não disponível — {daemon} não reiniciado")
        except Exception as e:
            log(f"[reload] Erro ao reiniciar {daemon}: {e}")


# ── Main sync ─────────────────────────────────────────────────────────────────

def sync() -> None:
    """Executa um ciclo de sync de credenciais."""
    items = fetch_credentials()
    if not items:
        # Edge function pode não existir ainda (antes do deploy do frontend)
        return

    changed_skills: list[str] = []

    for item in items:
        skill_name = item.get("skill_name", "")
        credentials = item.get("credentials", {})
        active = item.get("active", True)

        if not skill_name:
            continue

        # Ignora skills com OAuth flow próprio
        if skill_name in OAUTH_MANAGED_SKILLS:
            continue

        if not active:
            log(f"[sync] {skill_name}: inativo — mantendo arquivo existente (sem delete)")
            continue

        if not isinstance(credentials, dict) or not credentials:
            log(f"[sync] {skill_name}: credenciais vazias — pulando")
            continue

        changed = materialize_secrets(skill_name, credentials)
        if changed:
            changed_skills.append(skill_name)

    if changed_skills:
        log(f"[sync] {len(changed_skills)} skill(s) atualizada(s): {', '.join(changed_skills)}")
        reload_daemons()
    else:
        log("[sync] Nenhuma credencial mudou")


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()

    missing = [k for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN") if not os.environ.get(k)]
    if missing:
        log(f"[startup] ERRO: variáveis obrigatórias ausentes: {', '.join(missing)}")
        log("[startup] Configure em ~/.agente-cfo/.env e reinicie.")
        sys.exit(1)

    log("credentials_sync.py started (Sprint 26 — Zero SSH)")
    log(f"Intervalo de sync: {INTERVAL_MINUTES} minutos")
    log(f"Secrets dir: {SECRETS_DIR}")
    log(f"OAuth skills (ignoradas): {', '.join(sorted(OAUTH_MANAGED_SKILLS))}")

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
