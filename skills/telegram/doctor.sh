#!/usr/bin/env bash
# doctor.sh — valida daemon + conectividade Telegram
set -euo pipefail

ENV_FILE="${HOME}/.agente-cfo/.env"
LOG_FILE="${HOME}/.agente-cfo/logs/telegram-sync.log"

ok()  { echo "✓ $*"; }
warn(){ echo "⚠ $*"; }
err() { echo "✗ $*"; }

echo ""
echo "=== Telegram — Doctor ==="
echo ""

[[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true

[[ -n "${PANEL_BASE_URL:-}" ]] && ok "PANEL_BASE_URL definida" || err "PANEL_BASE_URL não definida"
[[ -n "${PANEL_TOKEN:-}" ]]    && ok "PANEL_TOKEN definida"    || err "PANEL_TOKEN não definida"
[[ -n "${HOOKS_TOKEN:-}" ]]    && ok "HOOKS_TOKEN definida"    || err "HOOKS_TOKEN não definida"

if systemctl is-active cfo-telegram-sync &>/dev/null; then
    ok "cfo-telegram-sync.service está ativo"
else
    warn "cfo-telegram-sync.service não está ativo"
fi

if [[ -n "${PANEL_BASE_URL:-}" && -n "${PANEL_TOKEN:-}" && -n "${HOOKS_TOKEN:-}" ]]; then
    echo -n "Testando telegram-bots-vps-list... "
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -H "X-Hooks-Token: ${HOOKS_TOKEN}" \
        "${PANEL_BASE_URL}/telegram-bots-vps-list" 2>/dev/null || echo "000")
    case "$HTTP" in
        200) ok "telegram-bots-vps-list respondeu 200" ;;
        404) warn "telegram-bots-vps-list não deployada ainda (404)" ;;
        *)   warn "telegram-bots-vps-list retornou HTTP $HTTP" ;;
    esac
fi

if [[ -f "$LOG_FILE" ]]; then
    echo ""
    echo "--- Últimas 5 linhas do log ---"
    tail -5 "$LOG_FILE"
else
    warn "Log não encontrado: $LOG_FILE"
fi

echo ""
