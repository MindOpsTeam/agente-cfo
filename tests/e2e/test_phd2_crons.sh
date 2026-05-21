#!/usr/bin/env bash
# test_phd2_crons.sh — Smoke test dos scripts proativos PHD-2.
# Verifica existência, sintaxe bash e conteúdo dos 4 scripts de ronda + snapshot.
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

SCRIPTS="$REPO_DIR/skills/agente-cfo/scripts"

echo "=== Smoke Test: Sprint PHD-2 — Crons Proativos ==="
echo ""

echo "--- snapshot_financeiro.py ---"
SNAP="$SCRIPTS/snapshot_financeiro.py"
[[ -f "$SNAP" ]] && check "snapshot_financeiro.py existe" "OK" || check "snapshot_financeiro.py existe" "FAIL"
[[ -f "$SNAP" ]] && $PYTHON -c "import ast; ast.parse(open('$SNAP').read())" 2>/dev/null && \
  check "snapshot_financeiro.py sintaxe Python OK" "OK" || \
  check "snapshot_financeiro.py sintaxe Python OK" "FAIL"
[[ -f "$SNAP" ]] && grep -q '\-\-get\|\-\-set\|\-\-diff\|\-\-update-now' "$SNAP" && \
  check "snapshot_financeiro.py tem todos os modos (--get/--set/--diff/--update-now)" "OK" || \
  check "snapshot_financeiro.py tem todos os modos (--get/--set/--diff/--update-now)" "FAIL"

echo ""
echo "--- ronda_matinal.sh ---"
RONDA_M="$SCRIPTS/ronda_matinal.sh"
[[ -f "$RONDA_M" ]] && check "ronda_matinal.sh existe" "OK" || check "ronda_matinal.sh existe" "FAIL"
[[ -f "$RONDA_M" ]] && bash -n "$RONDA_M" 2>/dev/null && \
  check "ronda_matinal.sh sintaxe bash OK" "OK" || check "ronda_matinal.sh sintaxe bash OK" "FAIL"
[[ -f "$RONDA_M" ]] && grep -q 'snapshot_financeiro\|zscore\|kpis\|aging' "$RONDA_M" && \
  check "ronda_matinal.sh usa skills PHD" "OK" || check "ronda_matinal.sh usa skills PHD" "FAIL"
[[ -f "$RONDA_M" ]] && grep -q 'RUNWAY_CRIT\|runway.*7\|🚨\|URGENTE' "$RONDA_M" && \
  check "ronda_matinal.sh detecta runway crítico" "OK" || \
  check "ronda_matinal.sh detecta runway crítico" "FAIL"
[[ -f "$RONDA_M" ]] && grep -q 'send_msg\|panel_post_reply\|WA_INSTANCE' "$RONDA_M" && \
  check "ronda_matinal.sh tem lógica de envio multi-canal" "OK" || \
  check "ronda_matinal.sh tem lógica de envio multi-canal" "FAIL"
[[ -f "$RONDA_M" ]] && grep -q '\-\-dry-run\|DRY_RUN' "$RONDA_M" && \
  check "ronda_matinal.sh suporta --dry-run" "OK" || \
  check "ronda_matinal.sh suporta --dry-run" "FAIL"

echo ""
echo "--- ronda_vespertina.sh ---"
RONDA_V="$SCRIPTS/ronda_vespertina.sh"
[[ -f "$RONDA_V" ]] && check "ronda_vespertina.sh existe" "OK" || check "ronda_vespertina.sh existe" "FAIL"
[[ -f "$RONDA_V" ]] && bash -n "$RONDA_V" 2>/dev/null && \
  check "ronda_vespertina.sh sintaxe bash OK" "OK" || check "ronda_vespertina.sh sintaxe bash OK" "FAIL"
[[ -f "$RONDA_V" ]] && grep -q 'SHOULD_SEND=0\|silencia\|silenciando' "$RONDA_V" && \
  check "ronda_vespertina.sh silencia quando sem anomalia" "OK" || \
  check "ronda_vespertina.sh silencia quando sem anomalia" "FAIL"
[[ -f "$RONDA_V" ]] && grep -q 'HAS_ANOMALY\|zscore\|ANOM_COUNT' "$RONDA_V" && \
  check "ronda_vespertina.sh detecta anomalias" "OK" || \
  check "ronda_vespertina.sh detecta anomalias" "FAIL"

echo ""
echo "--- relatorio_semanal.sh ---"
REL_S="$SCRIPTS/relatorio_semanal.sh"
[[ -f "$REL_S" ]] && check "relatorio_semanal.sh existe" "OK" || check "relatorio_semanal.sh existe" "FAIL"
[[ -f "$REL_S" ]] && bash -n "$REL_S" 2>/dev/null && \
  check "relatorio_semanal.sh sintaxe bash OK" "OK" || check "relatorio_semanal.sh sintaxe bash OK" "FAIL"
[[ -f "$REL_S" ]] && grep -q 'relatorio_semanal.py\|panel_reply\|WA_MSG' "$REL_S" && \
  check "relatorio_semanal.sh usa relatorio_semanal.py + painel + WA" "OK" || \
  check "relatorio_semanal.sh usa relatorio_semanal.py + painel + WA" "FAIL"

echo ""
echo "--- relatorio_mensal.sh ---"
REL_M="$SCRIPTS/relatorio_mensal.sh"
[[ -f "$REL_M" ]] && check "relatorio_mensal.sh existe" "OK" || check "relatorio_mensal.sh existe" "FAIL"
[[ -f "$REL_M" ]] && bash -n "$REL_M" 2>/dev/null && \
  check "relatorio_mensal.sh sintaxe bash OK" "OK" || check "relatorio_mensal.sh sintaxe bash OK" "FAIL"
[[ -f "$REL_M" ]] && grep -q 'relatorio_mensal.py\|panel_reply\|WA_MSG' "$REL_M" && \
  check "relatorio_mensal.sh usa relatorio_mensal.py + painel + WA" "OK" || \
  check "relatorio_mensal.sh usa relatorio_mensal.py + painel + WA" "FAIL"

echo ""
echo "--- setup.sh crons PHD-2 ---"
SETUP="$REPO_DIR/install/setup.sh"
grep -q 'CRON_ID_RONDA_MANHA\|ronda.*matinal\|Ronda Matinal PhD' "$SETUP" && \
  check "setup.sh tem cron ronda matinal" "OK" || check "setup.sh tem cron ronda matinal" "FAIL"
grep -q 'CRON_ID_RONDA_TARDE\|ronda.*vespert\|Ronda Vespertina PHP\|Ronda Vespertina' "$SETUP" && \
  check "setup.sh tem cron ronda vespertina" "OK" || check "setup.sh tem cron ronda vespertina" "FAIL"
grep -q 'CRON_ID_REL_SEMANAL\|relatorio-semanal\|Relatório Semanal PhD\|Relat.*Semanal' "$SETUP" && \
  check "setup.sh tem cron relatório semanal" "OK" || check "setup.sh tem cron relatório semanal" "FAIL"
grep -q 'CRON_ID_REL_MENSAL\|relatorio-mensal\|Relatório Mensal PhD\|Relat.*Mensal' "$SETUP" && \
  check "setup.sh tem cron relatório mensal" "OK" || check "setup.sh tem cron relatório mensal" "FAIL"
grep -q '_add_cron_phd2\|warn.*Cron.*não pôde' "$SETUP" && \
  check "setup.sh usa _add_cron_phd2 com fallback warn" "OK" || \
  check "setup.sh usa _add_cron_phd2 com fallback warn" "FAIL"

echo ""
echo "--- conversa.md crons proativos ---"
CONVERSA="$REPO_DIR/skills/agente-cfo/prompts/conversa.md"
grep -q 'Crons Proativos\|ronda-matinal\|relatorio-semanal' "$CONVERSA" && \
  check "conversa.md documenta crons proativos" "OK" || \
  check "conversa.md documenta crons proativos" "FAIL"
grep -q '🚨\|URGENTE\|runway.*7\|Silêncio intencional' "$CONVERSA" && \
  check "conversa.md tem protocolo de emergência + silêncio intencional" "OK" || \
  check "conversa.md tem protocolo de emergência + silêncio intencional" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
