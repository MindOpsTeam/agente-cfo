#!/usr/bin/env bash
# cfo-reporter.sh — Wrapper principal: lê prompt, coleta dados Omie, envia WhatsApp, reporta painel
# Uso: cfo-reporter.sh <caminho_do_prompt.md>
# Exemplo: cfo-reporter.sh ~/.openclaw/workspace/skills/agente-cfo/prompts/alerta_manha.md
set -euo pipefail

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

# ── Config ────────────────────────────────────────────────────────────────────
: "${CFO_WHATSAPP_TO:?missing — defina CFO_WHATSAPP_TO no ambiente (ex: +5511999999999)}"
: "${OMIE_APP_KEY:?missing — defina OMIE_APP_KEY no ambiente}"
: "${OMIE_APP_SECRET:?missing — defina OMIE_APP_SECRET no ambiente}"

OMIE_SKILL_PATH="${OMIE_SKILL_PATH:-$HOME/.openclaw/workspace/skills/omie}"
LOG_DIR="${CFO_LOG_DIR:-$HOME/.agente-cfo/logs}"
STATE_DIR="${CFO_STATE_DIR:-$HOME/.agente-cfo}"
LOG_FILE="$LOG_DIR/cfo-reporter.log"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$LOG_DIR" "$STATE_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
PROMPT_NAME=$(basename "$PROMPT_FILE" .md)

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== cfo-reporter.sh [$PROMPT_NAME] iniciado em $TIMESTAMP ==="

# ── Função: reportar ao painel (tolerante a falha) ────────────────────────────
_report_panel() {
    local event="$1" status="$2" detail="${3:-}"
    if [[ -n "${PANEL_WEBHOOK_URL:-}" ]]; then
        curl -s --max-time 10 -X POST "$PANEL_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -H "X-License: ${LICENSE_KEY:-}" \
            -d "{\"event\":\"$event\",\"status\":\"$status\",\"prompt\":\"$PROMPT_NAME\",\"detail\":\"$detail\",\"tenant\":\"${TENANT_ID:-unknown}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
            > /dev/null 2>&1 || true
    fi
}

# ── Coletar dados do Omie ─────────────────────────────────────────────────────
echo "Coletando dados do Omie ERP..."
OMIE_WRAPPER="$SKILL_DIR/scripts/omie-pull-wrapper.sh"

RESUMO_FINANCEIRO=""
CONTAS_RECEBER=""
CONTAS_PAGAR=""

if ! RESUMO_FINANCEIRO=$(bash "$OMIE_WRAPPER" resumo_financeiro 2>&1); then
    echo "ERRO: falha ao coletar resumo_financeiro"
    _report_panel "reporter_error" "fail" "omie resumo_financeiro falhou"
    exit 1
fi

if ! CONTAS_RECEBER=$(bash "$OMIE_WRAPPER" contas_receber 1 50 2>&1); then
    echo "ERRO: falha ao coletar contas_receber"
    _report_panel "reporter_error" "fail" "omie contas_receber falhou"
    exit 1
fi

if ! CONTAS_PAGAR=$(bash "$OMIE_WRAPPER" contas_pagar 1 50 2>&1); then
    echo "ERRO: falha ao coletar contas_pagar"
    _report_panel "reporter_error" "fail" "omie contas_pagar falhou"
    exit 1
fi

echo "Dados Omie coletados com sucesso."

# ── Montar contexto para o agente ─────────────────────────────────────────────
# Os dados coletados são exportados como variáveis de ambiente para que o
# agente OpenClaw que lê este prompt tenha acesso a eles no contexto da sessão.
# O agente (cron agentTurn) receberá o prompt + estes dados e gerará a mensagem.

DATA_HOJE=$(date '+%d/%m/%Y')
DATA_HOJE_ISO=$(date '+%Y-%m-%d')

# Escrever contexto em arquivo temporário para o agente consumir
CONTEXT_FILE=$(mktemp /tmp/cfo-context-XXXXXX.json)
trap 'rm -f "$CONTEXT_FILE"' EXIT

cat > "$CONTEXT_FILE" << EOF
{
  "prompt_file": "$PROMPT_FILE",
  "data_hoje": "$DATA_HOJE",
  "data_hoje_iso": "$DATA_HOJE_ISO",
  "whatsapp_to": "$CFO_WHATSAPP_TO",
  "omie_resumo_financeiro": $(echo "$RESUMO_FINANCEIRO" | python3 -c "import sys,json; data=sys.stdin.read(); print(json.dumps(data))" 2>/dev/null || echo "\"erro ao parsear\""),
  "omie_contas_receber": $(echo "$CONTAS_RECEBER" | python3 -c "import sys,json; data=sys.stdin.read(); print(json.dumps(data))" 2>/dev/null || echo "\"erro ao parsear\""),
  "omie_contas_pagar": $(echo "$CONTAS_PAGAR" | python3 -c "import sys,json; data=sys.stdin.read(); print(json.dumps(data))" 2>/dev/null || echo "\"erro ao parsear\"")
}
EOF

echo "Contexto preparado: $CONTEXT_FILE"

# ── Construir prompt completo para o agente ───────────────────────────────────
# Este script é chamado pelo cron agentTurn do OpenClaw.
# O agente já recebeu o prompt via cron message. Aqui apenas executamos
# a coleta de dados e a formatação, depois enviamos via wacli diretamente.
#
# NOTA: Em produção com cron agentTurn, o agente OpenClaw lê o prompt e
# chama este script via exec tool. Para testes manuais, você pode passar
# a mensagem gerada direto ao wacli com um LLM local.
#
# Para uso standalone (sem agente LLM), gera uma mensagem de fallback com dados brutos:

PROMPT_CONTENT=$(cat "$PROMPT_FILE")

# Mensagem de fallback com dados brutos (usado quando executado standalone sem LLM)
FALLBACK_MSG="📊 Dados CFO [$DATA_HOJE] — relatório automático
Resumo Omie disponível. Execute com agente LLM para insight formatado.
Dados brutos em: $CONTEXT_FILE"

# ── Tentar enviar via wacli ───────────────────────────────────────────────────
echo "Enviando relatório via WhatsApp para $CFO_WHATSAPP_TO..."

# Em contexto de cron agentTurn, o agente usa wacli diretamente após gerar a mensagem.
# Em contexto standalone (teste), usamos o fallback:
if [[ "${CFO_STANDALONE:-false}" == "true" ]]; then
    echo "Modo standalone: enviando mensagem de fallback..."
    if wacli send text --to "$CFO_WHATSAPP_TO" --message "$FALLBACK_MSG"; then
        echo "✅ WhatsApp enviado com sucesso (modo standalone)."
        _report_panel "reporter_sent" "ok" "standalone"
    else
        echo "❌ Falha ao enviar WhatsApp."
        _report_panel "reporter_error" "fail" "wacli send falhou"
        exit 1
    fi
else
    # Modo agente: exibir dados para o agente processar e enviar
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
fi

# ── Report final ao painel ────────────────────────────────────────────────────
_report_panel "reporter_complete" "ok" "$PROMPT_NAME"

echo "=== cfo-reporter.sh [$PROMPT_NAME] encerrado com sucesso ==="
