#!/usr/bin/env bash
# check-budget.sh — Estima custo LLM mensal e pausa crons se exceder LLM_BUDGET_BRL
# Reporta uso para /llm-usage e evento budget_exceeded para /event quando necessário.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

: "${LLM_BUDGET_BRL:?missing — defina LLM_BUDGET_BRL no ambiente (ex: 50)}"

LOG_FILE="$LOG_DIR/check-budget.log"
STATE_FILE="$STATE_DIR/budget-state.json"
CRON_IDS_FILE="$STATE_DIR/cron-ids.env"

LLM_INPUT_PRICE_BRL="${LLM_INPUT_PRICE_BRL:-9.50}"
LLM_OUTPUT_PRICE_BRL="${LLM_OUTPUT_PRICE_BRL:-47.50}"
LLM_MODEL="${LLM_MODEL:-anthropic/claude-sonnet-4-6}"

SESSIONS_DIR="$HOME/.openclaw/agents/main/sessions"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
MES_ATUAL=$(date '+%Y-%m')

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== check-budget.sh iniciado em $TIMESTAMP ==="

# ── Parsear tokens dos JSONL de sessões ───────────────────────────────────────
calcular_tokens_mes() {
    local mes="$1"
    local input_tokens=0
    local output_tokens=0

    if [[ ! -d "$SESSIONS_DIR" ]]; then
        echo "0 0 unknown"
        return
    fi

    # Coleta de tokens e session IDs; retorna totais + lista de sessions
    while IFS= read -r -d '' jsonl_file; do
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            read -r in_tok out_tok <<< "$(echo "$line" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    ts = d.get('timestamp','') or d.get('created_at','') or d.get('ts','')
    if not ts.startswith('$mes'):
        print(0, 0)
        sys.exit()
    usage = d.get('usage', {}) or d.get('response', {}).get('usage', {}) or {}
    i = usage.get('inputTokens', usage.get('input_tokens', 0)) or 0
    o = usage.get('outputTokens', usage.get('output_tokens', 0)) or 0
    print(i, o)
except:
    print(0, 0)
" 2>/dev/null || echo "0 0")"
            input_tokens=$((input_tokens + in_tok))
            output_tokens=$((output_tokens + out_tok))
        done < "$jsonl_file"
    done < <(find "$SESSIONS_DIR" -name "*.jsonl" -print0 2>/dev/null)

    echo "$input_tokens $output_tokens"
}

# ── Calcular custo ────────────────────────────────────────────────────────────
echo "Calculando uso de tokens para o mês: $MES_ATUAL..."
read -r INPUT_TOKENS OUTPUT_TOKENS <<< "$(calcular_tokens_mes "$MES_ATUAL")"

CUSTO_BRL=$(python3 -c "
i = $INPUT_TOKENS; o = $OUTPUT_TOKENS
custo = (i / 1_000_000 * $LLM_INPUT_PRICE_BRL) + (o / 1_000_000 * $LLM_OUTPUT_PRICE_BRL)
print(f'{custo:.2f}')
" 2>/dev/null || echo "0.00")

EXCEDEU=$(python3 -c "print('yes' if float('$CUSTO_BRL') > float('$LLM_BUDGET_BRL') else 'no')")

echo "Input tokens (mês): $INPUT_TOKENS"
echo "Output tokens (mês): $OUTPUT_TOKENS"
echo "Custo estimado: R\$ $CUSTO_BRL"
echo "Orçamento mensal: R\$ $LLM_BUDGET_BRL"
echo "Excedeu: $EXCEDEU"

# ── Salvar estado local ───────────────────────────────────────────────────────
cat > "$STATE_FILE" << EOF
{
  "mes": "$MES_ATUAL",
  "input_tokens": $INPUT_TOKENS,
  "output_tokens": $OUTPUT_TOKENS,
  "custo_brl": $CUSTO_BRL,
  "budget_brl": $LLM_BUDGET_BRL,
  "excedeu": $([ "$EXCEDEU" = "yes" ] && echo "true" || echo "false"),
  "updated_at": "$TIMESTAMP"
}
EOF

# ── Reportar uso ao painel (/llm-usage) ──────────────────────────────────────
# Usa "budget-check" como session_id agregado (não é uma sessão real, é o total do mês)
_panel_llm_usage \
    "budget-check-${MES_ATUAL}" \
    "$LLM_MODEL" \
    "$INPUT_TOKENS" \
    "$OUTPUT_TOKENS" \
    "$CUSTO_BRL" \
    "$MES_ATUAL"

# ── Ação: pausar crons se excedeu ─────────────────────────────────────────────
if [[ "$EXCEDEU" == "yes" ]]; then
    echo ""
    echo "⚠️ ORÇAMENTO EXCEDIDO! Pausando cron jobs de alerta..."

    if [[ -f "$CRON_IDS_FILE" ]]; then
        # shellcheck source=/dev/null
        source "$CRON_IDS_FILE"
        for VAR in CRON_ID_MANHA CRON_ID_TARDE; do
            if [[ -n "${!VAR:-}" ]]; then
                echo "Desabilitando cron: ${!VAR}..."
                openclaw cron disable "${!VAR}" 2>/dev/null && \
                    echo "✅ Cron ${!VAR} pausado." || \
                    echo "⚠️ Falha ao pausar cron ${!VAR}."
            fi
        done
    else
        echo "AVISO: $CRON_IDS_FILE não encontrado — pause manualmente via openclaw cron disable <id>"
    fi

    # Notificar via WhatsApp
    if [[ -n "${CFO_WHATSAPP_TO:-}" ]]; then
        MSG="⚠️ Agente CFO pausado: orçamento mensal de R\$ $LLM_BUDGET_BRL atingido (gasto: R\$ $CUSTO_BRL). Alertas desativados."
        wacli send text --to "$CFO_WHATSAPP_TO" --message "$MSG" 2>/dev/null || \
            echo "AVISO: falha ao enviar alerta WhatsApp de budget"
    fi

    # Reportar evento crítico ao painel
    _panel_event "llm_budget_exceeded" "critical" \
        "{\"custo_brl\":$CUSTO_BRL,\"budget_brl\":$LLM_BUDGET_BRL,\"mes\":\"$MES_ATUAL\",\"input_tokens\":$INPUT_TOKENS,\"output_tokens\":$OUTPUT_TOKENS}"

else
    PCT=$(python3 -c "print(f'{float(\"$CUSTO_BRL\")/float(\"$LLM_BUDGET_BRL\")*100:.1f}')")
    echo "✅ Dentro do orçamento ($PCT% utilizado)."

    # Reativar crons se haviam sido pausados (novo mês)
    if [[ -f "$CRON_IDS_FILE" ]]; then
        # shellcheck source=/dev/null
        source "$CRON_IDS_FILE"
        for VAR in CRON_ID_MANHA CRON_ID_TARDE; do
            if [[ -n "${!VAR:-}" ]]; then
                openclaw cron enable "${!VAR}" 2>/dev/null || true
            fi
        done
    fi
fi

echo "=== check-budget.sh encerrado ==="
