#!/usr/bin/env bash
# send_message.sh — Envia mensagem Telegram via Bot API.
# Args: $1=channel_full (ex: "telegram:marcoscfo_bot"), $2=chat_id, $3=text
# Lê: ~/.agente-cfo/.env (TELEGRAM_BOT_TOKEN_<BOT_USERNAME_UPPER> ou TELEGRAM_BOT_TOKEN)

set -euo pipefail

CHANNEL_FULL="${1:-}"
CHAT_ID="${2:-}"
TEXT="${3:-}"

if [[ -z "$CHANNEL_FULL" || -z "$CHAT_ID" || -z "$TEXT" ]]; then
  echo "Uso: $0 <channel_full> <chat_id> <text>" >&2
  exit 1
fi

ENV_FILE="${HOME}/.agente-cfo/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

# "telegram:marcoscfo_bot" → "MARCOSCFO_BOT"
BOT_USERNAME="${CHANNEL_FULL#*:}"
BOT_KEY=$(printf '%s' "$BOT_USERNAME" | tr '[:lower:]' '[:upper:]' | tr '-' '_')

# Indirect lookup: TELEGRAM_BOT_TOKEN_<BOT_KEY> tem prioridade sobre a genérica
SPECIFIC_VAR="TELEGRAM_BOT_TOKEN_${BOT_KEY}"
BOT_TOKEN="${!SPECIFIC_VAR:-}"
if [[ -z "$BOT_TOKEN" ]]; then
  BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
fi

if [[ -z "$BOT_TOKEN" ]]; then
  echo "Token Telegram não encontrado: $SPECIFIC_VAR ou TELEGRAM_BOT_TOKEN" >&2
  exit 2
fi

PAYLOAD=$(CHAT_ID="$CHAT_ID" TEXT="$TEXT" python3 -c '
import json, os
print(json.dumps({
  "chat_id": os.environ["CHAT_ID"],
  "text": os.environ["TEXT"],
  "parse_mode": "Markdown",
}))
')

LOG_FILE="${HOME}/.agente-cfo/logs/telegram-send.log"
mkdir -p "$(dirname "$LOG_FILE")"
printf '[%s] send_message bot=%s chat_id=%s\n' "$(date +%FT%T)" "$BOT_USERNAME" "$CHAT_ID" >> "$LOG_FILE"

MAX_TRIES=2
HTTP_CODE="000"
for attempt in $(seq 1 $MAX_TRIES); do
  HTTP_CODE=$(curl -s -o /tmp/_tg_resp.json -w "%{http_code}" \
    --max-time 15 \
    -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>>"$LOG_FILE" || echo "000")

  if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "201" ]]; then
    printf '[%s] OK HTTP=%s attempt=%d\n' "$(date +%FT%T)" "$HTTP_CODE" "$attempt" >> "$LOG_FILE"
    exit 0
  fi

  printf '[%s] FAIL HTTP=%s attempt=%d body=%s\n' \
    "$(date +%FT%T)" "$HTTP_CODE" "$attempt" \
    "$(head -c 200 /tmp/_tg_resp.json 2>/dev/null)" >> "$LOG_FILE"

  [[ $attempt -lt $MAX_TRIES ]] && sleep 2
done

echo "Falha ao enviar mensagem Telegram após $MAX_TRIES tentativas (HTTP=$HTTP_CODE)" >&2
exit 3
