#!/usr/bin/env bash
# heartbeat.sh — Envia heartbeat ao painel central (POST /heartbeat)
# Chamado pelo cron */5 * * * * registrado pelo setup.sh.
# Antes de enviar, tenta re-detectar a URL do Cloudflare Tunnel —
# quick tunnels trocam URL a cada restart do cloudflared.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

LOG_FILE="$LOG_DIR/heartbeat.log"
_ENV_FILE="${CFO_ENV_FILE:-$HOME/.agente-cfo/.env}"

# ── Ler arquivos de identidade do skill ───────────────────────────────────────
_IDENTITY_DIR="$HOME/.openclaw/workspace/skills/agente-cfo/identity"
_IDENTITY_CONTENT=""
_SOUL_CONTENT=""
[[ -f "${_IDENTITY_DIR}/identity.md" ]] && _IDENTITY_CONTENT=$(< "${_IDENTITY_DIR}/identity.md")
[[ -f "${_IDENTITY_DIR}/soul.md" ]]     && _SOUL_CONTENT=$(< "${_IDENTITY_DIR}/soul.md")
SYSTEM_PROMPT="${_IDENTITY_CONTENT}${_SOUL_CONTENT:+$'\n\n'${_SOUL_CONTENT}}"
export SYSTEM_PROMPT

# ── Override de _panel_heartbeat para incluir system_prompt ───────────────────
_panel_heartbeat() {
    [[ -z "${PANEL_BASE_URL:-}" ]] && return 0
    [[ -z "${PANEL_TOKEN:-}" ]]    && return 0
    [[ -z "${INSTANCE_ID:-}" ]]    && return 0

    local sp_json
    sp_json=$(printf '%s' "${SYSTEM_PROMPT:-}" \
        | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null \
        || echo '""')

    local body="{\"instance_id\":\"${INSTANCE_ID}\""
    if [[ -n "${INGRESS_URL:-}" ]]; then
        body="${body},\"ingress_url\":\"${INGRESS_URL}\""
    fi
    body="${body},\"system_prompt\":${sp_json}}"

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

# ── Re-detectar URL do Cloudflare Tunnel ──────────────────────────────────────
# Tenta detectar a URL atual do tunnel. Se encontrar e for diferente da
# INGRESS_URL no .env, atualiza o .env e exporta a nova valor.
# Se não conseguir detectar, mantém o valor atual (sem sobrescrever).
_detect_tunnel_url() {
    local detected=""

    # Tentativa 1: journalctl (systemd disponível)
    if command -v journalctl &>/dev/null 2>&1; then
        detected=$(journalctl -u cloudflared-cfo -n 100 --no-pager 2>/dev/null \
            | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' \
            | tail -1 || true)
    fi

    # Tentativa 2: log file direto (se cloudflared logar em arquivo)
    if [[ -z "$detected" ]]; then
        for logpath in \
            "/var/log/cloudflared-cfo.log" \
            "${HOME}/.agente-cfo/logs/cloudflared.log" \
            "/tmp/cloudflared-cfo.log"
        do
            if [[ -f "$logpath" ]]; then
                detected=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$logpath" \
                    2>/dev/null | tail -1 || true)
                [[ -n "$detected" ]] && break
            fi
        done
    fi

    # Tentativa 3: /proc/<pid>/fd linka pro log (Linux)
    if [[ -z "$detected" ]]; then
        local cf_pid
        cf_pid=$(pgrep -x cloudflared 2>/dev/null | head -1 || true)
        if [[ -n "$cf_pid" ]]; then
            # Tentar ler do cmdline (às vezes o logfile está lá)
            local cf_log
            cf_log=$(cat "/proc/${cf_pid}/cmdline" 2>/dev/null \
                | tr '\0' ' ' \
                | grep -oE -- '--logfile [^ ]+' \
                | awk '{print $2}' || true)
            if [[ -n "$cf_log" && -f "$cf_log" ]]; then
                detected=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$cf_log" \
                    2>/dev/null | tail -1 || true)
            fi
        fi
    fi

    echo "${detected:-}"
}

NEW_URL=$(_detect_tunnel_url || true)

if [[ -n "$NEW_URL" && "$NEW_URL" != "${INGRESS_URL:-}" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] tunnel url mudou: ${INGRESS_URL:-vazio} → $NEW_URL" >> "$LOG_FILE"
    INGRESS_URL="$NEW_URL"
    export INGRESS_URL

    # Atualizar .env inplace se ele existir
    if [[ -f "$_ENV_FILE" ]]; then
        if grep -q "^INGRESS_URL=" "$_ENV_FILE"; then
            sed -i "s|^INGRESS_URL=.*|INGRESS_URL=${NEW_URL}|" "$_ENV_FILE"
        else
            echo "INGRESS_URL=${NEW_URL}" >> "$_ENV_FILE"
        fi
    fi
fi

# ── Enviar heartbeat (com INGRESS_URL atual no body, se definido) ─────────────
_panel_heartbeat

# Log compacto (1 linha por execução)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] heartbeat ok — instance=${INSTANCE_ID:-unset} ingress=${INGRESS_URL:-vazio}" >> "$LOG_FILE"
