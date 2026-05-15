#!/usr/bin/env bash
#
# panel_reply.sh — envia a resposta de Marcos pro chat do painel.
# Usado quando o run tem name=panel_chat (chamado pelo chat-send-message).
#
# Uso:
#   bash panel_reply.sh "<thread_id>" "<run_id>" "<conteudo>" [status]
#   status: "sent" (default) | "error"
#
# Lê PANEL_BASE_URL e PANEL_TOKEN de ~/.agente-cfo/.env.

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "uso: $0 <thread_id> <run_id> <conteudo> [status]" >&2
  exit 2
fi

THREAD_ID="$1"
RUN_ID="$2"
CONTENT="$3"
STATUS="${4:-sent}"

ENV_FILE="${HOME}/.agente-cfo/.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck source=/dev/null
  set -a; source "$ENV_FILE"; set +a
fi

if [[ -z "${PANEL_BASE_URL:-}" || -z "${PANEL_TOKEN:-}" ]]; then
  echo "PANEL_BASE_URL e PANEL_TOKEN são obrigatórios (definir em $ENV_FILE)" >&2
  exit 3
fi

PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
  'thread_id': sys.argv[1],
  'run_id': sys.argv[2],
  'content': sys.argv[3],
  'status': sys.argv[4],
}))
" "$THREAD_ID" "$RUN_ID" "$CONTENT" "$STATUS")

curl -s -X POST "${PANEL_BASE_URL%/}/chat-marcos-reply" \
  -H "Content-Type: application/json" \
  -H "X-Panel-Token: ${PANEL_TOKEN}" \
  -d "$PAYLOAD"
echo

# Sprint 54 — Dispara marcos_learn.sh em background (fire-and-forget)
# Só aprendemos quando o run foi bem-sucedido (status=sent)
if [[ "${STATUS:-sent}" == "sent" && "${MARCOS_LEARN_DISABLED:-0}" != "1" ]]; then
    LEARN_SCRIPT="${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/marcos_learn.sh"
    if [[ -f "$LEARN_SCRIPT" ]]; then
        _LEARN_PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
    'thread_id': sys.argv[1],
    'user_message': '',
    'marcos_response': sys.argv[2],
    'tools_used': [],
    'channel': 'panel',
}))
" "$THREAD_ID" "${CONTENT:0:800}" 2>/dev/null || echo "")
        if [[ -n "$_LEARN_PAYLOAD" ]]; then
            echo "$_LEARN_PAYLOAD" | bash "$LEARN_SCRIPT" >> ~/.agente-cfo/logs/marcos-learn.log 2>&1 &
        fi
    fi
fi
