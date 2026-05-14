#!/usr/bin/env bash
# send_telegram.sh — Envia mensagem Telegram via Bot API
#
# Uso: send_telegram.sh <bot_username> <chat_id> <text>
#   bot_username : username do bot (ex: "marcoscfo_bot")
#   chat_id      : ID do chat/usuário Telegram (número ou @username)
#   text         : texto da mensagem

set -euo pipefail

BOT_USERNAME="${1:-}"
CHAT_ID="${2:-}"
TEXT="${3:-}"

if [[ -z "$BOT_USERNAME" || -z "$CHAT_ID" || -z "$TEXT" ]]; then
    echo "Uso: $0 <bot_username> <chat_id> <text>" >&2
    echo "  ex: $0 marcoscfo_bot 123456789 'Olá!'" >&2
    exit 1
fi

ENV_FILE="${HOME}/.agente-cfo/.env"
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true

PANEL_BASE_URL="${PANEL_BASE_URL:-}"
PANEL_TOKEN="${PANEL_TOKEN:-}"
HOOKS_TOKEN="${HOOKS_TOKEN:-}"

if [[ -z "$PANEL_BASE_URL" || -z "$PANEL_TOKEN" || -z "$HOOKS_TOKEN" ]]; then
    echo "ERRO: PANEL_BASE_URL, PANEL_TOKEN ou HOOKS_TOKEN não configurados" >&2
    exit 1
fi

# Busca token do bot via edge function (sem armazenar em disco)
TOKEN_RESP=$(curl -s --max-time 10 \
    -H "X-Panel-Token: ${PANEL_TOKEN}" \
    -H "X-Hooks-Token: ${HOOKS_TOKEN}" \
    "${PANEL_BASE_URL}/telegram-bots-vps-token?bot_username=${BOT_USERNAME}" 2>/dev/null || echo "{}")

BOT_TOKEN=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('token',''))" "$TOKEN_RESP" 2>/dev/null || echo "")

if [[ -z "$BOT_TOKEN" ]]; then
    echo "ERRO: token do bot '$BOT_USERNAME' não encontrado ou edge fn não deployada" >&2
    exit 1
fi

# Envia mensagem
HTTP_CODE=$(curl -s -o /tmp/tg_send_resp.json -w "%{http_code}" \
    --max-time 30 \
    -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json, sys
print(json.dumps({
    'chat_id': sys.argv[1],
    'text': sys.argv[2],
    'parse_mode': 'Markdown',
}))
" "$CHAT_ID" "$TEXT")" 2>/dev/null || echo "000")

case "$HTTP_CODE" in
    200)
        echo "✓ Mensagem enviada via Telegram (bot=${BOT_USERNAME} → chat=${CHAT_ID})"
        ;;
    400)
        ERR=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('description','?'))" < /tmp/tg_send_resp.json 2>/dev/null || cat /tmp/tg_send_resp.json)
        echo "ERRO 400: ${ERR}" >&2
        exit 1
        ;;
    *)
        echo "ERRO HTTP ${HTTP_CODE}: $(cat /tmp/tg_send_resp.json 2>/dev/null | head -c 200)" >&2
        exit 1
        ;;
esac

rm -f /tmp/tg_send_resp.json
