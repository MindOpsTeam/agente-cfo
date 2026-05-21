#!/usr/bin/env bash
# test_cfo_consol.sh — Sprint CFO-CONSOL: smoke test de visao_consolidada + alertas
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0; FAIL=0

check() {
  [[ "$2" == "OK" ]] && printf '  ✅ %s\n' "$1" && PASS=$((PASS+1)) && return
  printf '  ❌ %s — %s\n' "$1" "$2"; FAIL=$((FAIL+1))
}

echo "=== Smoke Test: Sprint CFO-CONSOL ==="
echo ""

echo "--- visao_consolidada.sh ---"
VS="$REPO_DIR/skills/agente-cfo/scripts/visao_consolidada.sh"
[[ -f "$VS" ]] && check "visao_consolidada.sh existe" "OK" || check "visao_consolidada.sh existe" "FAIL"
bash -n "$VS" 2>/dev/null && check "visao_consolidada.sh sintaxe bash OK" "OK" || \
  check "visao_consolidada.sh sintaxe bash OK" "FAIL"
grep -q 'kpis.py\|runway.py\|aging.py\|kpis' "$VS" && \
  check "visao_consolidada.sh chama kpis.py" "OK" || \
  check "visao_consolidada.sh chama kpis.py" "FAIL"
grep -q 'integrations_status\|cfo-conciliacao\|proximos_eventos\|analise_horizontal' "$VS" && \
  check "visao_consolidada.sh integra conciliação + calendário + integrações" "OK" || \
  check "visao_consolidada.sh integra conciliação + calendário + integrações" "FAIL"
grep -q '\-\-wa\|WA\|--format.*json\|FORMAT.*json' "$VS" && \
  check "visao_consolidada.sh suporta --wa e --format json" "OK" || \
  check "visao_consolidada.sh suporta --wa e --format json" "FAIL"
grep -q 'Visão Consolidada\|Financeiro\|Conciliação\|Integrações\|Próximos' "$VS" && \
  check "visao_consolidada.sh tem todas as seções markdown" "OK" || \
  check "visao_consolidada.sh tem todas as seções markdown" "FAIL"

echo ""
echo "--- visao_consolidada.sh dry-run (--format json, sem ERP real) ---"
JSON_OUT=$(bash "$VS" --format json 2>/dev/null || echo '{}')
JSON_OK=$(python3 -c "
import json,sys
try:
    d=json.loads('''$JSON_OUT''')
    assert 'financeiro' in d or 'date' in d, 'sem chave financeiro/date'
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
" 2>/dev/null || echo "FAIL")
[[ "$JSON_OK" == "OK" ]] && check "visao_consolidada.sh --format json retorna JSON válido" "OK" || \
  check "visao_consolidada.sh --format json retorna JSON válido" "FAIL — $JSON_OK"

echo ""
echo "--- alertas_templates.md ---"
AT="$REPO_DIR/skills/agente-cfo/identity/alertas_templates.md"
[[ -f "$AT" ]] && check "alertas_templates.md existe" "OK" || check "alertas_templates.md existe" "FAIL"
TEMPLATE_COUNT=$(grep -c "^### [0-9]" "$AT" 2>/dev/null || echo "0")
[[ "$TEMPLATE_COUNT" -ge 10 ]] && check "alertas_templates.md tem ≥10 templates" "OK" || \
  check "alertas_templates.md tem ≥10 templates (got $TEMPLATE_COUNT)" "FAIL"
grep -q 'cfo_runway_low\|cfo_cash_low\|cfo_overdue' "$AT" && \
  check "alertas_templates.md tem tipos cfo_* definidos" "OK" || \
  check "alertas_templates.md tem tipos cfo_* definidos" "FAIL"
grep -q 'channels.*whatsapp\|whatsapp.*painel\|Canais' "$AT" && \
  check "alertas_templates.md define canais por template" "OK" || \
  check "alertas_templates.md define canais por template" "FAIL"

echo ""
echo "--- docs/SPRINT-CFO-CONSOL-LOVABLE.md ---"
LP="$REPO_DIR/docs/SPRINT-CFO-CONSOL-LOVABLE.md"
[[ -f "$LP" ]] && check "SPRINT-CFO-CONSOL-LOVABLE.md existe" "OK" || \
  check "SPRINT-CFO-CONSOL-LOVABLE.md existe" "FAIL"
grep -q 'ALERT_TEMPLATES\|alertas sugeridos\|Ativar' "$LP" && \
  check "Lovable prompt tem templates de alertas clicáveis" "OK" || \
  check "Lovable prompt tem templates de alertas clicáveis" "FAIL"

echo ""
echo "--- conversa.md tem intent visão consolidada ---"
CONV="$REPO_DIR/skills/agente-cfo/prompts/conversa.md"
grep -q 'visão geral\|panorama\|executive summary\|consolidado\|visao_consolidada' "$CONV" && \
  check "conversa.md tem intent visão consolidada" "OK" || \
  check "conversa.md tem intent visão consolidada" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
