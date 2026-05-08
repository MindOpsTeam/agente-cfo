#!/usr/bin/env python3
"""
wacli_inbound.py — Daemon de inbound WhatsApp para o Agente CFO.

Faz polling de 'wacli messages list --json --after <cursor>' a cada 5s.
Detecta mensagens novas do dono (self-chat: from == JID pareado, para == JID pareado).
Dispara POST /hooks/agent para o OpenClaw processar.
Dedup por message.id via ~/.agente-cfo/state/wacli-cursor.json.

NOTA: Na primeira execução o cursor é inicializado com datetime.now(), portanto
mensagens anteriores ao primeiro start são ignoradas por design (bug 5 fix).

Compatibilidade de campos: suporta PascalCase (wacli ≥0.7.0) com fallback
para camelCase/snake_case (versões anteriores) — bug 4 fix.
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
    """Carrega estado do cursor. Na primeira execução (ou last_ts nulo) seta
    last_ts=now para ignorar histórico anterior ao primeiro start (bug 5).
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            if not state.get("last_ts"):
                state["last_ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                save_state(state)
                log(f"Cursor inicializado para agora: {state['last_ts']} (histórico ignorado)")
            return state
        except Exception:
            pass
    # Primeira execução: cursor = agora
    state = {
        "last_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seen_ids": [],
    }
    save_state(state)
    log(f"Estado criado. Cursor inicial: {state['last_ts']} (histórico ignorado por design)")
    return state


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_own_jid() -> str | None:
    """Detecta o JID do número pareado.

    Ordem de preferência (bug 6):
    1. wacli doctor (texto simples) → linha 'LINKED_JID  <jid>'
    2. wacli doctor --json → campos jid/phone (versões antigas)
    3. CFO_WHATSAPP_TO se já vier em formato JID (contém '@')
    4. Último recurso: converter número BR removendo o 9 móvel extra
       (formato E.164 com 13 dígitos: 55 + DDD + 9 + número).
    """
    # 1. wacli doctor texto simples — formato atual wacli 0.7.x
    try:
        r = subprocess.run(
            ["wacli", "doctor"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("LINKED_JID"):
                parts = line.split()
                if len(parts) >= 2 and "@" in parts[-1]:
                    return parts[-1]
    except Exception:
        pass

    # 2. wacli doctor --json (compatibilidade versões antigas)
    try:
        r = subprocess.run(
            ["wacli", "doctor", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            jid = d.get("jid") or d.get("data", {}).get("jid") or d.get("phone")
            if jid and "@" in str(jid):
                return jid
    except Exception:
        pass

    # 3. CFO_WHATSAPP_TO como JID direto (já contém '@')
    wa_to = os.environ.get("CFO_WHATSAPP_TO", "")
    if "@" in wa_to:
        return wa_to

    # 4. Converter número E.164 BR → JID, removendo o 9 móvel se necessário
    if wa_to:
        digits = "".join(c for c in wa_to if c.isdigit())
        if len(digits) == 13 and digits.startswith("55"):
            # 55 + DDD (2 dígitos) + 9 + 8 dígitos → remove o 9 da posição 4
            digits = digits[:4] + digits[5:]
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
    Mensagem válida = enviada PELO dono PRA ele mesmo (self-chat).
    Suporta PascalCase (wacli ≥0.7.0) com fallback camelCase/snake_case (bug 4).
    """
    from_me = msg.get("FromMe") or msg.get("fromMe") or msg.get("from_me") or False
    sender = msg.get("SenderJID") or msg.get("sender") or msg.get("from") or ""
    return bool(from_me) or (
        bool(sender) and bool(own_jid)
        and sender.split(":")[0] == own_jid.split(":")[0].split("@")[0]
    )


def extract_text(msg: dict) -> str | None:
    """Extrai texto de uma mensagem. Retorna None se não for texto.
    Suporta PascalCase (wacli ≥0.7.0) com fallback para camelCase (bug 4).
    """
    text = (
        msg.get("Text") or msg.get("text")
        or msg.get("DisplayText")
        or msg.get("body") or msg.get("content")
        or (msg.get("message") or {}).get("conversation")
        or (msg.get("message") or {}).get("extendedTextMessage", {}).get("text")
        or ""
    )
    return text.strip() if text else None


def msg_id(msg: dict) -> str | None:
    """Extrai ID da mensagem — PascalCase (wacli ≥0.7.0) com fallback (bug 4)."""
    return msg.get("MsgID") or msg.get("id") or msg.get("msgId") or msg.get("messageId")


def msg_timestamp(msg: dict):
    """Extrai timestamp da mensagem — PascalCase com fallback (bug 4)."""
    return msg.get("Timestamp") or msg.get("timestamp") or msg.get("ts") or msg.get("time")


def append_thread(jid: str, role: str, content: str):
    """Append a message to the thread memory file."""
    THREAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_jid = jid.replace("/", "_").replace(":", "_")
    thread_file = THREAD_DIR / f"{safe_jid}.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{role}] {content}\n"
    with open(thread_file, "a") as f:
        f.write(line)


def dispatch_to_agent(text: str, jid: str, mid: str):
    """
    POST /hooks/agent com o texto da mensagem.
    O agente OpenClaw processa usando prompts/conversa.md.
    Inclui o JID e msg_id no contexto para que o agente saiba pra onde responder.
    """
    hooks_token = os.environ.get("HOOKS_TOKEN", "")
    hooks_url = "http://127.0.0.1:18789/hooks/agent"

    full_message = (
        f"[WA_INBOUND] from_jid={jid} msg_id={mid}\n"
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
            log(f"dispatch OK: msg_id={mid} -> {resp.status} {body[:100]}")
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
                mid = msg_id(msg)  # PascalCase-aware (bug 4)
                if not mid:
                    continue
                if mid in seen_ids:
                    continue

                if not is_from_owner(msg, own_jid):
                    seen_ids.add(mid)
                    continue

                text = extract_text(msg)
                if not text:
                    seen_ids.add(mid)
                    continue

                log(f"Nova mensagem do dono: {text[:80]}")

                append_thread(own_jid, "user", text)
                dispatch_to_agent(text, own_jid, mid)

                seen_ids.add(mid)

                msg_ts = msg_timestamp(msg)  # PascalCase-aware (bug 4)
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
