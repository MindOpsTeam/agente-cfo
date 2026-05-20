#!/usr/bin/env bash
# panel_write_event.sh — Registra write executado por Marcos no painel.
# Marcos chama após CADA write bem-sucedido (create_payable, pay_payable, etc.)
#
# Uso:
#   bash panel_write_event.sh --action create_payable --erp omie --erp_record_id 4882 \
#     --amount 50 --supplier Uber --due_date 2026-05-20 --category Transporte \
#     --raw_text "gastei 50 com uber" --thread_id "whatsapp:inst:5511..." --run_id "inc_..." \
#     --channel "whatsapp:minha_inst"
#
# Lê do ~/.agente-cfo/.env: PANEL_BASE_URL, PANEL_TOKEN, INSTANCE_ID (opcional).
# Stdout: "OK: <id>" (201), "DUPLICATE: <id>" (200), ou WARN em stderr.

set -euo pipefail

ACTION=""; ERP=""; ERP_RECORD_ID=""; AMOUNT=""; SUPPLIER=""; DUE_DATE=""
CATEGORY=""; RAW_TEXT=""; THREAD_ID=""; RUN_ID=""; CHANNEL=""
STATUS="success"; ERROR_MSG=""; DEDUP_KEY_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action)         ACTION="$2"; shift 2 ;;
    --erp)            ERP="$2"; shift 2 ;;
    --erp_record_id)  ERP_RECORD_ID="$2"; shift 2 ;;
    --amount)         AMOUNT="$2"; shift 2 ;;
    --supplier|--supplier_or_customer) SUPPLIER="$2"; shift 2 ;;
    --due_date)       DUE_DATE="$2"; shift 2 ;;
    --category)       CATEGORY="$2"; shift 2 ;;
    --raw_text)       RAW_TEXT="$2"; shift 2 ;;
    --thread_id)      THREAD_ID="$2"; shift 2 ;;
    --run_id)         RUN_ID="$2"; shift 2 ;;
    --channel)        CHANNEL="$2"; shift 2 ;;
    --status)         STATUS="$2"; shift 2 ;;
    --error)          ERROR_MSG="$2"; shift 2 ;;
    --dedup_key)      DEDUP_KEY_OVERRIDE="$2"; shift 2 ;;
    *) echo "Arg desconhecido: $1" >&2; shift ;;
  esac
done

if [[ -z "$ACTION" || -z "$THREAD_ID" || -z "$CHANNEL" ]]; then
  echo "Obrigatório: --action, --thread_id, --channel" >&2
  exit 1
fi

ENV_FILE="${HOME}/.agente-cfo/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

PANEL_BASE_URL="${PANEL_BASE_URL:-}"
PANEL_TOKEN="${PANEL_TOKEN:-}"
INSTANCE_ID="${INSTANCE_ID:-}"

if [[ -z "$PANEL_BASE_URL" || -z "$PANEL_TOKEN" ]]; then
  echo "PANEL_BASE_URL e PANEL_TOKEN são obrigatórios no .env" >&2
  exit 2
fi

PAYLOAD=$(
  ACTION="$ACTION" ERP="$ERP" ERP_RECORD_ID="$ERP_RECORD_ID" \
  AMOUNT="$AMOUNT" SUPPLIER="$SUPPLIER" DUE_DATE="$DUE_DATE" \
  CATEGORY="$CATEGORY" RAW_TEXT="$RAW_TEXT" THREAD_ID="$THREAD_ID" \
  RUN_ID="$RUN_ID" CHANNEL="$CHANNEL" STATUS="$STATUS" \
  ERROR_MSG="$ERROR_MSG" INSTANCE_ID="$INSTANCE_ID" \
  DEDUP_KEY_OVERRIDE="$DEDUP_KEY_OVERRIDE" \
  python3 -c '
import json, os
def opt(k):
  v = os.environ.get(k, "")
  return v if v else None
def num(k):
  v = os.environ.get(k, "")
  if not v:
    return None
  try:
    return float(v)
  except ValueError:
    return None

d = {
  "channel":      os.environ.get("CHANNEL", ""),
  "thread_id":    os.environ.get("THREAD_ID", ""),
  "run_id":       opt("RUN_ID"),
  "action":       os.environ.get("ACTION", ""),
  "erp":          opt("ERP"),
  "erp_record_id":opt("ERP_RECORD_ID"),
  "amount":       num("AMOUNT"),
  "supplier":     opt("SUPPLIER"),
  "due_date":     opt("DUE_DATE"),
  "category":     opt("CATEGORY"),
  "raw_text":     opt("RAW_TEXT"),
  "status":       os.environ.get("STATUS", "success"),
  "error":        opt("ERROR_MSG"),
  "instance_id":  opt("INSTANCE_ID"),
  "dedup_key":    opt("DEDUP_KEY_OVERRIDE"),
}
print(json.dumps({k: v for k, v in d.items() if v is not None}))
'
)

LOG_FILE="${HOME}/.agente-cfo/logs/panel-write-event.log"
mkdir -p "$(dirname "$LOG_FILE")"
printf '[%s] action=%s thread=%s\n' "$(date +%FT%T)" "$ACTION" "$THREAD_ID" >> "$LOG_FILE"

RESP=$(curl -s -w "\n%{http_code}" --max-time 15 \
  -X POST "${PANEL_BASE_URL%/}/cfo-write-event" \
  -H "Content-Type: application/json" \
  -H "X-Panel-Token: ${PANEL_TOKEN}" \
  -d "$PAYLOAD" 2>>"$LOG_FILE" || printf '\n000')

HTTP_CODE=$(printf '%s' "$RESP" | tail -n1)
BODY=$(printf '%s\n' "$RESP" | sed '$d')

extract_id() {
  printf '%s' "$1" | python3 -c '
import json, sys
try:
  d = json.load(sys.stdin)
  print(d.get("id", "?"))
except Exception:
  print("?")
'
}

if [[ "$HTTP_CODE" == "200" ]]; then
  ID=$(extract_id "$BODY")
  printf '[%s] DUPLICATE id=%s\n' "$(date +%FT%T)" "$ID" >> "$LOG_FILE"
  echo "DUPLICATE: $ID"
elif [[ "$HTTP_CODE" == "201" ]]; then
  ID=$(extract_id "$BODY")
  printf '[%s] OK id=%s\n' "$(date +%FT%T)" "$ID" >> "$LOG_FILE"
  echo "OK: $ID"
else
  printf '[%s] WARN HTTP=%s body=%s\n' "$(date +%FT%T)" "$HTTP_CODE" "${BODY:0:200}" >> "$LOG_FILE"
  echo "WARN: panel_write_event HTTP=$HTTP_CODE body=${BODY:0:200}" >&2
  exit 4
fi
