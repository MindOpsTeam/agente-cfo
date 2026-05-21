#!/usr/bin/env bash
# conciliacao_diaria.sh — Roda 4 conciliações cross-sistema às 06:30.
# Se divergência > 0: manda resumo no WA.
# Se zero divergências: SILENCIA (não polui).
# Uso: bash conciliacao_diaria.sh [--dry-run] [--periodo N]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${HOME}/.agente-cfo/logs/conciliacao-diaria.log"

# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

DRY_RUN=0
PERIODO=7
for arg in "${@}"; do
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=1
    [[ "$arg" == "--periodo" ]] && true  # handled below
done
i=1
for arg in "${@}"; do
    [[ "$arg" == "--periodo" && $i -lt $# ]] && PERIODO="${@:$((i+1)):1}"; ((i++)) || true
done

log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" | tee -a "$LOG_FILE" >&2; }
log "conciliacao_diaria.sh iniciada (dry=$DRY_RUN periodo=${PERIODO}d)"

send_msg() {
    local msg="$1"
    local WA_INSTANCE="${EVOLUTION_INSTANCE:-${CFO_WA_INSTANCE:-}}"
    local WA_TO="${CFO_WHATSAPP_TO:-}"
    if [[ -n "$WA_INSTANCE" && -n "$WA_TO" ]]; then
        bash "$SCRIPT_DIR/panel_post_reply.sh" "whatsapp:${WA_INSTANCE}" "$WA_TO" "$msg" "" "" \
            2>>"$LOG_FILE" || log "AVISO: panel_post_reply.sh falhou"
    else
        local RUN_ID="conc_$(date +%s)"
        local THREAD_ID="panel:${INSTANCE_ID:-local}"
        bash "$SCRIPT_DIR/panel_reply.sh" "$THREAD_ID" "$RUN_ID" "$msg" "sent" \
            2>>"$LOG_FILE" || log "AVISO: panel_reply.sh falhou"
    fi
}

run_conciliacao() {
    local skill="$1" script="$2" label="$3"
    local skill_dir="${SKILLS_BASE}/${skill}/scripts/${script}"
    if [[ ! -f "$skill_dir" ]]; then
        echo '{"divergencias": 0, "error": "skill not found"}'
        return
    fi
    python3 "$skill_dir" --periodo "$PERIODO" --format json 2>>"$LOG_FILE" || echo '{}'
}

# ── Roda as 4 conciliações ────────────────────────────────────────────────────
log "Rodando conciliações (período: ${PERIODO}d)..."

COBRANCA_JSON=$(run_conciliacao "cfo-conciliacao-cobranca-erp" "cruzar.py" "Cobrança↔ERP")
ECOM_JSON=$(run_conciliacao "cfo-conciliacao-ecommerce-erp" "cruzar.py" "E-commerce↔ERP")
CRM_JSON=$(run_conciliacao "cfo-conciliacao-crm-erp" "cruzar.py" "CRM↔ERP")
MANUAL_JSON=$(run_conciliacao "cfo-conciliacao-manual-erp" "listar_pendentes.py" "Manual↔ERP")

# ── Extrai divergências ───────────────────────────────────────────────────────
parse_div() {
    echo "$1" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('divergencias') or d.get('total_pendentes') or 0)
except:
    print(0)
" 2>/dev/null || echo "0"
}

DIV_COB=$(parse_div "$COBRANCA_JSON")
DIV_ECOM=$(parse_div "$ECOM_JSON")
DIV_CRM=$(parse_div "$CRM_JSON")
DIV_MAN=$(parse_div "$MANUAL_JSON")

TOTAL_DIV=$(python3 -c "print(int('${DIV_COB:-0}') + int('${DIV_ECOM:-0}') + int('${DIV_CRM:-0}') + int('${DIV_MAN:-0}'))" 2>/dev/null || echo "0")

log "Divergências: cobrança=$DIV_COB ecommerce=$DIV_ECOM crm=$DIV_CRM manual=$DIV_MAN total=$TOTAL_DIV"

# ── Decide se envia ───────────────────────────────────────────────────────────
if [[ "$TOTAL_DIV" -eq 0 ]]; then
    log "Zero divergências — silenciando (design intencional)."
    exit 0
fi

# ── Monta mensagem ────────────────────────────────────────────────────────────
TODAY=$(date '+%d/%m/%Y')
MSG="⚠️ Divergências detectadas — ${TODAY} (últimos ${PERIODO}d)"$'\n'

[[ "$DIV_COB" -gt 0 ]] && MSG+="• Cobrança ↔ ERP: $DIV_COB divergência(s)"$'\n'
[[ "$DIV_ECOM" -gt 0 ]] && MSG+="• E-commerce ↔ ERP: $DIV_ECOM sem nota"$'\n'
[[ "$DIV_CRM" -gt 0 ]] && MSG+="• CRM Deals Won ↔ ERP: $DIV_CRM sem receita"$'\n'
[[ "$DIV_MAN" -gt 0 ]] && MSG+="• Lançamentos manuais pendentes: $DIV_MAN"$'\n'
MSG+="Para detalhes: 'Marcos, mostra as divergências'"

MSG=$(echo "$MSG" | head -c 580)

# ── Envia ─────────────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "=== DRY-RUN: conciliação diária ==="
    echo "$MSG"
    log "dry-run: mensagem exibida sem envio."
    exit 0
fi

send_msg "$MSG"
log "Alerta de conciliação enviado ($TOTAL_DIV divergências)."
