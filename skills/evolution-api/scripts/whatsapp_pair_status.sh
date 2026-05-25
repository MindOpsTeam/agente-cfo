#!/usr/bin/env bash
# whatsapp_pair_status.sh — Consulta estado de conexão de instância WhatsApp via Evolution API.
#
# Parte do SPRINT CHAN-1: polling de estado pelo painel sem SSH.
#
# Uso:
#   bash whatsapp_pair_status.sh --instance <nome>
#
# Saída (stdout JSON):
#   {"state":"open"}        — conectado (QR escaneado)
#   {"state":"connecting"}  — aguardando scan
#   {"state":"close"}       — desconectado
#   {"state":"unknown","error":"<msg>"}  — erro na consulta
#
# Requer no ~/.agente-cfo/.env:
#   EVOLUTION_API_URL, EVOLUTION_API_KEY
#
# Sprint CHAN-1 — 2026-05-25

set -euo pipefail

ENV_FILE="${HOME}/.agente-cfo/.env"
[[ -f "$ENV_FILE" ]] && { set -a; source "$ENV_FILE"; set +a; }

LOG_FILE="${HOME}/.agente-cfo/logs/whatsapp-pair.log"
mkdir -p "$(dirname "$LOG_FILE")"

_log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" >> "$LOG_FILE"; }

# ── Parse args ────────────────────────────────────────────────────────────────
INSTANCE_NAME=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --instance) INSTANCE_NAME="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [[ -z "$INSTANCE_NAME" ]]; then
    printf '{"state":"unknown","error":"argumento --instance obrigatorio"}\n' >&2
    exit 1
fi

# Valida nome
if ! printf '%s' "$INSTANCE_NAME" | grep -qE '^[a-zA-Z0-9_-]{1,64}$'; then
    printf '{"state":"unknown","error":"nome de instancia invalido"}\n' >&2
    exit 1
fi

_log "whatsapp_pair_status instance=$INSTANCE_NAME"

# ── Env vars ──────────────────────────────────────────────────────────────────
EVOLUTION_API_URL="${EVOLUTION_API_URL:-}"
EVOLUTION_API_KEY="${EVOLUTION_API_KEY:-}"

if [[ -z "$EVOLUTION_API_URL" || -z "$EVOLUTION_API_KEY" ]]; then
    printf '{"state":"unknown","error":"EVOLUTION_API_URL ou EVOLUTION_API_KEY nao definidos"}\n' >&2
    exit 1
fi

# ── Consulta /instance/connectionState/<instance> ─────────────────────────────
RESP_FILE=$(mktemp /tmp/_evo_state_XXXXXX.json)
trap 'rm -f "$RESP_FILE"' EXIT

HTTP_CODE=$(curl -s -o "$RESP_FILE" -w "%{http_code}" \
    --max-time 15 \
    -X GET "${EVOLUTION_API_URL%/}/instance/connectionState/${INSTANCE_NAME}" \
    -H "apikey: ${EVOLUTION_API_KEY}" 2>>"$LOG_FILE" || echo "000")

_log "Evolution /connectionState HTTP=$HTTP_CODE"

if [[ "$HTTP_CODE" == "000" ]]; then
    printf '{"state":"unknown","error":"timeout ou falha de rede na Evolution API"}\n'
    exit 0
fi

if [[ "$HTTP_CODE" == "404" ]]; then
    printf '{"state":"close","error":"instancia nao encontrada na Evolution API"}\n'
    exit 0
fi

if [[ "$HTTP_CODE" != "200" ]]; then
    ERR_BODY=$(head -c 200 "$RESP_FILE" 2>/dev/null || echo "")
    printf '{"state":"unknown","error":"HTTP %s: %s"}\n' "$HTTP_CODE" "$ERR_BODY"
    exit 0
fi

# ── Extrai state da resposta ───────────────────────────────────────────────────
# Formato Evolution: {"instance":{"instanceName":"...","state":"open"}}
# ou {"state":"open"} dependendo da versão
STATE=$(python3 -c "
import sys, json
try:
    d = json.load(open('$RESP_FILE'))
    # Tenta múltiplos caminhos
    state = d.get('state') or \
            (d.get('instance', {}) or {}).get('state') or \
            'unknown'
    # Normaliza: open, close, connecting
    state = str(state).lower()
    if state not in ('open', 'close', 'connecting'):
        state = 'unknown'
    print(state)
except Exception as e:
    print('unknown')
" 2>/dev/null || echo "unknown")

_log "state=$STATE"
printf '{"state":"%s"}\n' "$STATE"
