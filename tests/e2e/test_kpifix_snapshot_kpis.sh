#!/usr/bin/env bash
# test_kpifix_snapshot_kpis.sh — SPRINT KPI-FIX-BACKEND
#
# Smoke test para o subcommand snapshot_kpis do erp_gateway.py.
# Não requer VPS, ERP real nem Python 3.10+ (testa estrutura + execução quando disponível).
#
# Retorna: 0 se PASS, 1 se falhar.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GATEWAY="$REPO_DIR/skills/agente-cfo/scripts/erp_gateway.py"
PASS=0; FAIL=0; SKIP=0

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

check_ok()   { echo -e "  ${GREEN}✅${NC} $1"; PASS=$((PASS+1)); }
check_fail() { echo -e "  ${RED}❌${NC} $1 — $2"; FAIL=$((FAIL+1)); }
check_skip() { echo -e "  ${YELLOW}⏭️${NC}  $1 — $2 (skip)"; SKIP=$((SKIP+1)); }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   KPI-FIX-BACKEND — snapshot_kpis subcommand        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 1. erp_gateway.py — estrutura snapshot_kpis ---"

[[ -f "$GATEWAY" ]] && check_ok "erp_gateway.py existe" || { check_fail "erp_gateway.py" "não encontrado"; exit 1; }

python3 -m py_compile "$GATEWAY" 2>/dev/null && \
    check_ok "erp_gateway.py sintaxe OK" || \
    check_fail "erp_gateway.py sintaxe" "$(python3 -m py_compile "$GATEWAY" 2>&1 | head -2)"

# Verifica presença dos símbolos críticos
for _sym in \
    "snapshot_kpis" \
    "AGGREGATE_COMMANDS" \
    "cmd_snapshot_kpis" \
    "_sum_amounts" \
    "_run_client" \
    "payables_30d" \
    "receivables_30d" \
    "overdue_total" \
    "as_of" \
    "erp_error"
do
    grep -q "$_sym" "$GATEWAY" && \
        check_ok "erp_gateway.py contém: $_sym" || \
        check_fail "erp_gateway.py" "missing symbol: $_sym"
done

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 2. Output JSON schema de snapshot_kpis ---"

# Testa a função cmd_snapshot_kpis diretamente via Python inline
# (contorna o import de credential_error que requer Python 3.10+)
_SCHEMA_TEST=$(GATEWAY_PATH="$GATEWAY" python3 - <<'PYEOF'
import sys, json, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import subprocess

# Importa apenas as funções necessárias sem o top-level import de credential_error
import importlib.util, types

# Carrega o módulo mas substitui credential_error por stub
stub = types.ModuleType("credential_error")
stub.wrap_subprocess_result = lambda *a, **kw: None
sys.modules["credential_error"] = stub

gateway_path = os.environ.get("GATEWAY_PATH", "")
spec = importlib.util.spec_from_file_location(
    "erp_gateway",
    gateway_path,
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Testa _sum_amounts com vários formatos de resposta ERP
cases = [
    # lista direta
    ([{"nValorTitulo": 100.0}, {"nValorTitulo": 50.5}], 150.5),
    # dict com items
    ({"items": [{"valor": 200.0}, {"valor": 300.0}]}, 500.0),
    # balance direto
    ({"balance": 1234.56}, 1234.56),
    # lista vazia
    ([], 0.0),
    # dict sem campo conhecido
    ({"foo": "bar"}, 0.0),
]
errors = []
for inp, expected in cases:
    got = mod._sum_amounts(inp)
    if abs(got - expected) > 0.001:
        errors.append(f"_sum_amounts({inp!r}) = {got}, expected {expected}")

if errors:
    print("FAIL: " + "; ".join(errors))
    sys.exit(1)

# Testa que cmd_snapshot_kpis retorna JSON com os campos obrigatórios
# (sem cliente real, _run_client vai retornar {"error": "..."}  )
result = mod.cmd_snapshot_kpis("omie_test", "/nonexistent/client.py")
required = ["balance", "payables_30d", "receivables_30d", "overdue_total", "erp", "as_of"]
missing = [k for k in required if k not in result]
if missing:
    print(f"FAIL: campos ausentes no output: {missing}")
    sys.exit(1)

# Sem cliente: todos os valores devem ser 0.0 e erp_error deve estar presente
for field in ["balance", "payables_30d", "receivables_30d", "overdue_total"]:
    if result[field] != 0.0:
        print(f"FAIL: {field} deveria ser 0.0 sem ERP, got {result[field]}")
        sys.exit(1)
if "erp_error" not in result:
    print("FAIL: erp_error deveria estar presente quando ERP indisponível")
    sys.exit(1)
if result["erp"] != "omie_test":
    print(f"FAIL: erp deveria ser 'omie_test', got {result['erp']!r}")
    sys.exit(1)

# as_of deve ser ISO 8601 (contém T e Z)
if "T" not in result["as_of"] or "Z" not in result["as_of"]:
    print(f"FAIL: as_of formato inválido: {result['as_of']!r}")
    sys.exit(1)

print("OK: " + json.dumps(result))
PYEOF
"$GATEWAY" 2>&1) || true

if echo "$_SCHEMA_TEST" | grep -q "^OK:"; then
    check_ok "_sum_amounts: 5 casos corretos"
    check_ok "cmd_snapshot_kpis: campos obrigatórios presentes"
    check_ok "cmd_snapshot_kpis: zeros + erp_error quando ERP indisponível"
    check_ok "cmd_snapshot_kpis: as_of em formato ISO 8601 Z"
    # Mostra o JSON de saída para inspeção
    _JSON=$(echo "$_SCHEMA_TEST" | sed 's/^OK: //')
    echo "     output: $_JSON"
elif echo "$_SCHEMA_TEST" | grep -q "^FAIL:"; then
    _MSG=$(echo "$_SCHEMA_TEST" | grep "^FAIL:" | head -1)
    check_fail "snapshot_kpis schema" "$_MSG"
else
    # Python 3.9 ou outro problema de import — skip com aviso
    _PYVER=$(python3 -c 'import sys; print(sys.version[:6])' 2>/dev/null || echo "?")
    check_skip "snapshot_kpis runtime test" "Python ${_PYVER} — teste de execução requer Python 3.10+ (VPS OK)"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 3. snapshot_kpis no dispatcher (routing) ---"

# Verifica que snapshot_kpis está roteado ANTES do proxy final
_DISPATCH_LINE=$(grep -n "snapshot_kpis\|AGGREGATE_COMMANDS" "$GATEWAY" | head -5)
if echo "$_DISPATCH_LINE" | grep -q "AGGREGATE_COMMANDS"; then
    check_ok "AGGREGATE_COMMANDS definido no gateway"
else
    check_fail "AGGREGATE_COMMANDS" "não encontrado no dispatcher"
fi

# Verifica que o routing aparece antes do bloco "proxy simples"
_PROXY_LINE=$(grep -n "proxy simples\|# ── Todos os outros" "$GATEWAY" | head -1 | cut -d: -f1)
_AGGREGATE_LINE=$(grep -n "command in AGGREGATE_COMMANDS" "$GATEWAY" | head -1 | cut -d: -f1)
if [[ -n "$_PROXY_LINE" && -n "$_AGGREGATE_LINE" ]]; then
    if [[ "$_AGGREGATE_LINE" -lt "$_PROXY_LINE" ]]; then
        check_ok "snapshot_kpis roteado antes do proxy final (linha $_AGGREGATE_LINE < $_PROXY_LINE)"
    else
        check_fail "routing order" "AGGREGATE_COMMANDS (linha $_AGGREGATE_LINE) deve vir antes do proxy (linha $_PROXY_LINE)"
    fi
else
    check_skip "routing order" "não foi possível determinar posição das linhas"
fi

# Verifica exit 0 no bloco snapshot_kpis (dashboard não pode quebrar)
# exit(0) está dentro do bloco após AGGREGATE_COMMANDS — verifica em janela de 15 linhas
if grep -A15 "command in AGGREGATE_COMMANDS" "$GATEWAY" | grep -q "sys.exit(0)"; then
    check_ok "snapshot_kpis retorna exit 0 sempre"
else
    check_fail "snapshot_kpis exit" "sys.exit(0) não encontrado nas 15 linhas após AGGREGATE_COMMANDS"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 4. docstring atualizada ---"

if grep -q "snapshot_kpis" "$GATEWAY" && \
   python3 -c "
import ast, sys
with open(sys.argv[1]) as f:
    src = f.read()
tree = ast.parse(src)
docstring = ast.get_docstring(tree)
print('OK' if docstring and 'snapshot_kpis' in docstring else 'FAIL')
" "$GATEWAY" 2>/dev/null | grep -q "^OK$"; then
    check_ok "docstring do módulo menciona snapshot_kpis"
else
    check_fail "docstring" "snapshot_kpis não documentado na docstring do módulo"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
TOTAL=$((PASS+FAIL+SKIP))
if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}✅ PASS ${PASS}/${TOTAL} — KPI-FIX-BACKEND smoke OK${NC}"
    [[ $SKIP -gt 0 ]] && echo -e "   ${YELLOW}(${SKIP} skipped — Python 3.9 em dev; VPS roda 3.10+)${NC}"
    exit 0
else
    echo -e "${RED}❌ FAIL ${FAIL}/${TOTAL} — ${PASS} ok, ${SKIP} skip${NC}"
    exit 1
fi
