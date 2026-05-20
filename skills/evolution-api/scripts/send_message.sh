#!/usr/bin/env bash
# send_message.sh — Envia mensagem WhatsApp via Evolution API REST.
# Args: $1=channel_full (ex: "whatsapp:minha_instancia"), $2=external_id (phone E.164 ou JID), $3=text
# Lê: ~/.agente-cfo/.env (EVOLUTION_API_URL, EVOLUTION_API_KEY)

set -euo pipefail

CHANNEL_FULL="${1:-}"
EXTERNAL_ID="${2:-}"
TEXT="${3:-}"

if [[ -z "$CHANNEL_FULL" || -z "$EXTERNAL_ID" || -z "$TEXT" ]]; then
  echo "Uso: $0 <channel_full> <external_id> <text>" >&2
  exit 1
fi

ENV_FILE="${HOME}/.agente-cfo/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

EVOLUTION_API_URL="${EVOLUTION_API_URL:-}"
EVOLUTION_API_KEY="${EVOLUTION_API_KEY:-}"

if [[ -z "$EVOLUTION_API_URL" || -z "$EVOLUTION_API_KEY" ]]; then
  echo "EVOLUTION_API_URL e EVOLUTION_API_KEY são obrigatórios no .env" >&2
  exit 2
fi

# "whatsapp:minha_instancia" → "minha_instancia"
INSTANCE="${CHANNEL_FULL#*:}"

# Normaliza número: remove +, espaços, hifens, parenteses
NUMBER=$(printf '%s' "$EXTERNAL_ID" | tr -d '+ ()-')

PAYLOAD=$(NUMBER="$NUMBER" TEXT="$TEXT" python3 -c '
import json, os
print(json.dumps({"number": os.environ["NUMBER"], "text": os.environ["TEXT"]}))
')

LOG_FILE="${HOME}/.agente-cfo/logs/evolution-send.log"
mkdir -p "$(dirname "$LOG_FILE")"
printf '[%s] send_message instance=%s number=%s\n' \
  "$(date +%FT%T)" "$INSTANCE" "$NUMBER" >> "$LOG_FILE"

MAX_TRIES=2
HTTP_CODE="000"
for attempt in $(seq 1 $MAX_TRIES); do
  HTTP_CODE=$(curl -s -o /tmp/_evo_resp.json -w "%{http_code}" \
    --max-time 15 \
    -X POST "${EVOLUTION_API_URL%/}/message/sendText/${INSTANCE}" \
    -H "Content-Type: application/json" \
    -H "apikey: ${EVOLUTION_API_KEY}" \
    -d "$PAYLOAD" 2>>"$LOG_FILE" || echo "000")

  if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "201" ]]; then
    printf '[%s] OK HTTP=%s attempt=%d\n' "$(date +%FT%T)" "$HTTP_CODE" "$attempt" >> "$LOG_FILE"
    exit 0
  fi

  printf '[%s] FAIL HTTP=%s attempt=%d body=%s\n' \
    "$(date +%FT%T)" "$HTTP_CODE" "$attempt" \
    "$(head -c 200 /tmp/_evo_resp.json 2>/dev/null)" >> "$LOG_FILE"

  [[ $attempt -lt $MAX_TRIES ]] && sleep 2
done

echo "Falha ao enviar mensagem WhatsApp após $MAX_TRIES tentativas (HTTP=$HTTP_CODE)" >&2
exit 3
