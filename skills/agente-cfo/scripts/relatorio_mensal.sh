#!/usr/bin/env bash
# relatorio_mensal.sh — Relatório executivo mensal (dia 1 às 08h).
#
# Gera relatório mensal completo (DRE + comparativo MoM), posta markdown no painel,
# envia 4 bullets no WA.
# Uso: bash relatorio_mensal.sh [--dry-run] [--mes YYYY-MM]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_BASE="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="${HOME}/.agente-cfo/logs/relatorio-mensal.log"

# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

DRY_RUN=0
MES_ARG=""
i=1
for arg in "${@}"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --mes) MES_ARG="${*:$((i+1)):1}"; break ;;
    esac
    ((i++)) || true
done

log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" | tee -a "$LOG_FILE" >&2; }
log "relatorio_mensal.sh iniciada (dry=$DRY_RUN mes=${MES_ARG:-auto})"

send_canal() {
    local canal="$1" dest="$2" msg="$3"
    local RUN_ID="rel_men_$(date +%s)"
    bash "$SCRIPT_DIR/panel_post_reply.sh" "$canal" "$dest" "$msg" "" "$RUN_ID" \
        2>>"$LOG_FILE" || log "AVISO: panel_post_reply.sh falhou ($canal)"
}

# ── 1. Gera relatório ─────────────────────────────────────────────────────────
log "Gerando relatório mensal..."
MES_OPTS=""
[[ -n "$MES_ARG" ]] && MES_OPTS="--mes $MES_ARG"

REL_JSON=$(python3 "$SKILLS_BASE/cfo-relatorios-executivos/scripts/relatorio_mensal.py" \
    --format json $MES_OPTS 2>>"$LOG_FILE" || echo '{}')
REL_MD=$(python3 "$SKILLS_BASE/cfo-relatorios-executivos/scripts/relatorio_mensal.py" \
    --format markdown $MES_OPTS 2>>"$LOG_FILE" || echo "")

# ── 2. Extrai 4 bullets WA ────────────────────────────────────────────────────
WA_MSG=$(echo "$REL_JSON" | python3 - << 'PYEOF'
import json, sys

try:
    d = json.load(sys.stdin)
except:
    print("📑 Relatório mensal disponível no painel.")
    sys.exit(0)

def brl(v):
    try: return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return "N/D"

def delta_str(pct):
    if pct is None: return ""
    sign = "▲" if pct >= 0 else "▼"
    return f" ({sign}{abs(pct):.0f}% MoM)"

periodo = d.get("periodo", "")
receita = d.get("receita", 0)
resultado = d.get("resultado", 0)
delta_rec = d.get("delta_receita_pct")
overdue = d.get("overdue_total", 0)
runway = d.get("runway_meses", 0)
recs = d.get("recomendacoes") or []

res_signal = "🟢" if resultado >= 0 else "🔴"
runway_s = "🔴" if runway < 2 else ("🟡" if runway < 4 else "🟢")

lines = [
    f"📑 Relatório {periodo}",
    f"Receita: {brl(receita)}{delta_str(delta_rec)}",
    f"Resultado: {brl(resultado)} {res_signal}",
    f"Runway: {runway:.1f}m {runway_s} | Vencidos: {brl(overdue)}",
    "",
]
if recs:
    lines.append("Ações para este mês:")
    for i, r in enumerate(recs[:3], 1):
        lines.append(f"{i}. {r[:90]}")
lines.append("DRE completo: painel → /chat")
print("\n".join(lines))
PYEOF
)

WA_MSG=$(echo "$WA_MSG" | head -c 580)

# ── 3. Posta markdown no painel ───────────────────────────────────────────────
if [[ -n "$REL_MD" && "$DRY_RUN" -eq 0 ]]; then
    INSTANCE_ID="${INSTANCE_ID:-local}"
    THREAD_ID="panel:${INSTANCE_ID}"
    RUN_ID="rel_men_md_$(date +%s)"
    bash "$SCRIPT_DIR/panel_reply.sh" "$THREAD_ID" "$RUN_ID" "$REL_MD" "sent" \
        2>>"$LOG_FILE" || log "AVISO: panel_reply.sh falhou para markdown"
    log "Relatório mensal markdown postado no painel."
fi

# ── 4. Envia WA ───────────────────────────────────────────────────────────────
WA_INSTANCE="${EVOLUTION_INSTANCE:-${CFO_WA_INSTANCE:-}}"
WA_TO="${CFO_WHATSAPP_TO:-}"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "=== DRY-RUN: WA bullets ==="
    echo "$WA_MSG"
    echo ""
    echo "=== DRY-RUN: relatório markdown ==="
    echo "$REL_MD" | head -40
    log "dry-run: sem envio."
    exit 0
fi

if [[ -n "$WA_INSTANCE" && -n "$WA_TO" ]]; then
    send_canal "whatsapp:${WA_INSTANCE}" "$WA_TO" "$WA_MSG"
    log "Bullets mensais enviados ao WA ($WA_TO)."
else
    log "WA não configurado — relatório disponível no painel."
fi

log "relatorio_mensal.sh concluída."
