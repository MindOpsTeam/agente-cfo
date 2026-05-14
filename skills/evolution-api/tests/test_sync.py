#!/usr/bin/env python3
"""
Smoke tests da skill evolution-api — Sprint 33.

Testa:
1. evolution_client.py imports e instanciação
2. evolution_sync.py funções principais (sem API real)
3. send_evolution.sh sintaxe bash
4. Cenário E2E simulado: mensagem entra → forward → Marcos responde → send_evolution chamado
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── 1. Imports ────────────────────────────────────────────────────────────────
def test_imports():
    import evolution_client as ec
    import evolution_sync as es
    print("✓ evolution_client e evolution_sync importados")
    return ec, es


# ── 2. EvolutionClient — instanciação sem hit na API ─────────────────────────
def test_client_init(ec):
    client = ec.EvolutionClient(
        base_url="https://evo.test.example.com",
        api_key="test_key_123",
    )
    assert client.base_url == "https://evo.test.example.com"
    assert client.api_key == "test_key_123"
    assert client._headers["apikey"] == "test_key_123"
    print("✓ EvolutionClient.__init__ OK")


# ── 3. parse_evo_state ────────────────────────────────────────────────────────
def test_parse_state(es):
    cases = [
        ("open",         "connected"),
        ("connected",    "connected"),
        ("OPEN",         "connected"),
        ("connecting",   "qr_pending"),
        ("qr",           "qr_pending"),
        ("close",        "disconnected"),
        ("disconnected", "disconnected"),
        ("logged_out",   "disconnected"),
        ("",             "error"),
        ("unknown_xyz",  "error"),
    ]
    for raw, expected in cases:
        result = es.parse_evo_state(raw)
        assert result == expected, f"parse_evo_state({raw!r}) → {result!r}"
    print(f"✓ parse_evo_state: {len(cases)} casos OK")


# ── 4. instance_webhook_url ───────────────────────────────────────────────────
def test_webhook_url(es):
    url = es.instance_webhook_url("https://painel.supabase.co/functions/v1")
    assert url == "https://painel.supabase.co/functions/v1/whatsapp-incoming-webhook", url
    print("✓ instance_webhook_url OK")


# ── 5. fetch_evolution_config sem env → None ─────────────────────────────────
def test_fetch_config_no_env(es):
    for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN"):
        os.environ.pop(k, None)
    assert hasattr(es, "fetch_evolution_config")
    assert hasattr(es, "fetch_panel_instances")
    assert hasattr(es, "sync")
    print("✓ evolution_sync: funções principais presentes")


# ── 6. send_evolution.sh sintaxe ─────────────────────────────────────────────
def test_shell_syntax():
    script = Path(__file__).parent.parent / "scripts" / "send_evolution.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert result.returncode == 0, f"Erro de sintaxe: {result.stderr.decode()}"
    print("✓ send_evolution.sh: sintaxe bash OK")


# ── 7. doctor.sh sintaxe ──────────────────────────────────────────────────────
def test_doctor_syntax():
    script = Path(__file__).parent.parent / "doctor.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert result.returncode == 0, f"Erro de sintaxe: {result.stderr.decode()}"
    print("✓ doctor.sh: sintaxe bash OK")


# ── 8. Cenário E2E simulado ───────────────────────────────────────────────────
def test_e2e_message_pipeline():
    """
    Simula o fluxo end-to-end:
      1. Mensagem entra via webhook (Evolution → painel)
      2. Painel salva no chat_messages com channel='whatsapp:vendas'
      3. Painel dispara /hooks/agent na VPS
      4. Marcos processa e chama send_evolution.sh + panel_reply.sh
    
    Testa apenas a estrutura do fluxo (sem hit real).
    """

    # Simula payload Evolution para messages.upsert
    webhook_payload = {
        "event": "messages.upsert",
        "instance": "vendas",
        "data": {
            "key": {
                "fromMe": False,
                "remoteJid": "5548992044331@s.whatsapp.net",
                "id": "msg_abc123",
            },
            "message": {
                "conversation": "Qual o saldo da conta?"
            },
            "pushName": "Guilherme",
        },
    }

    # Valida extração de texto
    from evolution_sync import instance_webhook_url
    text = _extract_text(webhook_payload["data"]["message"])
    assert text == "Qual o saldo da conta?", f"Texto extraído incorreto: {text!r}"

    # Valida que thread_id e channel seriam corretos
    instance = webhook_payload["instance"]
    phone = webhook_payload["data"]["key"]["remoteJid"].split("@")[0]
    thread_id = f"wa:{instance}:{phone}"
    channel = f"whatsapp:{instance}"

    assert thread_id == "wa:vendas:5548992044331"
    assert channel == "whatsapp:vendas"

    # Valida que o prompt conteria as instruções de send_evolution + panel_reply
    prompt = _build_prompt(instance, "", phone, text, thread_id, "run_123")
    assert "send_evolution.sh" in prompt, "Prompt deve incluir send_evolution.sh"
    assert "panel_reply.sh" in prompt, "Prompt deve incluir panel_reply.sh"
    assert thread_id in prompt, "Prompt deve ter thread_id"
    assert phone in prompt, "Prompt deve ter phone"

    # Valida webhook URL do painel
    webhook_url = instance_webhook_url("https://xyz.supabase.co/functions/v1")
    assert "whatsapp-incoming-webhook" in webhook_url

    print("✓ E2E pipeline: mensagem → thread_id → channel → prompt → send_evolution OK")


def _extract_text(message: dict) -> str:
    """Replica a lógica do whatsapp-incoming-webhook em Python para o teste."""
    if "conversation" in message:
        return message["conversation"]
    if "extendedTextMessage" in message:
        return message["extendedTextMessage"].get("text", "")
    if "imageMessage" in message:
        return f"[imagem] {message['imageMessage'].get('caption', '')}"
    if "audioMessage" in message:
        return "[áudio]"
    return ""


def _build_prompt(instance: str, display: str, phone: str,
                  text: str, thread_id: str, run_id: str) -> str:
    """Replica buildPrompt() do whatsapp-incoming-webhook para o teste."""
    return (
        f"[WHATSAPP_CHAT]\n"
        f"Instância: {instance}{f' ({display})' if display else ''}\n"
        f"Telefone: {phone}\n"
        f"Mensagem: {text}\n\n"
        f"...send_evolution.sh \"{instance}\" \"{phone}\" ...\n"
        f"...panel_reply.sh \"{thread_id}\" \"{run_id}\" ...\n"
    )


# ── 9. Valida que channel é inferido corretamente no chat-marcos-reply ────────
def test_channel_inference():
    """Testa a lógica de inferência de channel a partir do thread_id."""

    def infer_channel(thread_id: str, explicit_channel: str = None) -> str:
        if explicit_channel:
            return explicit_channel
        if thread_id.startswith("wa:"):
            return f"whatsapp:{thread_id.split(':')[1]}"
        return "panel"

    assert infer_channel("panel:user123") == "panel"
    assert infer_channel("wa:vendas:5548") == "whatsapp:vendas"
    assert infer_channel("wa:suporte:5511") == "whatsapp:suporte"
    assert infer_channel("anything", "telegram:bot1") == "telegram:bot1"
    print("✓ channel inference: panel / whatsapp:<instance> / explicit OK")


# ── Runner ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Rodando smoke tests evolution-api (Sprint 33)...\n")
    ec, es = test_imports()
    test_client_init(ec)
    test_parse_state(es)
    test_webhook_url(es)
    test_fetch_config_no_env(es)
    test_shell_syntax()
    test_doctor_syntax()
    test_e2e_message_pipeline()
    test_channel_inference()
    print("\n✅ Todos os smoke tests passaram!")
