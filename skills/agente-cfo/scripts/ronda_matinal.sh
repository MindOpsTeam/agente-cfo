#!/usr/bin/env bash
# ronda_matinal.sh — Ronda proativa das 07h.
#
# Coleta saldo, runway, inadimplência e anomalia de despesas.
# Compara com snapshot anterior. Envia resumo curto ao dono via WA/painel.
# Se alguma métrica ultrapassar threshold: envia alerta adicional com ⚠️/🚨.
#
# Uso: bash ronda_matinal.sh [--dry-run]
# Chamado pelo cron "0 7 * * *" via OpenClaw.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${HOME}/.agente-cfo/logs/ronda-matinal.log"

# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" | tee -a "$LOG_FILE" >&2; }
log "ronda_matinal.sh iniciada (dry_run=$DRY_RUN)"

# ── Helpers ────────────────────────────────────────────────────────────────────
fmt_brl() {
    python3 -c "v=float('${1:-0}'); print(f'R$ {v:,.2f}'.replace(',','X').replace('.',',').replace('X','.'))"
}

send_msg() {
    local msg="$1"
    # Canal de destino: WhatsApp (Evolution API) ou fallback painel
    local WA_INSTANCE="${EVOLUTION_INSTANCE:-${CFO_WA_INSTANCE:-}}"
    local WA_TO="${CFO_WHATSAPP_TO:-}"

    if [[ -n "$WA_INSTANCE" && -n "$WA_TO" ]]; then
        bash "$SCRIPT_DIR/panel_post_reply.sh" \
            "whatsapp:${WA_INSTANCE}" "$WA_TO" "$msg" "" "" \
            2>>"$LOG_FILE" || \
            log "AVISO: panel_post_reply.sh falhou (tentando painel)"
    else
        # Fallback: posta só no painel (histórico unificado)
        local INSTANCE_ID="${INSTANCE_ID:-}"
        local THREAD_ID="panel:${INSTANCE_ID:-local}"
        local RUN_ID="ronda_mat_$(date +%s)"
        bash "$SCRIPT_DIR/panel_reply.sh" "$THREAD_ID" "$RUN_ID" "$msg" "sent" \
            2>>"$LOG_FILE" || log "AVISO: panel_reply.sh falhou"
    fi
}

# ── 1. Atualiza snapshot e captura dados ──────────────────────────────────────
SNAP_JSON=$(python3 "$SCRIPT_DIR/snapshot_financeiro.py" --update-now 2>>"$LOG_FILE" || echo '{}')
SNAP=$(echo "$SNAP_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('snapshot',{})))" 2>/dev/null || echo '{}')
DIFF=$(echo "$SNAP_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('diff',{})))" 2>/dev/null || echo '{}')

# Extrai valores do snapshot
extract() { echo "$SNAP" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$1',0))"; }
SALDO=$(extract balance)
RUNWAY=$(extract runway_meses)
BURN=$(extract burn_mensal_estimado)
OVERDUE=$(extract total_overdue)
REC=$(extract total_receivables_mes)
PAY=$(extract total_payables_mes)
INAD_PCT=$(extract inadimplencia_pct)

# ── 2. Z-score de anomalia ────────────────────────────────────────────────────
ZSCORE_JSON=$(python3 "$SKILLS_BASE/cfo-anomalias/scripts/zscore.py" --format json 2>>"$LOG_FILE" || echo '{}')
ZSCORE=$(echo "$ZSCORE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('zscore',0))" 2>/dev/null || echo "0")
HAS_ANOMALY=$(echo "$ZSCORE_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print('1' if d.get('anomalia') else '0')" 2>/dev/null || echo "0")

# ── 3. Projeção saldo ─────────────────────────────────────────────────────────
PROJETADO=$(python3 -c "print(round(float('${SALDO:-0}') + float('${REC:-0}') - float('${PAY:-0}'), 2))" 2>/dev/null || echo "$SALDO")

# ── 4. Variações relevantes do snapshot anterior ─────────────────────────────
SALDO_DELTA=$(echo "$DIFF" | python3 -c "
import json,sys
d=json.load(sys.stdin)
b=d.get('balance',{})
pct=b.get('delta_pct')
if pct is None: print('')
else: print(f'({\"▲\" if pct>=0 else \"▼\"}{abs(pct):.0f}% vs ontem)')
" 2>/dev/null || echo "")

# ── 5. Monta mensagem principal (WA max 600 chars) ────────────────────────────
TODAY=$(date '+%d/%m/%Y')
RUNWAY_SIGNAL="🟢"
[[ $(python3 -c "print(1 if float('${RUNWAY:-99}') < 2 else 0)") -eq 1 ]] && RUNWAY_SIGNAL="🔴"
[[ $(python3 -c "print(1 if float('${RUNWAY:-99}') < 4 else 0)") -eq 1 ]] && RUNWAY_SIGNAL="🟡"

INAD_SIGNAL="🟢"
[[ $(python3 -c "print(1 if float('${INAD_PCT:-0}') > 15 else 0)") -eq 1 ]] && INAD_SIGNAL="🔴"
[[ $(python3 -c "print(1 if float('${INAD_PCT:-0}') > 8 else 0)") -eq 1 ]] && INAD_SIGNAL="🟡"

MSG_PRINCIPAL=$(python3 -c "
import sys
saldo = float('${SALDO:-0}')
runway = float('${RUNWAY:-99}')
burn = float('${BURN:-0}')
rec = float('${REC:-0}')
pay = float('${PAY:-0}')
overdue = float('${OVERDUE:-0}')
inad = float('${INAD_PCT:-0}')
projetado = float('${PROJETADO:-0}')
delta = '${SALDO_DELTA:-}'
runway_s = '${RUNWAY_SIGNAL}'
inad_s = '${INAD_SIGNAL}'

def brl(v): return f'R\$ {v:,.2f}'.replace(',','X').replace('.',',').replace('X','.')

lines = [
    f'📊 Bom dia — {\"${TODAY}\"}',
    f'Caixa: {brl(saldo)} {delta}  ({runway:.1f}m runway {runway_s})',
    f'Receber mês: {brl(rec)} | Pagar mês: {brl(pay)}',
    f'Projetado: {brl(projetado)}',
]
if overdue > 0:
    lines.append(f'Vencidos: {brl(overdue)} {inad_s} ({inad:.0f}% inadimplência)')
print('\n'.join(lines))
" 2>/dev/null || echo "📊 Bom dia — $TODAY. Dados do ERP indisponíveis.")

# ── 6. Monta alerta separado se thresholds ultrapassados ──────────────────────
ALERT_MSG=""

# Runway < 7 dias = emergência
RUNWAY_CRIT=$(python3 -c "print(1 if float('${RUNWAY:-99}') < 0.25 else 0)" 2>/dev/null || echo "0")
# Runway < 60 dias = atenção
RUNWAY_WARN=$(python3 -c "print(1 if float('${RUNWAY:-99}') < 2 else 0)" 2>/dev/null || echo "0")
# Inadimplência > 20% receivables
INAD_CRIT=$(python3 -c "print(1 if float('${INAD_PCT:-0}') > 20 else 0)" 2>/dev/null || echo "0")
# Z-score > 2σ
ZSCORE_CRIT=$(python3 -c "print(1 if abs(float('${ZSCORE:-0}')) > 2 else 0)" 2>/dev/null || echo "0")

if [[ "$RUNWAY_CRIT" -eq 1 ]]; then
    ALERT_MSG="🚨 URGENTE: Runway de $(printf '%.1f' "$RUNWAY") meses. O caixa pode zerar em DIAS. Ação imediata necessária."
elif [[ "$RUNWAY_WARN" -eq 1 ]]; then
    ALERT_MSG="⚠️ Runway baixo: $(printf '%.1f' "$RUNWAY") meses (burn $(python3 -c "print(f'R\$ {float(\"${BURN:-0}\"):,.2f}'.replace(',','X').replace('.',',').replace('X','.'))" 2>/dev/null)/mês). Revisar custos."
fi

if [[ "$INAD_CRIT" -eq 1 && -z "$ALERT_MSG" ]]; then
    ALERT_MSG="⚠️ Inadimplência crítica: ${INAD_PCT}% das receitas vencidas. Executar campanha de cobrança."
fi

if [[ "$ZSCORE_CRIT" -eq 1 && -z "$ALERT_MSG" ]]; then
    ALERT_MSG="⚠️ Anomalia de despesas detectada (z=$(printf '%.1f' "$ZSCORE")σ). Verificar qual categoria está fora do padrão."
fi

# ── 7. Envia ──────────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "=== DRY-RUN: mensagem principal ==="
    echo "$MSG_PRINCIPAL"
    [[ -n "$ALERT_MSG" ]] && echo "" && echo "=== ALERTA ===" && echo "$ALERT_MSG"
    echo ""
    log "dry-run: mensagens exibidas sem envio."
    exit 0
fi

log "Enviando ronda matinal..."
send_msg "$MSG_PRINCIPAL"
log "Mensagem principal enviada."

if [[ -n "$ALERT_MSG" ]]; then
    sleep 2
    send_msg "$ALERT_MSG"
    log "Alerta enviado: $ALERT_MSG"
fi

log "ronda_matinal.sh concluída."
