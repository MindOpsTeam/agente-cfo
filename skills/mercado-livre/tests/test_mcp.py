"""Smoke test do MCP server — nao precisa de API keys reais."""
import subprocess, json, sys, os

VENV_PYTHON = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.venv', 'bin', 'python3')

def test_list_tools():
    proc = subprocess.Popen(
        [VENV_PYTHON, 'mcp_server.py'],
        cwd=os.path.join(os.path.dirname(__file__), '..'),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    msgs = [
        {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'0'}}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
        {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},
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
        except:
            pass

    assert tools_resp is not None, f'Sem resposta tools/list. stderr: {err.decode()[:500]}'
    tools = tools_resp['result']['tools']
    assert len(tools) > 0, 'Nenhuma tool registrada'
    for t in tools:
        assert 'name' in t
        assert 'inputSchema' in t
    print(f'OK — {len(tools)} tools registradas')

if __name__ == '__main__':
    test_list_tools()
