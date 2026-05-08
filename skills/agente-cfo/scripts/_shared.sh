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
#
# Bug 10a: "${3:-{}}" em bash expande como "${3:-{" + literal "}}" → payload_json
#   recebia "}" extra quando $3 estava presente, causando JSON inválido (HTTP 400).
#   Fix: atribuição separada com [[ -z ]] guard.
# Bug 10b: "|| true" suprimia falhas silenciosamente. Agora loga em panel.log.
_panel_event() {
    local type="$1"
    local severity="$2"
    # Bug 10a: não usar "${3:-{}}" — bash interpreta "}}" como token extra
    local payload_json
    payload_json="${3:-}"
    [[ -z "$payload_json" ]] && payload_json="{}"

    [[ -z "${PANEL_BASE_URL:-}" ]] && return 0
    [[ -z "${PANEL_TOKEN:-}" ]]    && return 0
    [[ -z "${INSTANCE_ID:-}" ]]    && return 0

    local body
    body=$(printf '{"instance_id":"%s","type":"%s","severity":"%s","payload":%s}' \
        "$INSTANCE_ID" "$type" "$severity" "$payload_json")

    # Bug 10b: log HTTP != 2xx em panel.log em vez de suprimir silenciosamente
    local resp http_code
    resp=$(curl -s -w "\n%{http_code}" --max-time 10 -X POST "${PANEL_BASE_URL}/event" \
        -H "Content-Type: application/json" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -d "$body" 2>>"$LOG_DIR/panel.log" || echo -e "\n000")
    http_code=$(printf '%s' "$resp" | tail -n1)
    if [[ "$http_code" != "201" && "$http_code" != "200" ]]; then
        printf '[%s] _panel_event %s/%s -> HTTP %s body=%s\n' \
            "$(date +%FT%T)" "$type" "$severity" "$http_code" "$body" \
            >> "$LOG_DIR/panel.log"
    fi
    return 0
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

    # Bug 10b: log falhas em vez de suprimir
    local resp http_code
    resp=$(curl -s -w "\n%{http_code}" --max-time 10 -X POST "${PANEL_BASE_URL}/llm-usage" \
        -H "Content-Type: application/json" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -d "$body" 2>>"$LOG_DIR/panel.log" || echo -e "\n000")
    http_code=$(printf '%s' "$resp" | tail -n1)
    if [[ "$http_code" != "201" && "$http_code" != "200" ]]; then
        printf '[%s] _panel_llm_usage session=%s -> HTTP %s\n' \
            "$(date +%FT%T)" "$session_id" "$http_code" \
            >> "$LOG_DIR/panel.log"
    fi
    return 0
}

# ── _panel_heartbeat() ────────────────────────────────────────────────────────
# Atualiza last_heartbeat da instância via /heartbeat.
_panel_heartbeat() {
    [[ -z "${PANEL_BASE_URL:-}" ]] && return 0
    [[ -z "${PANEL_TOKEN:-}" ]]    && return 0
    [[ -z "${INSTANCE_ID:-}" ]]    && return 0

    local body="{\"instance_id\":\"${INSTANCE_ID}\""
    if [[ -n "${INGRESS_URL:-}" ]]; then
        body="${body},\"ingress_url\":\"${INGRESS_URL}\""
    fi
    body="${body}}"

    # Bug 10b: log falhas
    local resp http_code
    resp=$(curl -s -w "\n%{http_code}" --max-time 10 -X POST "${PANEL_BASE_URL}/heartbeat" \
        -H "Content-Type: application/json" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -d "$body" 2>>"$LOG_DIR/panel.log" || echo -e "\n000")
    http_code=$(printf '%s' "$resp" | tail -n1)
    if [[ "$http_code" != "201" && "$http_code" != "200" ]]; then
        printf '[%s] _panel_heartbeat -> HTTP %s\n' \
            "$(date +%FT%T)" "$http_code" \
            >> "$LOG_DIR/panel.log"
    fi
    return 0
}

# ── _to_jid(phone) ────────────────────────────────────────────────────────────
# Bug 11: wacli send --to "+5548992044331" falha com "no LID found" quando o
#   destino é o número pareado. JID direto funciona: "554892044331@s.whatsapp.net"
# Converte +E.164 → <digits>@s.whatsapp.net. Passa JID direto se já contiver @.
_to_jid() {
    local input="$1"
    if [[ "$input" == *"@"* ]]; then
        echo "$input"
        return
    fi
    # Remove +, espaços, parênteses, hífens
    local digits
    digits=$(printf '%s' "$input" | tr -d '+ ()-')
    echo "${digits}@s.whatsapp.net"
}
