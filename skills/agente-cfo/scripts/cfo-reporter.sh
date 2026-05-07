#!/usr/bin/env bash
# cfo-reporter.sh — Wrapper principal: lê prompt, coleta dados Omie, envia WhatsApp, reporta painel
# Uso: cfo-reporter.sh <caminho_do_prompt.md>
# Exemplo: cfo-reporter.sh ~/.openclaw/workspace/skills/agente-cfo/prompts/alerta_manha.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

# ── Validação de args ─────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    echo "Uso: $0 <prompt_file>" >&2
    exit 1
fi

PROMPT_FILE="$1"
if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERRO: arquivo de prompt não encontrado: $PROMPT_FILE" >&2
    exit 1
fi

# ── Config obrigatório ────────────────────────────────────────────────────────
: "${CFO_WHATSAPP_TO:?missing — defina CFO_WHATSAPP_TO no ambiente (ex: +5511999999999)}"
: "${OMIE_APP_KEY:?missing — defina OMIE_APP_KEY no ambiente}"
: "${OMIE_APP_SECRET:?missing — defina OMIE_APP_SECRET no ambiente}"

LOG_FILE="$LOG_DIR/cfo-reporter.log"
OMIE_WRAPPER="$SCRIPT_DIR/omie-pull-wrapper.sh"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
PROMPT_NAME=$(basename "$PROMPT_FILE" .md)

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== cfo-reporter.sh [$PROMPT_NAME] iniciado em $TIMESTAMP ==="

# ── Coletar dados do Omie ─────────────────────────────────────────────────────
echo "Coletando dados do Omie ERP..."

if ! RESUMO_FINANCEIRO=$(bash "$OMIE_WRAPPER" resumo_financeiro 2>&1); then
    echo "ERRO: falha ao coletar resumo_financeiro"
    _panel_event "alerta_enviado" "error" \
        "{\"prompt\":\"$PROMPT_NAME\",\"status\":\"fail\",\"detail\":\"omie resumo_financeiro falhou\"}"
    exit 1
fi

if ! CONTAS_RECEBER=$(bash "$OMIE_WRAPPER" contas_receber 1 50 2>&1); then
    echo "ERRO: falha ao coletar contas_receber"
    _panel_event "alerta_enviado" "error" \
        "{\"prompt\":\"$PROMPT_NAME\",\"status\":\"fail\",\"detail\":\"omie contas_receber falhou\"}"
    exit 1
fi

if ! CONTAS_PAGAR=$(bash "$OMIE_WRAPPER" contas_pagar 1 50 2>&1); then
    echo "ERRO: falha ao coletar contas_pagar"
    _panel_event "alerta_enviado" "error" \
        "{\"prompt\":\"$PROMPT_NAME\",\"status\":\"fail\",\"detail\":\"omie contas_pagar falhou\"}"
    exit 1
fi

echo "Dados Omie coletados com sucesso."

# ── Montar contexto ───────────────────────────────────────────────────────────
DATA_HOJE=$(date '+%d/%m/%Y')
DATA_HOJE_ISO=$(date '+%Y-%m-%d')

CONTEXT_FILE=$(mktemp /tmp/cfo-context-XXXXXX.json)
trap 'rm -f "$CONTEXT_FILE"' EXIT

# _json_or_raw: parseia entrada como JSON; se inválido, envelopa como string
_json_or_raw() {
    python3 - <<'PY'
import sys, json
data = sys.stdin.read().strip()
try:
    print(json.dumps(json.loads(data), ensure_ascii=False))
except json.JSONDecodeError:
    print(json.dumps(data, ensure_ascii=False))
PY
}

RESUMO_JSON=$(echo "$RESUMO_FINANCEIRO" | _json_or_raw)
RECEBER_JSON=$(echo "$CONTAS_RECEBER" | _json_or_raw)
PAGAR_JSON=$(echo "$CONTAS_PAGAR" | _json_or_raw)

cat > "$CONTEXT_FILE" << EOF
{
  "prompt_file": "$PROMPT_FILE",
  "data_hoje": "$DATA_HOJE",
  "data_hoje_iso": "$DATA_HOJE_ISO",
  "whatsapp_to": "$CFO_WHATSAPP_TO",
  "omie_resumo_financeiro": ${RESUMO_JSON},
  "omie_contas_receber": ${RECEBER_JSON},
  "omie_contas_pagar": ${PAGAR_JSON}
}
EOF

echo "Contexto preparado: $CONTEXT_FILE"

# ── Enviar via wacli ou expor dados para o agente ─────────────────────────────
echo "Enviando relatório via WhatsApp para $CFO_WHATSAPP_TO..."

if [[ "${CFO_STANDALONE:-false}" == "true" ]]; then
    FALLBACK_MSG="📊 Dados CFO [$DATA_HOJE] — relatório automático
Resumo Omie disponível. Execute com agente LLM para insight formatado."

    if wacli send text --to "$CFO_WHATSAPP_TO" --message "$FALLBACK_MSG"; then
        echo "✅ WhatsApp enviado com sucesso (modo standalone)."
        _panel_event "alerta_enviado" "info" \
            "{\"prompt\":\"$PROMPT_NAME\",\"status\":\"ok\",\"mode\":\"standalone\"}"
    else
        echo "❌ Falha ao enviar WhatsApp."
        _panel_event "alerta_enviado" "error" \
            "{\"prompt\":\"$PROMPT_NAME\",\"status\":\"fail\",\"detail\":\"wacli send falhou\"}"
        exit 1
    fi
else
    # Modo agente: expor dados para o agente OpenClaw processar
    echo "--- DADOS PARA O AGENTE ---"
    echo "PROMPT: $PROMPT_NAME"
    echo "DATA: $DATA_HOJE"
    echo "RESUMO_FINANCEIRO:"
    echo "$RESUMO_FINANCEIRO"
    echo "CONTAS_RECEBER (primeiros 50):"
    echo "$CONTAS_RECEBER"
    echo "CONTAS_PAGAR (primeiros 50):"
    echo "$CONTAS_PAGAR"
    echo "--- FIM DOS DADOS ---"
    echo ""
    echo "O agente deve agora gerar a mensagem conforme o prompt e enviá-la via:"
    echo "  wacli send text --to \"$CFO_WHATSAPP_TO\" --message \"<mensagem_gerada>\""

    # Report de conclusão (agente enviará depois, mas registramos a execução)
    _panel_event "alerta_enviado" "info" \
        "{\"prompt\":\"$PROMPT_NAME\",\"status\":\"ok\",\"mode\":\"agent\"}"
fi

echo "=== cfo-reporter.sh [$PROMPT_NAME] encerrado com sucesso ==="
