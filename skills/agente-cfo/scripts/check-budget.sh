#!/usr/bin/env bash
# check-budget.sh — Estima custo LLM mensal e pausa crons se exceder LLM_BUDGET_BRL
# Parseia ~/.openclaw/agents/main/sessions/*.jsonl somando inputTokens + outputTokens
# Preços padrão: Claude Sonnet 4.6 (ajuste LLM_INPUT_PRICE_BRL e LLM_OUTPUT_PRICE_BRL)
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
: "${LLM_BUDGET_BRL:?missing — defina LLM_BUDGET_BRL no ambiente (ex: 50)}"

LOG_DIR="${CFO_LOG_DIR:-$HOME/.agente-cfo/logs}"
STATE_DIR="${CFO_STATE_DIR:-$HOME/.agente-cfo}"
LOG_FILE="$LOG_DIR/check-budget.log"
STATE_FILE="$STATE_DIR/budget-state.json"
CRON_IDS_FILE="$STATE_DIR/cron-ids.env"

# Preço por 1M tokens em BRL (Claude Sonnet 4.6 aproximado)
# Ajuste se usar outro modelo ou se a taxa de câmbio mudar significativamente
LLM_INPUT_PRICE_BRL="${LLM_INPUT_PRICE_BRL:-9.50}"    # ~$3/M tokens * ~3.17 BRL/USD
LLM_OUTPUT_PRICE_BRL="${LLM_OUTPUT_PRICE_BRL:-47.50}"  # ~$15/M tokens * ~3.17 BRL/USD

SESSIONS_DIR="$HOME/.openclaw/agents/main/sessions"

mkdir -p "$LOG_DIR" "$STATE_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
MES_ATUAL=$(date '+%Y-%m')

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== check-budget.sh iniciado em $TIMESTAMP ==="

# ── Função: parsear tokens dos JSONL de sessões ───────────────────────────────
calcular_tokens_mes() {
    local mes="$1"
    local input_tokens=0
    local output_tokens=0

    if [[ ! -d "$SESSIONS_DIR" ]]; then
        echo "AVISO: diretório de sessões não encontrado: $SESSIONS_DIR" >&2
        echo "0 0"
        return
    fi

    # Percorrer todos os arquivos JSONL do mês atual
    while IFS= read -r -d '' jsonl_file; do
        # Extrair apenas linhas do mês atual (baseado no campo timestamp ou created_at)
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue

            # Tentar extrair tokens (estrutura OpenClaw: usage.inputTokens / usage.outputTokens)
            in_tok=$(echo "$line" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    # Verificar se é do mês atual pelo timestamp
    ts = d.get('timestamp','') or d.get('created_at','') or d.get('ts','')
    if not ts.startswith('$mes'):
        print(0)
        sys.exit()
    usage = d.get('usage', {}) or d.get('response', {}).get('usage', {}) or {}
    print(usage.get('inputTokens', usage.get('input_tokens', 0)) or 0)
except:
    print(0)
" 2>/dev/null || echo 0)

            out_tok=$(echo "$line" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    ts = d.get('timestamp','') or d.get('created_at','') or d.get('ts','')
    if not ts.startswith('$mes'):
        print(0)
        sys.exit()
    usage = d.get('usage', {}) or d.get('response', {}).get('usage', {}) or {}
    print(usage.get('outputTokens', usage.get('output_tokens', 0)) or 0)
except:
    print(0)
" 2>/dev/null || echo 0)

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
input_tokens = $INPUT_TOKENS
output_tokens = $OUTPUT_TOKENS
input_price = $LLM_INPUT_PRICE_BRL
output_price = $LLM_OUTPUT_PRICE_BRL
custo = (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
print(f'{custo:.2f}')
" 2>/dev/null || echo "0.00")

BUDGET_FLOAT=$(python3 -c "print(float('$LLM_BUDGET_BRL'))")
CUSTO_FLOAT=$(python3 -c "print(float('$CUSTO_BRL'))")
EXCEDEU=$(python3 -c "print('yes' if float('$CUSTO_BRL') > float('$LLM_BUDGET_BRL') else 'no')")

echo "Input tokens (mês): $INPUT_TOKENS"
echo "Output tokens (mês): $OUTPUT_TOKENS"
echo "Custo estimado: R\$ $CUSTO_BRL"
echo "Orçamento mensal: R\$ $LLM_BUDGET_BRL"
echo "Excedeu: $EXCEDEU"

# ── Salvar estado ─────────────────────────────────────────────────────────────
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
                if openclaw cron disable "${!VAR}" 2>/dev/null; then
                    echo "✅ Cron ${!VAR} pausado."
                else
                    echo "⚠️ Falha ao pausar cron ${!VAR} (pode já estar desabilitado)."
                fi
            fi
        done
    else
        echo "AVISO: $CRON_IDS_FILE não encontrado — crons não puderam ser pausados automaticamente."
        echo "Execute manualmente: openclaw cron list && openclaw cron disable <id>"
    fi

    # Notificar via WhatsApp se disponível
    if [[ -n "${CFO_WHATSAPP_TO:-}" ]]; then
        MSG="⚠️ Agente CFO pausado: orçamento mensal de R\$ $LLM_BUDGET_BRL atingido (gasto: R\$ $CUSTO_BRL). Alertas desativados até o próximo mês ou reativação manual."
        wacli send text --to "$CFO_WHATSAPP_TO" --message "$MSG" 2>/dev/null || \
            echo "AVISO: falha ao enviar alerta WhatsApp de budget"
    fi

    # Reportar ao painel
    if [[ -n "${PANEL_WEBHOOK_URL:-}" ]]; then
        curl -s --max-time 10 -X POST "$PANEL_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -H "X-License: ${LICENSE_KEY:-}" \
            -d "{\"event\":\"budget_exceeded\",\"custo_brl\":$CUSTO_BRL,\"budget_brl\":$LLM_BUDGET_BRL,\"tenant\":\"${TENANT_ID:-unknown}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
            > /dev/null 2>&1 || true
    fi

else
    PCT=$(python3 -c "print(f'{float(\"$CUSTO_BRL\")/float(\"$LLM_BUDGET_BRL\")*100:.1f}')")
    echo "✅ Dentro do orçamento ($PCT% utilizado)."

    # Reativar crons se estavam pausados (início do novo mês)
    # Só reativa se o orçamento do mês atual está abaixo do limite
    if [[ -f "$CRON_IDS_FILE" ]]; then
        source "$CRON_IDS_FILE"
        for VAR in CRON_ID_MANHA CRON_ID_TARDE; do
            if [[ -n "${!VAR:-}" ]]; then
                openclaw cron enable "${!VAR}" 2>/dev/null || true
            fi
        done
    fi
fi

# ── Reportar status normal ao painel ─────────────────────────────────────────
if [[ -n "${PANEL_WEBHOOK_URL:-}" && "$EXCEDEU" == "no" ]]; then
    curl -s --max-time 10 -X POST "$PANEL_WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -H "X-License: ${LICENSE_KEY:-}" \
        -d "{\"event\":\"budget_check\",\"custo_brl\":$CUSTO_BRL,\"budget_brl\":$LLM_BUDGET_BRL,\"status\":\"ok\",\"tenant\":\"${TENANT_ID:-unknown}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
        > /dev/null 2>&1 || true
fi

echo "=== check-budget.sh encerrado ==="
