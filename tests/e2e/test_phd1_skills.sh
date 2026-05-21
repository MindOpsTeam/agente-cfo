#!/usr/bin/env bash
# test_phd1_skills.sh — Smoke test das 7 skills CFO PhD (Sprint PHD-1)
# Verifica estrutura, sintaxe e imports. Não executa contra APIs reais.
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

echo "=== Smoke Test: Sprint PHD-1 — Skills CFO Especializadas ==="
echo ""

# Lista de skills e scripts esperados
check_skill_scripts() {
  local skill="$1"; shift
  local scripts="$*"
  echo "--- ${skill} ---"
  local SKILL_DIR="$REPO_DIR/skills/$skill"
  [[ -f "$SKILL_DIR/SKILL.md" ]] && check "$skill/SKILL.md existe" "OK" || \
    check "$skill/SKILL.md existe" "FAIL"
  for script in $scripts; do
    local sp="$SKILL_DIR/scripts/$script"
    [[ -f "$sp" ]] && check "$skill/$script existe" "OK" || check "$skill/$script existe" "FAIL"
    [[ -f "$sp" ]] && \
      $PYTHON -c "import ast; ast.parse(open('$sp').read())" 2>/dev/null && \
      check "$skill/$script sintaxe Python OK" "OK" || \
      check "$skill/$script sintaxe Python OK" "FAIL"
  done
  echo ""
}

check_skill_scripts "cfo-analise-estrategica" "kpis.py margem.py dre.py analise_vertical.py analise_horizontal.py"
check_skill_scripts "cfo-projecao" "runway.py cenario.py burn.py ponto_equilibrio.py"
check_skill_scripts "cfo-inadimplencia" "aging.py top_devedores.py sugestao_cobranca.py"
check_skill_scripts "cfo-anomalias" "zscore.py anomalia_categoria.py concentracao_cliente.py"
check_skill_scripts "cfo-tributacao-br" "calendario_fiscal.py sugerir_regime.py"
check_skill_scripts "cfo-cobranca-orquestrada" "orquestrar_cobranca.py"
check_skill_scripts "cfo-relatorios-executivos" "relatorio_semanal.py relatorio_mensal.py"

# Template AGENTS.md PhD
echo "--- Template AGENTS.md PhD ---"
TMPL="$REPO_DIR/install/templates/AGENTS.md"
[[ -f "$TMPL" ]] && check "install/templates/AGENTS.md existe" "OK" || \
  check "install/templates/AGENTS.md existe" "FAIL"
[[ -f "$TMPL" ]] && grep -q "Discovery proativo\|Postura Agentic\|PhD" "$TMPL" && \
  check "AGENTS.md PhD contém postura agentic" "OK" || \
  check "AGENTS.md PhD contém postura agentic" "FAIL"
[[ -f "$TMPL" ]] && grep -q "zscore\|kpis.py\|runway\|DSO" "$TMPL" && \
  check "AGENTS.md PhD referencia skills especializadas" "OK" || \
  check "AGENTS.md PhD referencia skills especializadas" "FAIL"
[[ -f "$TMPL" ]] && grep -q "cfo-relatorios-executivos\|relatorio_semanal\|relatorio_mensal" "$TMPL" && \
  check "AGENTS.md PhD tem playbook de relatórios" "OK" || \
  check "AGENTS.md PhD tem playbook de relatórios" "FAIL"

echo ""
echo "--- setup.sh patches PHD-1 ---"
SETUP="$REPO_DIR/install/setup.sh"
grep -q 'cfo-analise-estrategica\|_CFO_SKILLS' "$SETUP" && \
  check "setup.sh instala skills CFO PhD" "OK" || \
  check "setup.sh instala skills CFO PhD" "FAIL"
grep -q 'AGENTS.md PhD\|templates/AGENTS.md\|AGENTS_PHD' "$SETUP" && \
  check "setup.sh aplica template AGENTS.md" "OK" || \
  check "setup.sh aplica template AGENTS.md" "FAIL"
grep -q 'mkdir.*memory\|agente-cfo/memory' "$SETUP" && \
  check "setup.sh cria diretório de memória" "OK" || \
  check "setup.sh cria diretório de memória" "FAIL"
bash -n "$SETUP" 2>/dev/null && \
  check "setup.sh sintaxe bash OK" "OK" || \
  check "setup.sh sintaxe bash OK" "FAIL"

echo ""
echo "--- Docs ---"
[[ -f "$REPO_DIR/docs/MARCOS-PHD.md" ]] && \
  check "docs/MARCOS-PHD.md existe" "OK" || \
  check "docs/MARCOS-PHD.md existe" "FAIL"
grep -q "Discovery Proativo\|7 Skills\|KPIs que Marcos" "$REPO_DIR/docs/MARCOS-PHD.md" 2>/dev/null && \
  check "docs/MARCOS-PHD.md tem conteúdo completo" "OK" || \
  check "docs/MARCOS-PHD.md tem conteúdo completo" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
