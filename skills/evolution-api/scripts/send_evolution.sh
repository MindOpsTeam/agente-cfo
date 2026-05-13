#!/usr/bin/env bash
# send_evolution.sh — Envia mensagem WhatsApp via Evolution API (multi-instance)
#
# Uso: send_evolution.sh <instance_name> <to_e164> <message>
#   instance_name : nome da instância Evolution (ex: "vendas", "suporte")
#   to_e164       : número no formato E.164 (ex: "+5511999999999")
#   message       : texto da mensagem
#
# A config da Evolution (base_url, api_key) é buscada via edge function.
# Não armazena credenciais em disco.

set -euo pipefail

INSTANCE="${1:-}"
TO="${2:-}"
MSG="${3:-}"

if [[ -z "$INSTANCE" || -z "$TO" || -z "$MSG" ]]; then
    echo "Uso: $0 <instance_name> <to_e164> <message>" >&2
    echo "  ex: $0 vendas +5511999999999 'Olá!'" >&2
    exit 1
fi

# Carrega env da VPS
ENV_FILE="${HOME}/.agente-cfo/.env"
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true

PANEL_BASE_URL="${PANEL_BASE_URL:-}"
PANEL_TOKEN="${PANEL_TOKEN:-}"
HOOKS_TOKEN="${HOOKS_TOKEN:-}"

if [[ -z "$PANEL_BASE_URL" || -z "$PANEL_TOKEN" || -z "$HOOKS_TOKEN" ]]; then
    echo "ERRO: PANEL_BASE_URL, PANEL_TOKEN ou HOOKS_TOKEN não configurados" >&2
    exit 1
fi

# Busca config da Evolution via edge function
CFG=$(curl -s --max-time 10 \
    -H "X-Panel-Token: ${PANEL_TOKEN}" \
    -H "X-Hooks-Token: ${HOOKS_TOKEN}" \
    "${PANEL_BASE_URL}/evolution-config-vps" 2>/dev/null || echo "{}")

BASE_URL=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('base_url',''))" "$CFG" 2>/dev/null || echo "")
API_KEY=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('api_key',''))" "$CFG" 2>/dev/null || echo "")

if [[ -z "$BASE_URL" || -z "$API_KEY" ]]; then
    echo "ERRO: Evolution não configurada no painel" >&2
    exit 1
fi

# Normaliza número: remove +, espaços, hifens
NUMBER=$(echo "$TO" | tr -d '+\- ')

# Monta payload JSON
PAYLOAD=$(python3 -c "
import json, sys
number = sys.argv[1]
text = sys.argv[2]
# Garante formato sem + (Evolution aceita 5511999999999)
print(json.dumps({'number': number, 'text': text}))
" "$NUMBER" "$MSG")

# Envia via Evolution API
HTTP_CODE=$(curl -s -o /tmp/evo_send_resp.json -w "%{http_code}" \
    --max-time 30 \
    -X POST "${BASE_URL%/}/message/sendText/${INSTANCE}" \
    -H "Content-Type: application/json" \
    -H "apikey: ${API_KEY}" \
    -d "$PAYLOAD" 2>/dev/null || echo "000")

case "$HTTP_CODE" in
    200|201)
        echo "✓ Mensagem enviada via Evolution (${INSTANCE} → ${TO})"
        ;;
    400)
        ERR=$(cat /tmp/evo_send_resp.json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('message',d))" 2>/dev/null || cat /tmp/evo_send_resp.json)
        echo "ERRO 400: ${ERR}" >&2
        exit 1
        ;;
    *)
        echo "ERRO HTTP ${HTTP_CODE}: $(cat /tmp/evo_send_resp.json 2>/dev/null | head -c 200)" >&2
        exit 1
        ;;
esac

rm -f /tmp/evo_send_resp.json
