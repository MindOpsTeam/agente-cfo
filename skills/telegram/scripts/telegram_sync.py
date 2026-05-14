#!/usr/bin/env python3
"""
telegram_sync.py — Daemon de sincronização Telegram bots ↔ painel.

Sprint 34 — Telegram via painel (zero SSH).

Loop a cada TELEGRAM_SYNC_INTERVAL_S (default: 30s):
  1. GET /telegram-bots-vps-list  → lista de bots ativos com token descriptografado
  2. Pra cada bot:
     a. Verifica que o token funciona (getMe)
     b. Registra webhook: setWebhook → ${PANEL_BASE_URL}/telegram-incoming-webhook?secret=<webhook_secret>
     c. POST /telegram-bots-vps-update → { id, status, bot_username, last_test_at }
  3. Bots que sumiram do painel: deleteWebhook (graceful cleanup)

Edge functions consumidas (todas com X-Panel-Token + X-Hooks-Token):
  GET /telegram-bots-vps-list    → [{ id, bot_username, bot_token, webhook_secret, active }]
  POST /telegram-bots-vps-update → [{ id, status, last_test_at }]

Logs: ~/.agente-cfo/logs/telegram-sync.log
Env:  PANEL_BASE_URL, PANEL_TOKEN, HOOKS_TOKEN, TELEGRAM_SYNC_INTERVAL_S
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE = Path.home() / ".agente-cfo" / ".env"
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "telegram-sync.log"

INTERVAL_SECONDS = int(os.environ.get("TELEGRAM_SYNC_INTERVAL_S", "30"))

# Adiciona scripts/ ao path pra importar telegram_client
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


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


# ── Panel HTTP ────────────────────────────────────────────────────────────────

def _panel_headers() -> dict:
    return {
        "X-Panel-Token": os.environ["PANEL_TOKEN"],
        "X-Hooks-Token": os.environ["HOOKS_TOKEN"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _panel_base() -> str:
    return os.environ["PANEL_BASE_URL"].rstrip("/")


def _panel_get(path: str) -> Optional[Any]:
    url = f"{_panel_base()}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers=_panel_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        log(f"[panel_get] HTTP {e.code} {path}: {e.read().decode()[:100]}")
        return None
    except Exception as e:
        log(f"[panel_get] Erro {path}: {e}")
        return None


def _panel_post(path: str, body: Any) -> Optional[Any]:
    url = f"{_panel_base()}/{path.lstrip('/')}"
    data = json.dumps(body, default=str).encode()
    req = urllib.request.Request(url, data=data, headers=_panel_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        log(f"[panel_post] HTTP {e.code} {path}: {e.read().decode()[:100]}")
        return None
    except Exception as e:
        log(f"[panel_post] Erro {path}: {e}")
        return None


# ── Fetch bots ────────────────────────────────────────────────────────────────

def fetch_bots() -> list:
    """
    GET /telegram-bots-vps-list → lista de bots com token descriptografado.
    Retorna [{ id, bot_username, bot_token, webhook_secret, active, receives_marcos_chat }]
    """
    data = _panel_get("telegram-bots-vps-list")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("bots", [])


# ── Webhook URL ────────────────────────────────────────────────────────────────

def bot_webhook_url(panel_base: str, webhook_secret: str) -> str:
    """
    URL que o Telegram chama ao receber atualizações.
    secret é passado como query param para validação no webhook handler.
    """
    import urllib.parse
    secret_encoded = urllib.parse.quote(webhook_secret, safe="")
    return f"{panel_base}/telegram-incoming-webhook?secret={secret_encoded}"


# ── Sync de um bot ─────────────────────────────────────────────────────────────

def sync_bot(bot: dict) -> dict:
    """
    Verifica e registra webhook para um bot.
    Retorna { id, status, last_test_at, bot_username }.
    """
    from telegram_client import TelegramClient

    bot_id = bot.get("id", "")
    bot_username = bot.get("bot_username", "")
    bot_token = bot.get("bot_token", "")
    webhook_secret = bot.get("webhook_secret", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    if not bot_token:
        log(f"[sync_bot] {bot_username}: token vazio — pulando")
        return {"id": bot_id, "status": "error", "last_test_at": now_iso, "bot_username": bot_username}

    client = TelegramClient(token=bot_token)

    # 1. Verifica que o token funciona
    try:
        me = client.get_me()
        actual_username = me.get("username", "?")
        log(f"[sync_bot] {bot_username}: getMe OK (@{actual_username})")
    except Exception as e:
        log(f"[sync_bot] {bot_username}: getMe FALHOU — {e}")
        return {"id": bot_id, "status": "error", "last_test_at": now_iso, "bot_username": bot_username}

    # 2. Registra/atualiza webhook
    panel_base = _panel_base()
    webhook_url = bot_webhook_url(panel_base, webhook_secret)

    try:
        client.set_webhook(
            url=webhook_url,
            secret_token=webhook_secret,
            allowed_updates=["message", "edited_message", "callback_query"],
            drop_pending_updates=False,
        )
        log(f"[sync_bot] {bot_username}: webhook registrado → {webhook_url[:80]}...")
        status = "active"
    except Exception as e:
        log(f"[sync_bot] {bot_username}: setWebhook FALHOU — {e}")
        status = "webhook_error"

    return {
        "id": bot_id,
        "status": status,
        "last_test_at": now_iso,
        "bot_username": bot_username,
    }


def delete_bot_webhook(bot_token: str, bot_username: str) -> None:
    """Remove webhook de bot que foi desativado/removido do painel."""
    from telegram_client import TelegramClient
    try:
        TelegramClient(token=bot_token).delete_webhook()
        log(f"[cleanup] {bot_username}: webhook removido")
    except Exception as e:
        log(f"[cleanup] {bot_username}: deleteWebhook falhou — {e}")


# ── Main sync cycle ────────────────────────────────────────────────────────────

def sync() -> None:
    """Executa um ciclo completo de sincronização."""
    bots = fetch_bots()

    if not bots:
        log("[sync] Nenhum bot configurado no painel")
        return

    active_usernames = {b.get("bot_username", "") for b in bots if b.get("active")}
    updates = []

    for bot in bots:
        if not bot.get("active"):
            # Bot inativado: remove webhook gracefully
            if bot.get("bot_token") and bot.get("bot_username"):
                delete_bot_webhook(bot["bot_token"], bot["bot_username"])
            continue

        result = sync_bot(bot)
        updates.append(result)

    # Envia atualizações pro painel
    if updates:
        resp = _panel_post("telegram-bots-vps-update", updates)
        if resp is not None:
            log(f"[sync] Painel atualizado: {len(updates)} bot(s)")
        else:
            log("[sync] Falha ao atualizar painel (edge fn não deployada ainda?)")


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()

    missing = [k for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN") if not os.environ.get(k)]
    if missing:
        log(f"[startup] ERRO: variáveis obrigatórias ausentes: {', '.join(missing)}")
        sys.exit(1)

    log("telegram_sync.py started (Sprint 34 — Telegram via painel)")
    log(f"Intervalo: {INTERVAL_SECONDS}s | Panel: {os.environ['PANEL_BASE_URL']}")

    while True:
        log("--- Início do ciclo telegram-sync ---")
        try:
            sync()
        except Exception as e:
            log(f"[main] Erro no ciclo: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_loop()
