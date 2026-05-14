"""Smoke test do MCP server HubSpot — não precisa de API keys reais.

Testa ambos os modos de auth:
  - Private App Token (HUBSPOT_TOKEN)
  - OAuth (HUBSPOT_OAUTH_ACCESS_TOKEN + credenciais)
"""
import subprocess
import json
import sys
import os

VENV_PYTHON = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.venv', 'bin', 'python3')
SKILL_DIR = os.path.join(os.path.dirname(__file__), '..')


def _run_tools_list(extra_env: dict | None = None) -> tuple:
    """Inicia mcp_server.py, envia initialize + tools/list, retorna (tools, stderr)."""
    env = {**os.environ}
    # Remove qualquer auth real do ambiente pra não confundir
    for k in ("HUBSPOT_TOKEN", "HUBSPOT_OAUTH_ACCESS_TOKEN", "HUBSPOT_OAUTH_REFRESH_TOKEN",
              "HUBSPOT_OAUTH_CLIENT_ID", "HUBSPOT_OAUTH_CLIENT_SECRET"):
        env.pop(k, None)
    if extra_env:
        env.update(extra_env)

    proc = subprocess.Popen(
        [VENV_PYTHON, 'mcp_server.py'],
        cwd=SKILL_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    msgs = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '0'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
    ]
    stdin_data = ''.join(json.dumps(m) + '\n' for m in msgs).encode()
    try:
        out, err = proc.communicate(stdin_data, timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()

    lines = [l for l in out.decode().strip().split('\n') if l.strip()]
    tools_resp = None
    for line in lines:
        try:
            obj = json.loads(line)
            if obj.get('id') == 2:
                tools_resp = obj
        except Exception:
            pass

    if tools_resp is None:
        return None, err.decode()
    return tools_resp.get('result', {}).get('tools', []), err.decode()


def test_list_tools_private_app():
    """Modo Private App Token (HUBSPOT_TOKEN)."""
    tools, err = _run_tools_list({"HUBSPOT_TOKEN": "fake_private_app_token"})
    assert tools is not None, f"Sem resposta tools/list. stderr: {err[:500]}"
    assert len(tools) > 0, "Nenhuma tool registrada"
    for t in tools:
        assert 'name' in t
        assert 'inputSchema' in t
    print(f"OK — {len(tools)} tools (Private App mode)")


def test_list_tools_oauth():
    """Modo OAuth (HUBSPOT_OAUTH_* envs)."""
    tools, err = _run_tools_list({
        "HUBSPOT_OAUTH_ACCESS_TOKEN": "fake_oauth_access",
        "HUBSPOT_OAUTH_REFRESH_TOKEN": "fake_oauth_refresh",
        "HUBSPOT_OAUTH_CLIENT_ID": "e9278c85-cea0-4761-99f2-fd44f70a8dcb",
        "HUBSPOT_OAUTH_CLIENT_SECRET": "24f676c2-7e3d-4bdb-82f7-6a7310db4846",
    })
    assert tools is not None, f"Sem resposta tools/list (OAuth mode). stderr: {err[:500]}"
    assert len(tools) > 0, "Nenhuma tool registrada (OAuth mode)"
    print(f"OK — {len(tools)} tools (OAuth mode)")


def test_client_auth_detection():
    """Testa _validate_env diretamente sem hit real na API."""
    import sys
    sys.path.insert(0, os.path.join(SKILL_DIR, 'scripts'))
    sys.path.insert(0, os.path.join(SKILL_DIR, '..', '_lib'))

    # Salva e limpa env
    saved = {k: os.environ.pop(k, None) for k in (
        "HUBSPOT_TOKEN", "HUBSPOT_OAUTH_ACCESS_TOKEN", "HUBSPOT_OAUTH_REFRESH_TOKEN",
        "HUBSPOT_OAUTH_CLIENT_ID", "HUBSPOT_OAUTH_CLIENT_SECRET"
    )}

    try:
        from hubspot_client import HubSpotClient

        # Modo 1: Private App
        os.environ["HUBSPOT_TOKEN"] = "pat_fake_token"
        c = HubSpotClient.__new__(HubSpotClient)
        c._stages = {}
        c._validate_env()
        assert c._auth_mode == "private_app"
        assert c.token == "pat_fake_token"
        assert "Bearer pat_fake_token" in c.headers["Authorization"]
        print("OK — Private App Token auth mode detectado")
        del os.environ["HUBSPOT_TOKEN"]

        # Modo 2: OAuth
        os.environ.update({
            "HUBSPOT_OAUTH_ACCESS_TOKEN": "oauth_access_fake",
            "HUBSPOT_OAUTH_REFRESH_TOKEN": "oauth_refresh_fake",
            "HUBSPOT_OAUTH_CLIENT_ID": "fake_client_id",
            "HUBSPOT_OAUTH_CLIENT_SECRET": "fake_client_secret",
        })
        c2 = HubSpotClient.__new__(HubSpotClient)
        c2._stages = {}
        c2._validate_env()
        assert c2._auth_mode == "oauth"
        assert c2.token == "oauth_access_fake"
        assert "Bearer oauth_access_fake" in c2.headers["Authorization"]
        assert c2._oauth_client_id == "fake_client_id"
        print("OK — OAuth mode detectado")

        # Modo 3: Sem auth → deve levantar
        for k in ("HUBSPOT_TOKEN", "HUBSPOT_OAUTH_ACCESS_TOKEN", "HUBSPOT_OAUTH_REFRESH_TOKEN",
                  "HUBSPOT_OAUTH_CLIENT_ID", "HUBSPOT_OAUTH_CLIENT_SECRET"):
            os.environ.pop(k, None)
        try:
            c3 = HubSpotClient.__new__(HubSpotClient)
            c3._stages = {}
            c3._validate_env()
            assert False, "Deveria ter levantado RuntimeError"
        except RuntimeError as e:
            assert "nenhuma auth" in str(e).lower() or "HUBSPOT" in str(e)
            print("OK — RuntimeError sem auth")

    finally:
        # Restaura env
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


if __name__ == '__main__':
    test_client_auth_detection()
    test_list_tools_private_app()
    test_list_tools_oauth()
    print(f"\n✅ Todos os testes HubSpot passaram")
