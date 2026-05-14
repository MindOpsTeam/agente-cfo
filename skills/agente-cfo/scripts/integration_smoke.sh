#!/usr/bin/env bash
# integration_smoke.sh — Valida pipeline E2E: credencial → MCP → tool response
#
# Uso: bash integration_smoke.sh <skill_name>
# Exit 0 = PASS, 1 = FAIL

set -euo pipefail

SKILL="${1:-}"
if [[ -z "$SKILL" ]]; then
    echo "Uso: $0 <skill_name>  (ex: asaas, hubspot, omie)" >&2
    exit 1
fi

SECRETS_DIR="${HOME}/.openclaw/secrets"
WORKSPACE="${HOME}/.openclaw/workspace/skills"
ENV_FILE="${SECRETS_DIR}/${SKILL}.env"
MCP_SCRIPT="${WORKSPACE}/${SKILL}/mcp_server.py"

PASS=0; FAIL=0
_ok()   { echo "  ✓ $*"; }
_fail() { echo "  ✗ $*"; FAIL=$((FAIL+1)); }
_warn() { echo "  ⚠ $*"; }

echo ""
echo "=== integration_smoke: ${SKILL} ==="
echo ""

# ── 1. Secrets file ─────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    PERM=$(stat -c "%a" "$ENV_FILE" 2>/dev/null || stat -f "%OLp" "$ENV_FILE" 2>/dev/null || echo "???")
    _ok "secrets present: ${ENV_FILE} (mode=${PERM})"
    [[ "$PERM" != "600" ]] && _warn "chmod 600 recomendado (atual: $PERM)"
else
    # Supabase projects usam 'supabase_*' — secrets são inline no MCP, não em .env separado
    if [[ "$SKILL" == supabase_* ]]; then
        _ok "secrets: n/a (supabase project — chave inline no MCP config)"
    else
        _fail "secrets missing: ${ENV_FILE} não encontrado"
    fi
fi

# ── 2. MCP registrado ────────────────────────────────────────────────────────
MCP_CONFIG=$(openclaw mcp show "$SKILL" --json 2>/dev/null || echo "null")
if [[ "$MCP_CONFIG" != "null" && -n "$MCP_CONFIG" ]]; then
    CMD=$(echo "$MCP_CONFIG" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('command','?'))" 2>/dev/null || echo "?")
    ARGS=$(echo "$MCP_CONFIG" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(d.get('args',[])[:2]))" 2>/dev/null || echo "")
    _ok "mcp registered: ${CMD} ${ARGS}"
else
    _fail "mcp not registered: 'openclaw mcp show ${SKILL}' retornou null"
fi

# ── 3. MCP responde (list tools) ─────────────────────────────────────────────
if [[ -f "$MCP_SCRIPT" ]]; then
    # Monta env pra o processo
    ENV_ARGS=()
    if [[ -f "$ENV_FILE" ]]; then
        while IFS= read -r line; do
            [[ -z "$line" || "$line" == \#* ]] && continue
            ENV_ARGS+=("$line")
        done < "$ENV_FILE"
    fi

    # Envia initialize + tools/list e captura resposta com timeout
    MSGS='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'$'\n'
    MSGS+='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'$'\n'

    RESPONSE=$(
        env "${ENV_ARGS[@]}" python3 "$MCP_SCRIPT" <<< "$MSGS" 2>/dev/null \
        | timeout 8 python3 -c "
import sys, json
tools_resp = None
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
        if obj.get('id') == 2:
            tools_resp = obj
            break
    except:
        pass
if tools_resp:
    tools = tools_resp.get('result', {}).get('tools', [])
    print(len(tools))
else:
    print('NO_RESPONSE')
" 2>/dev/null || echo "ERROR"
    )

    case "$RESPONSE" in
        NO_RESPONSE) _fail "mcp no response (tools/list não retornou id=2)" ;;
        ERROR|"")    _fail "mcp error (timeout ou crash)" ;;
        *)
            if [[ "$RESPONSE" =~ ^[0-9]+$ ]]; then
                _ok "mcp responds: ${RESPONSE} tools"
            else
                _fail "mcp unexpected response: ${RESPONSE}"
            fi
            ;;
    esac
else
    if [[ "$SKILL" == supabase_* ]]; then
        # Supabase usa npx — verifica se npx está disponível
        if command -v npx &>/dev/null; then
            _ok "mcp responds: n/a (npx-based supabase server — npx disponível)"
        else
            _fail "mcp check: npx não disponível (supabase usa @supabase/mcp-server-supabase)"
        fi
    else
        _fail "mcp script missing: ${MCP_SCRIPT}"
    fi
fi

# ── 4. Gateway ativo ─────────────────────────────────────────────────────────
GW_STATUS=$(systemctl is-active openclaw-gateway 2>/dev/null || echo "unknown")
case "$GW_STATUS" in
    active)  _ok "gateway: active" ;;
    unknown) _warn "gateway: status desconhecido (não-Linux ou systemd indisponível)" ;;
    *)       _fail "gateway: ${GW_STATUS}" ;;
esac

# ── Resultado ────────────────────────────────────────────────────────────────
echo ""
if [[ $FAIL -eq 0 ]]; then
    echo "  RESULT: ✅ PASS"
    exit 0
else
    echo "  RESULT: ❌ FAIL (${FAIL} check(s) falharam)"
    exit 1
fi
