#!/usr/bin/env bash
# ronda_vespertina.sh — Ronda proativa das 18h.
#
# Foca em ANOMALIAS do dia: novos vencidos, despesas atípicas, variação de vendas.
# Se nada relevante: SILENCIA (não polua o WA com "nada novo hoje").
# Se houver anomalia: envia relatório curto.
#
# Uso: bash ronda_vespertina.sh [--dry-run] [--force]
# --force: envia mesmo sem anomalia (útil para testar)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${HOME}/.agente-cfo/logs/ronda-vespertina.log"

# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

DRY_RUN=0
FORCE=0
for arg in "${@}"; do
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=1
    [[ "$arg" == "--force" ]] && FORCE=1
done

log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" | tee -a "$LOG_FILE" >&2; }
log "ronda_vespertina.sh iniciada (dry=$DRY_RUN force=$FORCE)"

send_msg() {
    local msg="$1"
    local WA_INSTANCE="${EVOLUTION_INSTANCE:-${CFO_WA_INSTANCE:-}}"
    local WA_TO="${CFO_WHATSAPP_TO:-}"
    if [[ -n "$WA_INSTANCE" && -n "$WA_TO" ]]; then
        bash "$SCRIPT_DIR/panel_post_reply.sh" "whatsapp:${WA_INSTANCE}" "$WA_TO" "$msg" "" "" \
            2>>"$LOG_FILE" || log "AVISO: panel_post_reply.sh falhou"
    else
        local RUN_ID="ronda_vesp_$(date +%s)"
        local THREAD_ID="panel:${INSTANCE_ID:-local}"
        bash "$SCRIPT_DIR/panel_reply.sh" "$THREAD_ID" "$RUN_ID" "$msg" "sent" \
            2>>"$LOG_FILE" || log "AVISO: panel_reply.sh falhou"
    fi
}

# ── 1. Detecta anomalias do dia ────────────────────────────────────────────────
ZSCORE_JSON=$(python3 "$SKILLS_BASE/cfo-anomalias/scripts/zscore.py" --format json 2>>"$LOG_FILE" || echo '{}')
HAS_ANOMALY=$(echo "$ZSCORE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('anomalia') else '0')" 2>/dev/null || echo "0")
ZSCORE=$(echo "$ZSCORE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('zscore',0))" 2>/dev/null || echo "0")

# Detecta variação de categoria
ANOM_CAT=$(python3 "$SKILLS_BASE/cfo-anomalias/scripts/anomalia_categoria.py" --format json 2>>"$LOG_FILE" || echo '{}')
ANOM_COUNT=$(echo "$ANOM_CAT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(len(d.get('anomalias',[])))
except:
    print(0)
" 2>/dev/null || echo "0")

# Novos vencidos hoje
TODAY_ISO=$(date '+%Y-%m-%d')
OVERDUE_JSON=$(python3 "$SCRIPT_DIR/erp_gateway.py" list_overdue 2>>"$LOG_FILE" || echo '{}')
OVERDUE_TOTAL=$(echo "$OVERDUE_JSON" | python3 -c "
import json,sys
try:
    r=json.load(sys.stdin)
    lst=r.get('records') or r.get('items') or r.get('data') or []
    print(sum(float(x.get('amount_brl') or x.get('amount') or 0) for x in lst if isinstance(x,dict)))
except:
    print(0)
" 2>/dev/null || echo "0")

# ── 2. Decide se envia ────────────────────────────────────────────────────────
SHOULD_SEND=0
ALERTS=()

if [[ "$HAS_ANOMALY" -eq 1 ]]; then
    SHOULD_SEND=1
    ALERTS+=("⚠️ Despesas fora do padrão: z=$(printf '%.1f' "$ZSCORE")σ vs histórico 3m.")
fi

if [[ "$ANOM_COUNT" -gt 0 ]]; then
    SHOULD_SEND=1
    # Pega top anomalia
    TOP_ANOM=$(echo "$ANOM_CAT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
a=sorted(d.get('anomalias',[]),key=lambda x:abs(x.get('delta_pct',0)),reverse=True)
if a:
    x=a[0]
    pct=x.get('delta_pct',0)
    print(f'{x[\"categoria\"]}: {\"▲\" if pct>=0 else \"▼\"}{abs(pct):.0f}% MoM')
" 2>/dev/null || echo "")
    [[ -n "$TOP_ANOM" ]] && ALERTS+=("🔍 $TOP_ANOM")
fi

if [[ "$FORCE" -eq 1 ]]; then
    SHOULD_SEND=1
fi

# Se nada relevante: silencia
if [[ "$SHOULD_SEND" -eq 0 ]]; then
    log "Sem anomalias relevantes — silenciando (design intencional)."
    exit 0
fi

# ── 3. Monta mensagem ─────────────────────────────────────────────────────────
TODAY_FMT=$(date '+%d/%m/%Y')
OVERDUE_FMT=$(python3 -c "v=float('${OVERDUE_TOTAL:-0}'); print(f'R\$ {v:,.2f}'.replace(',','X').replace('.',',').replace('X','.'))" 2>/dev/null || echo "N/D")

MSG=$(python3 - << PYEOF
alerts = ${#ALERTS[@]}
lines = ["📊 Ronda Vespertina — $TODAY_FMT"]
PYEOF
)

# Monta mensagem via bash
MSG="📊 Ronda Vespertina — $TODAY_FMT"$'\n'
for alert in "${ALERTS[@]}"; do
    MSG+="$alert"$'\n'
done
if [[ "$OVERDUE_TOTAL" != "0" && "$OVERDUE_TOTAL" != "0.0" ]]; then
    MSG+="Vencidos total: $OVERDUE_FMT"$'\n'
fi
MSG+="Ver detalhes: painel → /chat"

# Trunca pra 600 chars
MSG=$(echo "$MSG" | head -c 580)

# ── 4. Envia ──────────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "=== DRY-RUN: vespertina ==="
    echo "$MSG"
    log "dry-run: mensagem exibida sem envio."
    exit 0
fi

send_msg "$MSG"
log "ronda_vespertina.sh: alertas enviados (${#ALERTS[@]} anomalias)."
