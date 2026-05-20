#!/usr/bin/env bash
# test_agente_cfo_mcp.sh — Smoke test do MCP server de agente-cfo
# Verifica: boot, handshake JSON-RPC, tools/list (espera 14 tools), tool_call controlado.
# Retorna: 0 se PASS, 1 se falhar.

set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python3"
MCP_SERVER="${REPO_DIR}/skills/agente-cfo/mcp_server.py"

PASS=0
FAIL=0

check() {
  local desc="$1" result="$2"
  if [[ "$result" == "OK" ]]; then
    printf '  ✅ %s\n' "$desc"
    PASS=$((PASS+1))
  else
    printf '  ❌ %s — %s\n' "$desc" "$result"
    FAIL=$((FAIL+1))
  fi
}

echo "=== Smoke Test: agente-cfo MCP Server ==="
echo ""

echo "--- Pré-requisitos ---"
[[ -f "$PYTHON" ]] && check "venv python3 existe" "OK" || check "venv python3 existe" "FAIL: $PYTHON não encontrado"
[[ -f "$MCP_SERVER" ]] && check "mcp_server.py existe" "OK" || check "mcp_server.py existe" "FAIL"

# Sintaxe
"$PYTHON" -c "import ast; ast.parse(open('$MCP_SERVER').read()); print('ok')" 2>/dev/null | grep -q "ok" && \
  check "mcp_server.py sintaxe Python OK" "OK" || check "mcp_server.py sintaxe Python OK" "FAIL"

echo ""
echo "--- Handshake JSON-RPC ---"

RESULT=$("$PYTHON" - "$REPO_DIR" << 'PYEOF'
import subprocess, json, time, os, sys

PYTHON = sys.executable
REPO_DIR = sys.argv[1]
MCP_PATH = os.path.join(REPO_DIR, 'skills/agente-cfo/mcp_server.py')

env = {**os.environ, 'OMIE_APP_KEY': 'dummy', 'OMIE_APP_SECRET': 'dummy'}

proc = subprocess.Popen(
    [PYTHON, MCP_PATH],
    cwd=os.path.dirname(MCP_PATH),
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    env=env,
)
time.sleep(1.2)
rc = proc.poll()
if rc is not None:
    print(f"BOOT_FAIL:{proc.stderr.read().decode()[:200]}")
    sys.exit(0)
print("BOOT_OK")

def sr(p, msg, timeout=10):
    p.stdin.write((json.dumps(msg) + '\n').encode()); p.stdin.flush()
    import time as t; deadline = t.time() + timeout
    while t.time() < deadline:
        line = p.stdout.readline()
        if line.strip():
            try: return json.loads(line.strip())
            except: pass
        t.sleep(0.05)
    return None

r = sr(proc, {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'1'}}})
print("INIT_OK" if r and 'result' in r else f"INIT_FAIL:{r}")

proc.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'}).encode() + b'\n')
proc.stdin.flush(); time.sleep(0.2)

r2 = sr(proc, {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}})
if r2 and 'result' in r2:
    tools = r2['result'].get('tools', [])
    print(f"TOOLS:{len(tools)}")
    for t in tools: print(f"  TOOL:{t['name']}")
else:
    print(f"TOOLS_FAIL:{r2}")

# Tool call dummy
if r2 and 'result' in r2 and r2['result'].get('tools'):
    r3 = sr(proc, {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'cfo_get_balance','arguments':{}}}, timeout=12)
    if r3:
        if 'error' in r3 or ('result' in r3):
            print("CTRL_ERR_OK")
        else:
            print(f"CTRL_ERR_UNEXPECTED:{r3}")
    else:
        print("CTRL_ERR_TIMEOUT")

proc.terminate(); proc.wait(timeout=3)
PYEOF
)

echo "$RESULT" | grep -q "BOOT_OK" && check "boot sem crash" "OK" || check "boot sem crash" "FAIL"
echo "$RESULT" | grep -q "INIT_OK" && check "initialize (2024-11-05)" "OK" || check "initialize (2024-11-05)" "FAIL"

TOOL_COUNT=$(echo "$RESULT" | grep "^TOOLS:" | sed 's/TOOLS://' || echo "0")
[[ "$TOOL_COUNT" -ge 14 ]] && check "tools/list ≥ 14 tools (got $TOOL_COUNT)" "OK" || \
  check "tools/list ≥ 14 tools (got $TOOL_COUNT)" "FAIL"

echo "$RESULT" | grep -q "CTRL_ERR_OK" && check "tool_call retorna resultado controlado" "OK" || \
  check "tool_call retorna resultado controlado" "FAIL — $(echo "$RESULT" | grep CTRL_ERR || echo sem resultado)"

echo ""
echo "--- Ferramenta por ferramenta ---"
EXPECTED_TOOLS=(
  cfo_get_balance cfo_list_payables cfo_list_receivables cfo_list_overdue
  cfo_get_cash_projection cfo_company_info cfo_create_payable cfo_create_receivable
  cfo_pay_payable cfo_mark_received cfo_cancel_payable cfo_update_category
  cfo_write_event cfo_post_reply
)
for tool in "${EXPECTED_TOOLS[@]}"; do
  echo "$RESULT" | grep -q "TOOL:$tool" && check "$tool exposta" "OK" || check "$tool exposta" "FAIL"
done

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
