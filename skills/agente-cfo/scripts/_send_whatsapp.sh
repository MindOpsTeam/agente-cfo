#!/usr/bin/env bash
# _send_whatsapp.sh — Wrapper de envio WhatsApp que converte +E.164 → JID antes do send.
# Uso: bash _send_whatsapp.sh "<to>" "<message>"
#
# Bug 11: wacli send --to "+5548992044331" falha com "no LID found" quando o
#   destino é o número pareado (caso comum: dono da PME enviando pra si mesmo).
#   JID direto "554892044331@s.whatsapp.net" funciona consistentemente.
#
# Retorna o exit code do wacli send (0 = sucesso, != 0 = falha).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

if [[ $# -lt 2 ]]; then
    echo "Uso: $0 <to> <message>" >&2
    echo "  <to>: número E.164 (+5511...) ou JID (...@s.whatsapp.net)" >&2
    exit 1
fi

TO_RAW="$1"
MESSAGE="$2"

# Converter para JID (passa direto se já for JID)
TO_JID=$(_to_jid "$TO_RAW")

LOG_FILE="$LOG_DIR/wacli-send.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] _send_whatsapp: to_raw=$TO_RAW to_jid=$TO_JID" >> "$LOG_FILE"

# Tenta send com --lock-wait para tolerar wacli-sync com o lock
# Se --lock-wait não existir nesta versão do wacli, cai no fallback sem flag.
if wacli send text --help 2>&1 | grep -q -- '--lock-wait'; then
    wacli send text --to "$TO_JID" --lock-wait 30s --message "$MESSAGE"
    WA_EXIT=$?
else
    wacli send text --to "$TO_JID" --message "$MESSAGE"
    WA_EXIT=$?
fi

if [[ $WA_EXIT -eq 0 ]]; then
    echo "[$TIMESTAMP] _send_whatsapp: OK (jid=$TO_JID)" >> "$LOG_FILE"
else
    echo "[$TIMESTAMP] _send_whatsapp: FAIL exit=$WA_EXIT (jid=$TO_JID)" >> "$LOG_FILE"
fi

exit $WA_EXIT
