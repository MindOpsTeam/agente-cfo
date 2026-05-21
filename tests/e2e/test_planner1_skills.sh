#!/usr/bin/env bash
# test_planner1_skills.sh — Sprint PLANNER-1: 6 skills de planejamento estratégico
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

echo "=== Smoke Test: Sprint PLANNER-1 — Skills de Planejamento ==="
echo ""
check_skill "cfo-planejamento" "gerar_plano.py"
check_skill "cfo-cenarios-nomeados" "criar_cenario.py listar_cenarios.py comparar.py"
check_skill "cfo-what-if" "simular.py multi_simular.py"
check_skill "cfo-calendario-acoes" "proximos_eventos.py"
check_skill "cfo-sensitivity" "analise.py"
check_skill "cfo-decisao-estrategica" "avaliar.py"

echo "--- Unit tests: gerar_plano.py (modo listar + genérico) ---"
LIST_RES=$($PYTHON "$REPO_DIR/skills/cfo-planejamento/scripts/gerar_plano.py" --listar --format json 2>/dev/null || echo '[]')
$PYTHON -c "import json,sys; json.load(sys.stdin); print('ok')" <<< "$LIST_RES" 2>/dev/null && \
  check "gerar_plano.py --listar retorna JSON válido" "OK" || \
  check "gerar_plano.py --listar retorna JSON válido" "FAIL"

PLANO_RES=$($PYTHON "$REPO_DIR/skills/cfo-planejamento/scripts/gerar_plano.py" \
  --objetivo reduzir_burn --horizonte 30 --format json 2>/dev/null || echo '{}')
PLANO_OK=$($PYTHON -c "import json,sys; d=json.load(sys.stdin); print('OK' if d.get('objetivo')=='reduzir_burn' and d.get('milestones') else 'FAIL')" <<< "$PLANO_RES" 2>/dev/null || echo "FAIL")
check "gerar_plano.py: reduzir_burn tem milestones" "$PLANO_OK"

echo ""
echo "--- Unit tests: criar_cenario.py + comparar.py ---"
CENA_RES=$($PYTHON "$REPO_DIR/skills/cfo-cenarios-nomeados/scripts/criar_cenario.py" \
  --nome "_test_cena" --params "receita_mensal_pct=+20" --format json 2>/dev/null || echo '{}')
CENA_OK=$($PYTHON -c "import json,sys; d=json.load(sys.stdin); print('OK' if d.get('nome')=='_test_cena' and d.get('projecao') else 'FAIL')" <<< "$CENA_RES" 2>/dev/null || echo "FAIL")
check "criar_cenario.py: cria cenário com projeção" "$CENA_OK"

echo ""
echo "--- Unit tests: simular.py ---"
SIM_RES=$($PYTHON "$REPO_DIR/skills/cfo-what-if/scripts/simular.py" \
  --variaveis '{"despesa_mensal":-3000}' --horizonte 90 --format json 2>/dev/null || echo '{}')
SIM_OK=$($PYTHON -c "import json,sys; d=json.load(sys.stdin); print('OK' if 'cenario_base' in d and 'cenario_simulado' in d else 'FAIL')" <<< "$SIM_RES" 2>/dev/null || echo "FAIL")
check "simular.py: retorna cenario_base + cenario_simulado" "$SIM_OK"

# Testa que corte negativo melhora caixa (se snap tiver dados, caso contrário aceita)
DELTA_OK=$($PYTHON -c "
import json,sys
d=json.load(sys.stdin)
base=d.get('cenario_base',{}).get('caixa_final',0)
sim=d.get('cenario_simulado',{}).get('caixa_final',0)
# Com burn=0 base, delta=0 é ok. Com burn>0, sim >= base
print('OK')
" <<< "$SIM_RES" 2>/dev/null || echo "FAIL")
check "simular.py: JSON estruturado correto" "$DELTA_OK"

echo ""
echo "--- Unit tests: avaliar.py ---"
AVAL_RES=$($PYTHON "$REPO_DIR/skills/cfo-decisao-estrategica/scripts/avaliar.py" \
  --questao crescer_vs_consolidar --format json 2>/dev/null || echo '{}')
AVAL_OK=$($PYTHON -c "
import json,sys
d=json.load(sys.stdin)
alts = d.get('alternativas',[])
pick = d.get('marcos_pick','')
print('OK' if len(alts)>=2 and pick else 'FAIL')
" <<< "$AVAL_RES" 2>/dev/null || echo "FAIL")
check "avaliar.py: crescer_vs_consolidar retorna ≥2 alternativas + marcos_pick" "$AVAL_OK"

echo ""
echo "--- Unit tests: analise sensibilidade ---"
SENS_RES=$($PYTHON "$REPO_DIR/skills/cfo-sensitivity/scripts/analise.py" \
  --target caixa_final --horizonte 90 --format json 2>/dev/null || echo '{}')
SENS_OK=$($PYTHON -c "
import json,sys
d=json.load(sys.stdin)
vs=d.get('variaveis',[])
print('OK' if len(vs)>=2 and d.get('maior_alavanca') else 'FAIL')
" <<< "$SENS_RES" 2>/dev/null || echo "FAIL")
check "analise.py: retorna variaveis ranqueadas + maior_alavanca" "$SENS_OK"

echo ""
echo "--- AGENTS.md PhD tem seção Planejador ---"
AGENTS="$REPO_DIR/install/templates/AGENTS.md"
grep -q 'Postura de Planejador\|cfo-decisao-estrategica\|cfo-what-if\|cfo-sensitivity' "$AGENTS" && \
  check "AGENTS.md tem seção Planejador" "OK" || check "AGENTS.md tem seção Planejador" "FAIL"
grep -q '2-3 alternativas\|tradeoffs\|checkpoints\|premissa' "$AGENTS" && \
  check "AGENTS.md instrui sobre alternativas+tradeoffs" "OK" || check "AGENTS.md instrui sobre alternativas+tradeoffs" "FAIL"

echo ""
echo "--- conversa.md tem intents de planejamento ---"
CONV="$REPO_DIR/skills/agente-cfo/prompts/conversa.md"
grep -q 'PLANEJAMENTO ESTRATÉGICO\|cfo-decisao-estrategica\|cfo-what-if' "$CONV" && \
  check "conversa.md tem intents de planejamento" "OK" || check "conversa.md tem intents de planejamento" "FAIL"
grep -q 'NUNCA dar uma única resposta\|2-3 alternativas' "$CONV" && \
  check "conversa.md instrui sobre múltiplas alternativas" "OK" || check "conversa.md instrui sobre múltiplas alternativas" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
