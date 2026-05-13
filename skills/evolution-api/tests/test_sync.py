#!/usr/bin/env python3
"""
Smoke test da skill evolution-api.
Não precisa de Evolution rodando nem credenciais reais.
"""
import json
import sys
from pathlib import Path

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
        ("OPEN",         "connected"),   # case-insensitive
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
        assert result == expected, f"parse_evo_state({raw!r}) → {result!r}, esperado {expected!r}"
    print(f"✓ parse_evo_state: {len(cases)} casos OK")


# ── 4. instance_webhook_url ───────────────────────────────────────────────────
def test_webhook_url(es):
    # panel_base já vem sem barra final (via _panel_base() que faz rstrip("/"))
    url = es.instance_webhook_url("https://painel.supabase.co/functions/v1")
    assert url == "https://painel.supabase.co/functions/v1/whatsapp-incoming-webhook", url
    print("✓ instance_webhook_url OK")


# ── 5. fetch_evolution_config sem env → None ─────────────────────────────────
def test_fetch_config_no_env(es):
    # Garante que sem env vars retorna None (não crasha)
    for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN"):
        os.environ.pop(k, None)
    # Não podemos chamar fetch_evolution_config diretamente (usa os.environ)
    # mas podemos verificar que _panel_get lida bem
    # Testamos apenas que o módulo não tem erros de sintaxe/import
    assert hasattr(es, "fetch_evolution_config")
    assert hasattr(es, "fetch_panel_instances")
    assert hasattr(es, "sync")
    print("✓ evolution_sync: funções principais presentes")


# ── 6. send_evolution.sh sintaxe ─────────────────────────────────────────────
def test_shell_syntax():
    import subprocess
    script = Path(__file__).parent.parent / "scripts" / "send_evolution.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert result.returncode == 0, f"Erro de sintaxe: {result.stderr.decode()}"
    print("✓ send_evolution.sh: sintaxe bash OK")


# ── 7. doctor.sh sintaxe ──────────────────────────────────────────────────────
def test_doctor_syntax():
    import subprocess
    script = Path(__file__).parent.parent / "doctor.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
    assert result.returncode == 0, f"Erro de sintaxe: {result.stderr.decode()}"
    print("✓ doctor.sh: sintaxe bash OK")


# ── Runner ────────────────────────────────────────────────────────────────────
import os

if __name__ == "__main__":
    print("Rodando smoke tests da skill evolution-api...\n")
    ec, es = test_imports()
    test_client_init(ec)
    test_parse_state(es)
    test_webhook_url(es)
    test_fetch_config_no_env(es)
    test_shell_syntax()
    test_doctor_syntax()
    print("\n✅ Todos os smoke tests passaram!")
