#!/usr/bin/env bash
# test_credential_invalid.sh — Smoke test: gateways detectam 401/MISSING_SCOPES
# Usa clients stub que simulam 401, 403 MISSING_SCOPES e 200 success.
# Retorna: 0 se PASS, 1 se falhar.

set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python3"
[[ -f "$PYTHON" ]] || PYTHON="python3"
PASS=0; FAIL=0

check() {
  [[ "$2" == "OK" ]] && printf '  ✅ %s\n' "$1" && PASS=$((PASS+1)) && return
  printf '  ❌ %s — %s\n' "$1" "$2"; FAIL=$((FAIL+1))
}

echo "=== Smoke Test: Sprint VALIDATE-1 — Credential-aware Gateways ==="
echo ""

SCRIPTS="$REPO_DIR/skills/agente-cfo/scripts"

echo "--- credential_error.py: sintaxe + unit tests ---"
CRED_MOD="$SCRIPTS/credential_error.py"
[[ -f "$CRED_MOD" ]] && check "credential_error.py existe" "OK" || check "credential_error.py existe" "FAIL"
$PYTHON -c "import ast; ast.parse(open('$CRED_MOD').read())" 2>/dev/null && \
  check "credential_error.py sintaxe OK" "OK" || check "credential_error.py sintaxe OK" "FAIL"

# Unit tests do módulo
UNIT_RESULT=$($PYTHON - "$CRED_MOD" << 'PYEOF'
import sys, importlib.util, types

path = sys.argv[1]
spec = importlib.util.spec_from_file_location("credential_error", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Test 1: 401 detectado
r = mod.detect_credential_error("asaas", "HTTP 401: Unauthorized", "", 1)
assert r is not None, "401 não detectado"
assert r["error_kind"] == "credential_invalid", f"error_kind errado: {r}"
assert r["skill"] == "asaas"
assert r["http_status"] == 401
assert "message_pt" in r
assert "fix_url" in r
print("UNIT_401_OK")

# Test 2: MISSING_SCOPES detectado
r2 = mod.detect_credential_error("hubspot", "MISSING_SCOPES: crm.objects.deals.write", "", 1,
                                   required_scopes=["crm.objects.deals.write"])
assert r2 is not None, "MISSING_SCOPES não detectado"
assert r2["error_kind"] == "scopes_missing", f"error_kind errado: {r2}"
assert r2["required_scopes"] == ["crm.objects.deals.write"]
print("UNIT_SCOPES_OK")

# Test 3: sucesso não detecta nada
r3 = mod.detect_credential_error("asaas", '{"success": true, "balance": 1000}', "", 0)
assert r3 is None, f"falso positivo: {r3}"
print("UNIT_SUCCESS_OK")

# Test 4: 403 detectado
r4 = mod.detect_credential_error("iugu", "HTTP 403: Forbidden", "", 1)
assert r4 is not None
assert r4["error_kind"] == "credential_invalid"
print("UNIT_403_OK")
PYEOF
)

echo "$UNIT_RESULT" | grep -q "UNIT_401_OK" && check "detect_credential_error: 401 → credential_invalid" "OK" || check "detect_credential_error: 401 → credential_invalid" "FAIL"
echo "$UNIT_RESULT" | grep -q "UNIT_SCOPES_OK" && check "detect_credential_error: MISSING_SCOPES → scopes_missing" "OK" || check "detect_credential_error: MISSING_SCOPES → scopes_missing" "FAIL"
echo "$UNIT_RESULT" | grep -q "UNIT_SUCCESS_OK" && check "detect_credential_error: 200 success → None (sem falso positivo)" "OK" || check "detect_credential_error: 200 success → None (sem falso positivo)" "FAIL"
echo "$UNIT_RESULT" | grep -q "UNIT_403_OK" && check "detect_credential_error: 403 → credential_invalid" "OK" || check "detect_credential_error: 403 → credential_invalid" "FAIL"

echo ""
echo "--- Integração com erp_gateway.py (stub 401) ---"
# Cria skill stub que retorna 401
STUB_DIR=$(mktemp -d)
mkdir -p "$STUB_DIR/.openclaw/workspace/skills/_stub401_erp/scripts"
cat > "$STUB_DIR/.openclaw/workspace/skills/_stub401_erp/scripts/_stub401_erp_client.py" << 'STUBEOF'
import json, sys
print(json.dumps({"error": "HTTP 401: Unauthorized", "code": "invalid_api_key"}))
sys.exit(1)
STUBEOF

ERP_GW="$SCRIPTS/erp_gateway.py"
[[ -f "$ERP_GW" ]] && check "erp_gateway.py existe" "OK" || check "erp_gateway.py existe" "FAIL"
$PYTHON -c "import ast; ast.parse(open('$ERP_GW').read())" 2>/dev/null && \
  check "erp_gateway.py sintaxe OK" "OK" || check "erp_gateway.py sintaxe OK" "FAIL"
grep -q "wrap_subprocess_result\|credential_error" "$ERP_GW" && \
  check "erp_gateway.py importa credential_error" "OK" || check "erp_gateway.py importa credential_error" "FAIL"

# Testa integração funcional
RESULT401=$(HOME="$STUB_DIR" CFO_ERP_NAME="_stub401_erp" PANEL_BASE_URL="" \
  $PYTHON "$ERP_GW" get_balance 2>/dev/null || echo '{}')
ERR_KIND=$(echo "$RESULT401" | $PYTHON -c "import json,sys; d=json.load(sys.stdin); print(d.get('error_kind',''))" 2>/dev/null || echo "")
[[ "$ERR_KIND" == "credential_invalid" ]] && \
  check "erp_gateway: stub 401 → error_kind=credential_invalid" "OK" || \
  check "erp_gateway: stub 401 → error_kind=credential_invalid" "FAIL — got: $ERR_KIND (output: ${RESULT401:0:100})"

MSG_PT=$(echo "$RESULT401" | $PYTHON -c "import json,sys; d=json.load(sys.stdin); print(d.get('message_pt',''))" 2>/dev/null || echo "")
[[ -n "$MSG_PT" ]] && check "erp_gateway: message_pt presente na resposta 401" "OK" || \
  check "erp_gateway: message_pt presente na resposta 401" "FAIL — vazio"

rm -rf "$STUB_DIR"

echo ""
echo "--- Integração com erp_gateway.py (stub MISSING_SCOPES — HubSpot style) ---"
STUB_DIR2=$(mktemp -d)
mkdir -p "$STUB_DIR2/.openclaw/workspace/skills/_stubscopes_erp/scripts"
cat > "$STUB_DIR2/.openclaw/workspace/skills/_stubscopes_erp/scripts/_stubscopes_erp_client.py" << 'STUBEOF'
import json, sys
print(json.dumps({"error": "MISSING_SCOPES: crm.objects.deals.write", "code": "scopes_missing"}))
sys.exit(1)
STUBEOF

RESULT_SCOPES=$(HOME="$STUB_DIR2" CFO_ERP_NAME="_stubscopes_erp" PANEL_BASE_URL="" \
  $PYTHON "$ERP_GW" list_payables 2>/dev/null || echo '{}')
SCOPE_KIND=$(echo "$RESULT_SCOPES" | $PYTHON -c "import json,sys; d=json.load(sys.stdin); print(d.get('error_kind',''))" 2>/dev/null || echo "")
[[ "$SCOPE_KIND" == "scopes_missing" ]] && \
  check "erp_gateway: MISSING_SCOPES → error_kind=scopes_missing" "OK" || \
  check "erp_gateway: MISSING_SCOPES → error_kind=scopes_missing" "FAIL — got: $SCOPE_KIND"
rm -rf "$STUB_DIR2"

echo ""
echo "--- Sintaxe dos 4 gateways ---"
for gw in erp_gateway cobranca_gateway crm_gateway ecommerce_gateway; do
  f="$SCRIPTS/${gw}.py"
  [[ -f "$f" ]] && check "${gw}.py existe" "OK" || check "${gw}.py existe" "FAIL"
  [[ -f "$f" ]] && $PYTHON -c "import ast; ast.parse(open('$f').read())" 2>/dev/null && \
    check "${gw}.py sintaxe OK" "OK" || check "${gw}.py sintaxe OK" "FAIL"
  [[ -f "$f" ]] && grep -q "wrap_subprocess_result\|credential_error" "$f" && \
    check "${gw}.py usa credential_error" "OK" || check "${gw}.py usa credential_error" "FAIL"
done

echo ""
echo "--- conversa.md ---"
CONVERSA="$REPO_DIR/skills/agente-cfo/prompts/conversa.md"
grep -q "credential_invalid\|scopes_missing\|error_kind" "$CONVERSA" && \
  check "conversa.md tem protocolo credential_invalid" "OK" || \
  check "conversa.md tem protocolo credential_invalid" "FAIL"
grep -q "message_pt\|fix_url\|Workaround silencioso\|workaround silencioso\|NÃO\|Não" "$CONVERSA" && \
  check "conversa.md proíbe workaround silencioso" "OK" || \
  check "conversa.md proíbe workaround silencioso" "FAIL"

echo ""
echo "--- docs/SPRINT-VALIDATE-1-LOVABLE-PROMPT.md ---"
LOVABLE_DOC="$REPO_DIR/docs/SPRINT-VALIDATE-1-LOVABLE-PROMPT.md"
[[ -f "$LOVABLE_DOC" ]] && check "SPRINT-VALIDATE-1-LOVABLE-PROMPT.md existe" "OK" || \
  check "SPRINT-VALIDATE-1-LOVABLE-PROMPT.md existe" "FAIL"
grep -q "botão.*Testar\|credential_invalid\|integration-credentials-test" "$LOVABLE_DOC" 2>/dev/null && \
  check "Lovable prompt cobre botão Testar + error_kind" "OK" || \
  check "Lovable prompt cobre botão Testar + error_kind" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
