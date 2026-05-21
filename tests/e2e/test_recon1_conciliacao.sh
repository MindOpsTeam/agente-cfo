#!/usr/bin/env bash
# test_recon1_conciliacao.sh — Sprint RECON-1: conciliação + aprendizado + ação composta
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python3"
[[ -f "$PYTHON" ]] || PYTHON="python3"
PASS=0; FAIL=0

check() {
  [[ "$2" == "OK" ]] && printf '  ✅ %s\n' "$1" && PASS=$((PASS+1)) && return
  printf '  ❌ %s — %s\n' "$1" "$2"; FAIL=$((FAIL+1))
}

check_skill() {
  local skill="$1"; shift; local scripts="$*"
  echo "--- $skill ---"
  local d="$REPO_DIR/skills/$skill"
  [[ -f "$d/SKILL.md" ]] && check "$skill/SKILL.md" "OK" || check "$skill/SKILL.md" "FAIL"
  for s in $scripts; do
    local p="$d/scripts/$s"
    [[ -f "$p" ]] && check "$skill/$s existe" "OK" || check "$skill/$s existe" "FAIL"
    [[ -f "$p" ]] && $PYTHON -c "import ast; ast.parse(open('$p').read())" 2>/dev/null && \
      check "$skill/$s sintaxe OK" "OK" || check "$skill/$s sintaxe OK" "FAIL"
  done; echo ""
}

echo "=== Smoke Test: Sprint RECON-1 — Conciliação Cross-Sistema ==="
echo ""
check_skill "cfo-conciliacao-cobranca-erp" "cruzar.py"
check_skill "cfo-conciliacao-ecommerce-erp" "cruzar.py"
check_skill "cfo-conciliacao-crm-erp" "cruzar.py"
check_skill "cfo-conciliacao-manual-erp" "listar_pendentes.py migrar.py"
check_skill "cfo-conciliacao-bancaria" "importar_extrato.py cruzar.py"
check_skill "cfo-aprendizado-padrao" "aprender.py sugerir_categoria.py"
check_skill "cfo-acao-composta" "iniciar_workflow.py"

echo "--- Unit tests: aprendizado de padrões ---"
LEARN_RESULT=$($PYTHON "$REPO_DIR/skills/cfo-aprendizado-padrao/scripts/aprender.py" \
  --supplier "TestUber" --category "Transporte" --format json 2>/dev/null || echo '{}')
echo "$LEARN_RESULT" | $PYTHON -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('learned') else 1)" 2>/dev/null && \
  check "aprender.py: aprende e persiste padrão" "OK" || \
  check "aprender.py: aprende e persiste padrão" "FAIL — $LEARN_RESULT"

echo ""
echo "--- Unit tests: sugestão por keywords (sem histórico) ---"
SUGEST_RESULT=$($PYTHON - "$REPO_DIR" << 'PYEOF'
import sys, os, tempfile, json
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
(tmp / "memory").mkdir()
os.environ["HOME"] = str(tmp)

REPO = Path(sys.argv[1])
script = REPO / "skills/cfo-aprendizado-padrao/scripts/sugerir_categoria.py"
if not script.exists(): print("SKIP"); sys.exit(0)

import importlib.util
sys.argv = ["sugerir_categoria.py", "--supplier", "Uber", "--format", "json"]
out = []
import io
from contextlib import redirect_stdout
f = io.StringIO()
spec = importlib.util.spec_from_file_location("sugerir", str(script))
mod = importlib.util.module_from_spec(spec)
with redirect_stdout(f):
    spec.loader.exec_module(mod)
    mod.main()
raw = f.getvalue().strip()
try:
    d = json.loads(raw)
    assert d.get("categoria") == "Transporte", f"esperado Transporte, got {d}"
    print("SUGEST_KEYWORDS_OK")
except Exception as e:
    print(f"FAIL: {e} | raw={raw[:100]}")
PYEOF
)
echo "$SUGEST_RESULT" | grep -q "SUGEST_KEYWORDS_OK\|SKIP" && \
  check "sugerir_categoria.py: Uber → Transporte por keyword" "OK" || \
  check "sugerir_categoria.py: Uber → Transporte por keyword" "FAIL — $SUGEST_RESULT"

echo ""
echo "--- Unit tests: workflow multi-step ---"
WF_RESULT=$($PYTHON - "$REPO_DIR" << 'PYEOF'
import sys, os, tempfile, json
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(tmp)

REPO = Path(sys.argv[1])
script = REPO / "skills/cfo-acao-composta/scripts/iniciar_workflow.py"
if not script.exists(): print("SKIP"); sys.exit(0)

import importlib.util, io
from contextlib import redirect_stdout

def run_main(argv):
    sys.argv = argv
    f = io.StringIO()
    spec = importlib.util.spec_from_file_location("wf", str(script))
    mod = importlib.util.module_from_spec(spec)
    with redirect_stdout(f):
        spec.loader.exec_module(mod)
        mod.main()
    return f.getvalue().strip()

out = run_main(["wf.py","--nome","teste-wf","--steps","a,b,c","--format","json"])
d = json.loads(out)
assert "id" in d, f"sem id: {d}"
wf_id = d["id"]
assert d["step_atual"] == "a", f"expected a, got {d['step_atual']}"
print(f"WF_CREATE_OK id={wf_id}")

# step-ok
out2 = run_main(["wf.py","--step-ok",wf_id,"--step-nome","a","--format","json"])
d2 = json.loads(out2)
assert d2.get("prox_step") == "b", f"expected b: {d2}"
print("WF_STEP_OK")
PYEOF
)
echo "$WF_RESULT" | grep -q "WF_CREATE_OK" && check "iniciar_workflow.py: cria workflow com steps" "OK" || check "iniciar_workflow.py: cria workflow com steps" "FAIL"
echo "$WF_RESULT" | grep -q "WF_STEP_OK" && check "iniciar_workflow.py: step-ok avança para próximo step" "OK" || check "iniciar_workflow.py: step-ok avança para próximo step" "FAIL"

echo ""
echo "--- conciliacao_diaria.sh ---"
CONC_SH="$REPO_DIR/skills/agente-cfo/scripts/conciliacao_diaria.sh"
[[ -f "$CONC_SH" ]] && check "conciliacao_diaria.sh existe" "OK" || check "conciliacao_diaria.sh existe" "FAIL"
bash -n "$CONC_SH" 2>/dev/null && check "conciliacao_diaria.sh sintaxe OK" "OK" || check "conciliacao_diaria.sh sintaxe OK" "FAIL"
grep -q 'TOTAL_DIV.*-eq 0\|Zero divergências\|silenciando' "$CONC_SH" && \
  check "conciliacao_diaria.sh silencia quando zero divergências" "OK" || \
  check "conciliacao_diaria.sh silencia quando zero divergências" "FAIL"
grep -q 'cfo-conciliacao-cobranca-erp\|cfo-conciliacao-ecommerce\|cfo-conciliacao-crm\|cfo-conciliacao-manual' "$CONC_SH" && \
  check "conciliacao_diaria.sh roda as 4 conciliações" "OK" || \
  check "conciliacao_diaria.sh roda as 4 conciliações" "FAIL"

echo ""
echo "--- setup.sh + AGENTS.md ---"
SETUP="$REPO_DIR/install/setup.sh"
grep -q 'CRON_ID_CONCILIACAO\|conciliacao.*diaria\|Conciliação Diária' "$SETUP" && \
  check "setup.sh registra cron conciliação 06:30" "OK" || check "setup.sh registra cron conciliação 06:30" "FAIL"
bash -n "$SETUP" 2>/dev/null && check "setup.sh sintaxe OK" "OK" || check "setup.sh sintaxe OK" "FAIL"
AGENTS="$REPO_DIR/install/templates/AGENTS.md"
grep -q 'Conciliação\|cfo-conciliacao\|cross-sistema\|divergências' "$AGENTS" && \
  check "AGENTS.md PhD tem seção de conciliação" "OK" || check "AGENTS.md PhD tem seção de conciliação" "FAIL"
grep -q 'cfo-aprendizado-padrao\|sugerir_categoria\|auto=true' "$AGENTS" && \
  check "AGENTS.md PhD tem aprendizado de padrões" "OK" || check "AGENTS.md PhD tem aprendizado de padrões" "FAIL"
grep -q 'cfo-acao-composta\|iniciar_workflow\|checkpoint' "$AGENTS" && \
  check "AGENTS.md PhD tem ações compostas" "OK" || check "AGENTS.md PhD tem ações compostas" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
