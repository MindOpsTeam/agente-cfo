#!/usr/bin/env bash
# relatorio_semanal.sh — Relatório executivo de sexta 16h.
#
# Gera relatório semanal completo, posta no painel, envia resumo 3-bullets no WA.
# Uso: bash relatorio_semanal.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${HOME}/.agente-cfo/logs/relatorio-semanal.log"

# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" | tee -a "$LOG_FILE" >&2; }
log "relatorio_semanal.sh iniciada (dry=$DRY_RUN)"

send_canal() {
    local canal="$1" dest="$2" msg="$3"
    local RUN_ID="rel_sem_$(date +%s)"
    bash "$SCRIPT_DIR/panel_post_reply.sh" "$canal" "$dest" "$msg" "" "$RUN_ID" \
        2>>"$LOG_FILE" || log "AVISO: panel_post_reply.sh falhou ($canal)"
}

# ── 1. Gera relatório completo ────────────────────────────────────────────────
log "Gerando relatório semanal..."
REL_JSON=$(python3 "$SKILLS_BASE/cfo-relatorios-executivos/scripts/relatorio_semanal.py" \
    --format json 2>>"$LOG_FILE" || echo '{}')
REL_TEXT=$(python3 "$SKILLS_BASE/cfo-relatorios-executivos/scripts/relatorio_semanal.py" \
    --format text 2>>"$LOG_FILE" || echo "Relatório indisponível")
REL_MD=$(python3 "$SKILLS_BASE/cfo-relatorios-executivos/scripts/relatorio_semanal.py" \
    --format markdown 2>>"$LOG_FILE" || echo "")

# ── 2. Extrai bullets para o WA ───────────────────────────────────────────────
WA_MSG=$(echo "$REL_JSON" | python3 - << 'PYEOF'
import json, sys

try:
    d = json.load(sys.stdin)
except:
    print("📑 Relatório semanal no painel.")
    sys.exit(0)

def brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except:
        return "N/D"

caixa = d.get("caixa", 0)
runway = d.get("runway_meses", 0)
overdue = d.get("overdue_total", 0)
rec = d.get("recebimentos_semana", 0)
pay = d.get("pagamentos_semana", 0)
saldo_sem = rec - pay
recs = d.get("recomendacoes") or []

runway_s = "🔴" if runway < 2 else ("🟡" if runway < 4 else "🟢")
lines = [
    f"📑 Relatório Semanal — {d.get('periodo','').split(' a ')[0] if d.get('periodo') else ''}",
    f"Semana: +{brl(rec)} / -{brl(pay)} = {'+' if saldo_sem >= 0 else ''}{brl(saldo_sem)}",
    f"Caixa: {brl(caixa)} | Runway: {runway:.1f}m {runway_s}",
]
if overdue > 0:
    lines.append(f"Vencidos: {brl(overdue)}")
lines.append("")
if recs:
    lines.append("Top recomendações:")
    for i, r in enumerate(recs[:3], 1):
        lines.append(f"{i}. {r[:100]}")
lines.append("Relatório completo: painel → /chat")
print("\n".join(lines))
PYEOF
)

# Trunca pra 580 chars
WA_MSG=$(echo "$WA_MSG" | head -c 580)

# ── 3. Posta relatório completo no painel ─────────────────────────────────────
if [[ -n "$REL_MD" ]]; then
    INSTANCE_ID="${INSTANCE_ID:-local}"
    THREAD_ID="panel:${INSTANCE_ID}"
    RUN_ID="rel_sem_md_$(date +%s)"
    if [[ "$DRY_RUN" -eq 0 ]]; then
        bash "$SCRIPT_DIR/panel_reply.sh" "$THREAD_ID" "$RUN_ID" "$REL_MD" "sent" \
            2>>"$LOG_FILE" || log "AVISO: panel_reply.sh falhou para markdown"
        log "Relatório markdown postado no painel."
    fi
fi

# ── 4. Envia resumo no WA ─────────────────────────────────────────────────────
WA_INSTANCE="${EVOLUTION_INSTANCE:-${CFO_WA_INSTANCE:-}}"
WA_TO="${CFO_WHATSAPP_TO:-}"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "=== DRY-RUN: WA resumo ==="
    echo "$WA_MSG"
    echo ""
    echo "=== DRY-RUN: relatório texto ==="
    echo "$REL_TEXT"
    log "dry-run: mensagens exibidas sem envio."
    exit 0
fi

if [[ -n "$WA_INSTANCE" && -n "$WA_TO" ]]; then
    send_canal "whatsapp:${WA_INSTANCE}" "$WA_TO" "$WA_MSG"
    log "Resumo semanal enviado ao WA ($WA_TO)."
else
    log "WA não configurado — relatório disponível apenas no painel."
fi

log "relatorio_semanal.sh concluída."
