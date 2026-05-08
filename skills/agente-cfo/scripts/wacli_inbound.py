#!/usr/bin/env python3
"""
wacli_inbound.py — Daemon de inbound WhatsApp para o Agente CFO.

Faz polling de 'wacli messages list --json --after <cursor>' a cada 5s.
Detecta mensagens novas do dono (self-chat: from == JID pareado, para == JID pareado).
Dispara POST /hooks/agent para o OpenClaw processar.
Dedup por message.id via ~/.agente-cfo/state/wacli-cursor.json.
"""
import json
import os
import sys
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

ENV_FILE = Path.home() / ".agente-cfo" / ".env"
STATE_FILE = Path.home() / ".agente-cfo" / "state" / "wacli-cursor.json"
THREAD_DIR = Path.home() / ".agente-cfo" / "memory" / "threads"
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "wacli-inbound.log"
POLL_INTERVAL = 5  # seconds


def load_env():
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state() -> dict:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_ts": None, "seen_ids": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_own_jid() -> str | None:
    """Detecta o JID do numero pareado via wacli doctor --json ou contatos."""
    try:
        r = subprocess.run(
            ["wacli", "doctor", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            jid = d.get("jid") or d.get("data", {}).get("jid") or d.get("phone")
            if jid:
                return jid
    except Exception:
        pass
    # Fallback: ler CFO_WHATSAPP_TO do env e converter
    wa_to = os.environ.get("CFO_WHATSAPP_TO", "")
    if wa_to:
        digits = "".join(c for c in wa_to if c.isdigit())
        if digits:
            return f"{digits}@s.whatsapp.net"
    return None


def poll_messages(after_ts: str | None, own_jid: str) -> list[dict]:
    """
    Chama wacli messages list --json [--after TS] --chat <own_jid> --limit 50
    Retorna lista de mensagens novas.
    """
    cmd = ["wacli", "messages", "list", "--json", "--limit", "50", "--chat", own_jid]
    if after_ts:
        cmd += ["--after", after_ts]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return []
        data = json.loads(r.stdout)
        # wacli retorna {"success": true, "data": {"messages": [...]}}
        msgs = data.get("data", {}).get("messages") or []
        return msgs if isinstance(msgs, list) else []
    except Exception as e:
        log(f"poll_messages error: {e}")
        return []


def is_from_owner(msg: dict, own_jid: str) -> bool:
    """
    Mensagem valida = enviada PELO dono PRA ele mesmo (self-chat).
    wacli usa "from_me" ou "sender" == own_jid.
    Aceita tanto fromMe=true quanto sender == own_jid.
    """
    from_me = msg.get("fromMe") or msg.get("from_me") or False
    sender = msg.get("sender") or msg.get("from") or ""
    return bool(from_me) or (
        bool(sender) and bool(own_jid)
        and sender.split(":")[0] == own_jid.split(":")[0].split("@")[0]
    )


def extract_text(msg: dict) -> str | None:
    """Extrai texto de uma mensagem. Retorna None se nao for texto."""
    text = (
        msg.get("text")
        or msg.get("body")
        or msg.get("content")
        or (msg.get("message") or {}).get("conversation")
        or (msg.get("message") or {}).get("extendedTextMessage", {}).get("text")
        or ""
    )
    return text.strip() if text else None


def append_thread(jid: str, role: str, content: str):
    """Append a message to the thread memory file."""
    THREAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_jid = jid.replace("/", "_").replace(":", "_")
    thread_file = THREAD_DIR / f"{safe_jid}.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{role}] {content}\n"
    with open(thread_file, "a") as f:
        f.write(line)


def dispatch_to_agent(text: str, jid: str, msg_id: str):
    """
    POST /hooks/agent com o texto da mensagem.
    O agente OpenClaw processa usando prompts/conversa.md.
    Inclui o JID e msg_id no contexto para que o agente saiba pra onde responder.
    """
    hooks_token = os.environ.get("HOOKS_TOKEN", "")
    hooks_url = "http://127.0.0.1:18789/hooks/agent"

    full_message = (
        f"[WA_INBOUND] from_jid={jid} msg_id={msg_id}\n"
        f"Mensagem do dono: {text}\n\n"
        f"Instrucoes: Leia prompts/conversa.md e responda esta mensagem. "
        f"Depois de formular a resposta, envie via: "
        f"bash $SCRIPTS_DIR/_send_whatsapp.sh '{jid}' '<resposta>'"
    )

    payload = json.dumps({
        "message": full_message,
        "name": "wa_inbound",
        "wakeMode": "now",
        "deliver": False,
        "timeoutSeconds": 300,
    }).encode("utf-8")

    req = urllib.request.Request(
        hooks_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {hooks_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            log(f"dispatch OK: msg_id={msg_id} -> {resp.status} {body[:100]}")
    except urllib.error.HTTPError as e:
        log(f"dispatch HTTP error {e.code}: {e.read().decode()[:200]}")
    except Exception as e:
        log(f"dispatch error: {e}")


def run():
    load_env()
    log("wacli_inbound.py started")

    own_jid = get_own_jid()
    if not own_jid:
        log("ERROR: nao foi possivel detectar JID proprio. Defina CFO_WHATSAPP_TO no .env")
        sys.exit(1)
    log(f"Monitorando self-chat para JID: {own_jid}")

    state = load_state()
    seen_ids = set(state.get("seen_ids", []))
    last_ts = state.get("last_ts")

    while True:
        try:
            msgs = poll_messages(last_ts, own_jid)
            new_ts = last_ts
            for msg in msgs:
                msg_id = msg.get("id") or msg.get("ID") or msg.get("messageId")
                if not msg_id:
                    continue
                if msg_id in seen_ids:
                    continue

                if not is_from_owner(msg, own_jid):
                    seen_ids.add(msg_id)
                    continue

                text = extract_text(msg)
                if not text:
                    seen_ids.add(msg_id)
                    continue

                log(f"Nova mensagem do dono: {text[:80]}")

                append_thread(own_jid, "user", text)
                dispatch_to_agent(text, own_jid, msg_id)

                seen_ids.add(msg_id)

                msg_ts = msg.get("timestamp") or msg.get("ts") or msg.get("time")
                if msg_ts:
                    if isinstance(msg_ts, (int, float)):
                        msg_ts = datetime.fromtimestamp(msg_ts, tz=timezone.utc).isoformat()
                    new_ts = msg_ts

            # Guardar apenas ultimos 500 IDs
            if len(seen_ids) > 500:
                seen_ids = set(list(seen_ids)[-500:])

            save_state({"last_ts": new_ts, "seen_ids": list(seen_ids)})

        except Exception as e:
            log(f"poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
