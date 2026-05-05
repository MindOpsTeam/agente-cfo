#!/usr/bin/env bash
# _shared.sh — Helpers compartilhados entre todos os scripts do Agente CFO.
# NÃO execute diretamente. Use: source "$SCRIPT_DIR/_shared.sh"

# ── Carregar env file ─────────────────────────────────────────────────────────
_ENV_FILE="${CFO_ENV_FILE:-$HOME/.agente-cfo/.env}"
if [[ -f "$_ENV_FILE" ]]; then
    set +u
    # shellcheck source=/dev/null
    source "$_ENV_FILE"
    set -u
fi

# ── Defaults ──────────────────────────────────────────────────────────────────
PANEL_BASE_URL="${PANEL_BASE_URL:-}"          # URL do Supabase do cliente (sem default hardcoded)
LOG_DIR="${CFO_LOG_DIR:-$HOME/.agente-cfo/logs}"
STATE_DIR="${CFO_STATE_DIR:-$HOME/.agente-cfo}"
OMIE_SKILL_PATH="${OMIE_SKILL_PATH:-$HOME/.openclaw/workspace/skills/omie}"

mkdir -p "$LOG_DIR" "$STATE_DIR"

# ── _panel_event(type, severity, payload_json) ────────────────────────────────
# Envia evento ao painel via /event. Tolerante a falha.
# Silencioso se PANEL_BASE_URL, PANEL_TOKEN ou INSTANCE_ID não estiverem definidos.
_panel_event() {
    local type="$1"
    local severity="$2"
    local payload_json="${3:-{}}"

    [[ -z "${PANEL_BASE_URL:-}" ]] && return 0
    [[ -z "${PANEL_TOKEN:-}" ]]    && return 0
    [[ -z "${INSTANCE_ID:-}" ]]    && return 0

    local body
    body=$(printf '{"instance_id":"%s","type":"%s","severity":"%s","payload":%s}' \
        "$INSTANCE_ID" "$type" "$severity" "$payload_json")

    curl -s --max-time 10 -X POST "${PANEL_BASE_URL}/event" \
        -H "Content-Type: application/json" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -d "$body" \
        > /dev/null 2>&1 || true
}

# ── _panel_llm_usage(session_id, model, input_tokens, output_tokens, cost_brl, period) ──
# Upsert de uso LLM no painel via /llm-usage.
_panel_llm_usage() {
    local session_id="$1"
    local model="$2"
    local input_tokens="$3"
    local output_tokens="$4"
    local cost_brl="$5"
    local period="$6"

    [[ -z "${PANEL_BASE_URL:-}" ]] && return 0
    [[ -z "${PANEL_TOKEN:-}" ]]    && return 0
    [[ -z "${INSTANCE_ID:-}" ]]    && return 0

    local body
    body=$(printf '{"instance_id":"%s","session_id":"%s","model":"%s","input_tokens":%s,"output_tokens":%s,"cost_brl":%s,"period":"%s"}' \
        "$INSTANCE_ID" "$session_id" "$model" "$input_tokens" "$output_tokens" "$cost_brl" "$period")

    curl -s --max-time 10 -X POST "${PANEL_BASE_URL}/llm-usage" \
        -H "Content-Type: application/json" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -d "$body" \
        > /dev/null 2>&1 || true
}

# ── _panel_heartbeat() ────────────────────────────────────────────────────────
# Atualiza last_heartbeat da instância via /heartbeat.
_panel_heartbeat() {
    [[ -z "${PANEL_BASE_URL:-}" ]] && return 0
    [[ -z "${PANEL_TOKEN:-}" ]]    && return 0
    [[ -z "${INSTANCE_ID:-}" ]]    && return 0

    curl -s --max-time 10 -X POST "${PANEL_BASE_URL}/heartbeat" \
        -H "Content-Type: application/json" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -d "{\"instance_id\":\"${INSTANCE_ID}\"}" \
        > /dev/null 2>&1 || true
}
