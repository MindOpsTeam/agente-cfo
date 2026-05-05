#!/usr/bin/env bash
# omie-pull-wrapper.sh — Wrapper do omie_client.py com retry, timeout e log de erros
# Uso: omie-pull-wrapper.sh <comando_omie> [args...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

# ── Validação de args ─────────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    echo "Uso: $0 <comando_omie> [args...]" >&2
    exit 1
fi

OMIE_COMMAND="$1"
shift
OMIE_ARGS=("$@")

# ── Config ────────────────────────────────────────────────────────────────────
: "${OMIE_APP_KEY:?missing — defina OMIE_APP_KEY no ambiente}"
: "${OMIE_APP_SECRET:?missing — defina OMIE_APP_SECRET no ambiente}"

LOG_FILE="$LOG_DIR/omie-pull-wrapper.log"
OMIE_SCRIPT="$OMIE_SKILL_PATH/scripts/omie_client.py"

TIMEOUT_SEC=30
MAX_RETRIES=2
RETRY_WAIT=5

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] [omie-pull-wrapper] $*" | tee -a "$LOG_FILE"
}

# ── Verificar script Python ───────────────────────────────────────────────────
if [[ ! -f "$OMIE_SCRIPT" ]]; then
    log "ERRO: omie_client.py não encontrado em $OMIE_SCRIPT"
    _panel_event "omie_error" "error" \
        "{\"command\":\"$OMIE_COMMAND\",\"code\":\"omie_script_not_found\",\"message\":\"omie_client.py ausente em $OMIE_SCRIPT\"}"
    exit 1
fi

# ── Retry loop ────────────────────────────────────────────────────────────────
LAST_ERROR=""
attempt=0
while [[ $attempt -le $MAX_RETRIES ]]; do
    attempt=$((attempt + 1))
    log "Tentativa $attempt/$((MAX_RETRIES + 1)): omie $OMIE_COMMAND ${OMIE_ARGS[*]:-}"

    EXIT_CODE=0
    OUTPUT=$(timeout "$TIMEOUT_SEC" python3 "$OMIE_SCRIPT" "$OMIE_COMMAND" "${OMIE_ARGS[@]:-}" 2>&1) || EXIT_CODE=$?

    if [[ $EXIT_CODE -eq 0 ]]; then
        log "Sucesso: $OMIE_COMMAND"
        echo "$OUTPUT"
        exit 0
    fi

    if [[ $EXIT_CODE -eq 124 ]]; then
        log "TIMEOUT após ${TIMEOUT_SEC}s — tentativa $attempt"
        LAST_ERROR="timeout após ${TIMEOUT_SEC}s"
    else
        HTTP_CODE=$(echo "$OUTPUT" | grep -oP 'HTTP \K[0-9]+' | head -1 || echo "")
        if [[ "$HTTP_CODE" =~ ^4 ]]; then
            # 4xx: erro de credencial/parâmetro — sem retry, reporta imediatamente
            log "ERRO 4xx ($HTTP_CODE) — sem retry."
            _panel_event "omie_error" "error" \
                "{\"command\":\"$OMIE_COMMAND\",\"http_status\":$HTTP_CODE,\"message\":\"Erro HTTP $HTTP_CODE\"}"
            exit 1
        elif [[ "$HTTP_CODE" =~ ^5 ]]; then
            log "ERRO 5xx ($HTTP_CODE) — tentativa $attempt."
            LAST_ERROR="Erro HTTP $HTTP_CODE"
        else
            log "ERRO desconhecido (exit $EXIT_CODE) — tentativa $attempt."
            LAST_ERROR="exit $EXIT_CODE"
        fi
    fi

    if [[ $attempt -le $MAX_RETRIES ]]; then
        log "Aguardando ${RETRY_WAIT}s antes de nova tentativa..."
        sleep "$RETRY_WAIT"
    fi
done

log "FALHA DEFINITIVA após $((MAX_RETRIES + 1)) tentativas: $LAST_ERROR"
_panel_event "omie_error" "error" \
    "{\"command\":\"$OMIE_COMMAND\",\"message\":\"$LAST_ERROR após $((MAX_RETRIES + 1)) tentativas\"}"
exit 1
