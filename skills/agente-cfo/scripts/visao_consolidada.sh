#!/usr/bin/env bash
# visao_consolidada.sh — Executive summary consolidado do estado financeiro.
#
# Marcos chama quando user diz: "visão geral", "panorama", "como vamos",
# "executive summary", "consolidado", "me passa um resumo completo".
#
# Coleta:
#   1. KPIs financeiros (kpis.py) — saldo, runway, burn, inadimplência
#   2. Estado das integrações (integrations_status.sh)
#   3. Divergências de conciliação rápida (cobrança + manual)
#   4. Próximos eventos do calendário (proximos_eventos.py — 14 dias)
#   5. Variação MoM de receita (analise_horizontal.py)
#
# Output: markdown ~20 linhas + versão WA (~600 chars)
# Uso:
#   bash visao_consolidada.sh                 # markdown pra painel
#   bash visao_consolidada.sh --wa            # versão curta pra WA
#   bash visao_consolidada.sh --format json   # JSON raw pra Marcos processar
#   bash visao_consolidada.sh --dry-run       # sem enviar, só imprimir

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${HOME}/.agente-cfo/logs/visao-consolidada.log"

FORMAT="markdown"
DRY_RUN=0
for arg in "${@}"; do
    case "$arg" in
        --wa|--whatsapp) FORMAT="wa" ;;
        --format)        true ;; # handled by next iteration
        --dry-run)       DRY_RUN=1 ;;
        json)            [[ "${prev_arg:-}" == "--format" ]] && FORMAT="json" ;;
        markdown)        [[ "${prev_arg:-}" == "--format" ]] && FORMAT="markdown" ;;
    esac
    prev_arg="$arg"
done

log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" >> "$LOG_FILE" 2>/dev/null || true; }
log "visao_consolidada.sh iniciada (format=$FORMAT dry=$DRY_RUN)"

PYTHON=/Users/barboza/.npm-global/lib/node_modules/openclaw/.venv/bin/python3
# Tenta venv do repo, senão python3 global
if [[ ! -f "$PYTHON" ]]; then
    PYTHON=$(command -v python3 2>/dev/null || echo "python3")
fi

run_python() {
    local script="$1"; shift
    "$PYTHON" "$script" "$@" 2>/dev/null || echo '{}'
}

run_bash() {
    local script="$1"; shift
    bash "$script" "$@" 2>/dev/null || echo ''
}

# ── 1. KPIs financeiros ───────────────────────────────────────────────────────
KPI_JSON=$(run_python "$SKILLS_BASE/cfo-analise-estrategica/scripts/kpis.py" --format json)
SALDO=$(echo "$KPI_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('balance',0))" 2>/dev/null || echo "0")
RUNWAY=$(echo "$KPI_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('runway_meses',0))" 2>/dev/null || echo "0")
BURN=$(echo "$KPI_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('burn_mensal_estimado',0))" 2>/dev/null || echo "0")
OVERDUE=$(echo "$KPI_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_overdue',0))" 2>/dev/null || echo "0")
INAD_PCT=$(echo "$KPI_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('inadimplencia_pct',0))" 2>/dev/null || echo "0")
REC=$(echo "$KPI_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_receivables_mes',0))" 2>/dev/null || echo "0")
PAY=$(echo "$KPI_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_payables_mes',0))" 2>/dev/null || echo "0")

# ── 2. Integrações ───────────────────────────────────────────────────────────
INTEG_TEXT=$(run_bash "$SCRIPT_DIR/integrations_status.sh" 2>/dev/null | head -5 || echo "Status indisponível")

# ── 3. Conciliação rápida ────────────────────────────────────────────────────
CONC_COB=$(run_python "$SKILLS_BASE/cfo-conciliacao-cobranca-erp/scripts/cruzar.py" --periodo 7 --format json)
DIV_COB=$(echo "$CONC_COB" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('divergencias',0))" 2>/dev/null || echo "0")
DIV_MAN=0
if [[ -f "$SKILLS_BASE/cfo-conciliacao-manual-erp/scripts/listar_pendentes.py" ]]; then
    MAN_JSON=$(run_python "$SKILLS_BASE/cfo-conciliacao-manual-erp/scripts/listar_pendentes.py" --format json)
    DIV_MAN=$(echo "$MAN_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_pendentes',0))" 2>/dev/null || echo "0")
fi
TOTAL_DIV=$((DIV_COB + DIV_MAN))

# ── 4. Próximos eventos (14 dias) ────────────────────────────────────────────
EVENTOS_JSON=$(run_python "$SKILLS_BASE/cfo-calendario-acoes/scripts/proximos_eventos.py" --dias 14 --format json)
PROX_COUNT=$(echo "$EVENTOS_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total',0))" 2>/dev/null || echo "0")
PROX_TOP=$(echo "$EVENTOS_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
evs=d.get('eventos',[])[:3]
for e in evs:
    print(f\"  - {e.get('data','?')[5:]}: {e.get('titulo','?')[:45]}\")
" 2>/dev/null || echo "  - Sem eventos críticos")

# ── 5. Variação MoM ──────────────────────────────────────────────────────────
HORIZ_JSON=$(run_python "$SKILLS_BASE/cfo-analise-estrategica/scripts/analise_horizontal.py" --format json)
DELTA_REC=$(echo "$HORIZ_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
pct=d.get('receitas',{}).get('delta_pct')
if pct is None: print('N/D')
else: print(f\"+{pct:.0f}%\" if pct>=0 else f\"{pct:.0f}%\")
" 2>/dev/null || echo "N/D")

# ── Formata saída ─────────────────────────────────────────────────────────────
TODAY=$(date '+%d/%m/%Y')

brl() {
    python3 -c "v=float('${1:-0}'); print(f'R\$ {v:,.2f}'.replace(',','X').replace('.',',').replace('X','.'))" 2>/dev/null || echo "R\$ 0,00"
}

SALDO_BRL=$(brl "$SALDO")
BURN_BRL=$(brl "$BURN")
OVERDUE_BRL=$(brl "$OVERDUE")
REC_BRL=$(brl "$REC")
PAY_BRL=$(brl "$PAY")
PROJETADO=$(python3 -c "print(round(float('${SALDO:-0}') + float('${REC:-0}') - float('${PAY:-0}'), 2))" 2>/dev/null || echo "0")
PROJ_BRL=$(brl "$PROJETADO")

RUNWAY_SIGNAL="🟢"; [[ $(python3 -c "print(1 if float('${RUNWAY:-99}') < 4 else 0)" 2>/dev/null) -eq 1 ]] && RUNWAY_SIGNAL="🟡"
[[ $(python3 -c "print(1 if float('${RUNWAY:-99}') < 2 else 0)" 2>/dev/null) -eq 1 ]] && RUNWAY_SIGNAL="🔴"
INAD_SIGNAL="🟢"; [[ $(python3 -c "print(1 if float('${INAD_PCT:-0}') > 15 else 0)" 2>/dev/null) -eq 1 ]] && INAD_SIGNAL="🔴"
[[ $(python3 -c "print(1 if float('${INAD_PCT:-0}') > 8 else 0)" 2>/dev/null) -eq 1 ]] && INAD_SIGNAL="🟡"
DIV_SIGNAL="🟢"; [[ "$TOTAL_DIV" -gt 0 ]] && DIV_SIGNAL="🟡"
[[ "$TOTAL_DIV" -gt 5 ]] && DIV_SIGNAL="🔴"

if [[ "$FORMAT" == "json" ]]; then
    python3 - << PYEOF
import json
print(json.dumps({
    "date": "$TODAY",
    "financeiro": {
        "saldo": float("${SALDO:-0}"),
        "runway_meses": float("${RUNWAY:-0}"),
        "burn_mensal": float("${BURN:-0}"),
        "total_overdue": float("${OVERDUE:-0}"),
        "inadimplencia_pct": float("${INAD_PCT:-0}"),
        "receita_mes": float("${REC:-0}"),
        "pagamentos_mes": float("${PAY:-0}"),
        "projetado": float("${PROJETADO:-0}"),
    },
    "conciliacao": {"total_divergencias": int("${TOTAL_DIV:-0}"), "cobranca": int("${DIV_COB:-0}"), "manual": int("${DIV_MAN:-0}")},
    "proximos_eventos_count": int("${PROX_COUNT:-0}"),
    "delta_receita_mom": "${DELTA_REC}",
}, ensure_ascii=False))
PYEOF
    exit 0
fi

if [[ "$FORMAT" == "wa" ]]; then
    echo "📊 Consolidado — $TODAY"
    echo ""
    echo "Caixa: $SALDO_BRL | Runway: $(printf '%.1f' "$RUNWAY")m $RUNWAY_SIGNAL"
    echo "Receber: $REC_BRL | Pagar: $PAY_BRL → Proj: $PROJ_BRL"
    [[ "$OVERDUE" != "0" && "$OVERDUE" != "0.0" ]] && echo "Vencidos: $OVERDUE_BRL $INAD_SIGNAL (${INAD_PCT}%)"
    [[ "$TOTAL_DIV" -gt 0 ]] && echo "Divergências: $TOTAL_DIV $DIV_SIGNAL"
    [[ "$PROX_COUNT" -gt 0 ]] && echo "Próx. $PROX_COUNT eventos (14d)"
    echo "Receita MoM: $DELTA_REC"
    exit 0
fi

# Markdown pra painel
cat << MARKDOWN
## 📊 Visão Consolidada — $TODAY

### 💰 Financeiro
| Métrica | Valor |
|---------|-------|
| Caixa atual | $SALDO_BRL |
| Runway | $(printf '%.1f' "$RUNWAY") meses $RUNWAY_SIGNAL |
| Burn mensal | $BURN_BRL |
| A receber (mês) | $REC_BRL |
| A pagar (mês) | $PAY_BRL |
| Projetado fim do mês | $PROJ_BRL |
| Vencidos (inadimplência) | $OVERDUE_BRL $INAD_SIGNAL (${INAD_PCT}%) |
| Receita vs mês anterior | $DELTA_REC |

### 🔀 Conciliação
$([ "$TOTAL_DIV" -eq 0 ] && echo "✅ Sem divergências detectadas (últimos 7 dias)." || echo "⚠️ $TOTAL_DIV divergência(s): Cobrança↔ERP: $DIV_COB | Manuais pendentes: $DIV_MAN")

### 🔌 Integrações
\`\`\`
$INTEG_TEXT
\`\`\`

### 📅 Próximos eventos (14 dias) — $PROX_COUNT total
$PROX_TOP

---
_Atualizado em $(date '+%d/%m/%Y %H:%M')_
MARKDOWN
