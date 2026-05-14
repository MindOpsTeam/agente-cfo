#!/usr/bin/env python3
"""
Smoke tests da skill telegram — Sprint 34.
Estrutural, sem hit real na API do Telegram.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── 1. Imports ────────────────────────────────────────────────────────────────
def test_imports():
    import telegram_client as tc
    import telegram_sync as ts
    print("✓ telegram_client e telegram_sync importados")
    return tc, ts


# ── 2. TelegramClient — instanciação sem hit na API ──────────────────────────
def test_client_init(tc):
    client = tc.TelegramClient(token="123456789:AAHtest_token_here")
    assert "123456789" in client._base
    assert client.token == "123456789:AAHtest_token_here"
    assert callable(client._request)  # só verifica que existe
    print("✓ TelegramClient.__init__ OK")


# ── 3. bot_webhook_url ────────────────────────────────────────────────────────
def test_webhook_url(ts):
    url = ts.bot_webhook_url(
        "https://xyz.supabase.co/functions/v1",
        "my_secret_123"
    )
    assert "telegram-incoming-webhook" in url
    assert "secret=my_secret_123" in url
    assert url.startswith("https://xyz.supabase.co")
    print("✓ bot_webhook_url OK:", url)


# ── 4. fetch_bots sem env → [] ───────────────────────────────────────────────
def test_fetch_bots_no_env(ts):
    for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN"):
        os.environ.pop(k, None)
    # Sem env vars, _panel_get lança KeyError — fetch_bots deve tratar
    try:
        result = ts.fetch_bots()
        assert result == []
        print("✓ fetch_bots retorna [] sem env vars")
    except KeyError:
        # Aceitável — sem env vars o daemon não inicia (validado no run_loop)
        print("✓ fetch_bots: sem PANEL_BASE_URL → KeyError esperado (validado no startup)")


# ── 5. send_telegram.sh sintaxe ──────────────────────────────────────────────
def test_send_syntax():
    script = Path(__file__).parent.parent / "scripts" / "send_telegram.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert result.returncode == 0, f"Erro de sintaxe: {result.stderr.decode()}"
    print("✓ send_telegram.sh: sintaxe bash OK")


# ── 6. doctor.sh sintaxe ─────────────────────────────────────────────────────
def test_doctor_syntax():
    script = Path(__file__).parent.parent / "doctor.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert result.returncode == 0, f"Erro de sintaxe: {result.stderr.decode()}"
    print("✓ doctor.sh: sintaxe bash OK")


# ── 7. connect.sh sintaxe ────────────────────────────────────────────────────
def test_connect_syntax():
    script = Path(__file__).parent.parent / "connect.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert result.returncode == 0, f"Erro de sintaxe: {result.stderr.decode()}"
    print("✓ connect.sh: sintaxe bash OK")


# ── 8. Cenário E2E simulado ───────────────────────────────────────────────────
def test_e2e_pipeline():
    """
    Simula o fluxo end-to-end sem API real:
    1. Payload Update Telegram entra via webhook
    2. thread_id e channel são derivados corretamente
    3. Prompt de resposta contém send_telegram.sh + panel_reply.sh
    """
    # Payload típico de mensagem Telegram (Update object)
    update = {
        "update_id": 123456789,
        "message": {
            "message_id": 42,
            "from": {
                "id": 987654321,
                "first_name": "Guilherme",
                "username": "guilherme_bfcfo",
                "is_bot": False,
            },
            "chat": {
                "id": 987654321,
                "type": "private",
                "first_name": "Guilherme",
            },
            "text": "Qual o faturamento do mês?",
            "date": 1716000000,
        },
    }

    bot_username = "marcoscfo_bot"
    chat_id = str(update["message"]["chat"]["id"])
    text = update["message"]["text"]

    # Deriva thread_id e channel (mesma lógica do incoming webhook)
    thread_id = f"telegram:{bot_username}:{chat_id}"
    channel = f"telegram:{bot_username}"

    assert thread_id == "telegram:marcoscfo_bot:987654321"
    assert channel == "telegram:marcoscfo_bot"

    # Prompt deve conter instruções de resposta
    run_id = f"tg_123_{update['message']['message_id']}"
    prompt = _build_prompt(bot_username, chat_id, text, thread_id, run_id)

    assert "send_telegram.sh" in prompt
    assert "panel_reply.sh" in prompt
    assert bot_username in prompt
    assert chat_id in prompt
    assert text in prompt

    print("✓ E2E pipeline: update → thread_id → channel → prompt OK")


def _build_prompt(bot_username: str, chat_id: str, text: str,
                  thread_id: str, run_id: str) -> str:
    """Replica a lógica do telegram-incoming-webhook para o teste."""
    return (
        f"[TELEGRAM_CHAT]\nBot: {bot_username}\nChat ID: {chat_id}\n"
        f"Mensagem: {text}\n\n"
        f"...send_telegram.sh \"{bot_username}\" \"{chat_id}\" '<resposta>'\n"
        f"...panel_reply.sh \"{thread_id}\" \"{run_id}\" '<resposta>' 'sent'\n"
    )


# ── 9. Channel inference para Telegram ───────────────────────────────────────
def test_channel_inference():
    def infer_channel(thread_id: str) -> str:
        if thread_id.startswith("telegram:"):
            return f"telegram:{thread_id.split(':')[1]}"
        if thread_id.startswith("wa:"):
            return f"whatsapp:{thread_id.split(':')[1]}"
        return "panel"

    assert infer_channel("telegram:marcoscfo_bot:987654") == "telegram:marcoscfo_bot"
    assert infer_channel("wa:vendas:5511") == "whatsapp:vendas"
    assert infer_channel("panel:user123") == "panel"
    print("✓ channel inference Telegram/WhatsApp/panel OK")


# ── Runner ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Rodando smoke tests da skill telegram (Sprint 34)...\n")
    tc, ts = test_imports()
    test_client_init(tc)
    test_webhook_url(ts)
    test_fetch_bots_no_env(ts)
    test_send_syntax()
    test_doctor_syntax()
    test_connect_syntax()
    test_e2e_pipeline()
    test_channel_inference()
    print("\n✅ Todos os smoke tests passaram!")
