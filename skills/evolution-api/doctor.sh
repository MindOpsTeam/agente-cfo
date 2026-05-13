#!/usr/bin/env bash
# doctor.sh — valida daemon + conectividade com Evolution API
set -euo pipefail

ENV_FILE="${HOME}/.agente-cfo/.env"
LOG_FILE="${HOME}/.agente-cfo/logs/evolution-sync.log"

ok()  { echo "✓ $*"; }
warn(){ echo "⚠ $*"; }
err() { echo "✗ $*"; }

echo ""
echo "=== Evolution API — Doctor ==="
echo ""

# Carrega env
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true

# 1. Env vars obrigatórias
[[ -n "${PANEL_BASE_URL:-}" ]] && ok "PANEL_BASE_URL definida" || err "PANEL_BASE_URL não definida"
[[ -n "${PANEL_TOKEN:-}" ]]    && ok "PANEL_TOKEN definida"    || err "PANEL_TOKEN não definida"
[[ -n "${HOOKS_TOKEN:-}" ]]    && ok "HOOKS_TOKEN definida"    || err "HOOKS_TOKEN não definida"

# 2. Serviço systemd
if systemctl is-active cfo-evolution-sync &>/dev/null; then
    ok "cfo-evolution-sync.service está ativo"
else
    warn "cfo-evolution-sync.service não está ativo"
fi

# 3. Testa edge function evolution-config-vps
if [[ -n "${PANEL_BASE_URL:-}" && -n "${PANEL_TOKEN:-}" && -n "${HOOKS_TOKEN:-}" ]]; then
    echo -n "Testando evolution-config-vps... "
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -H "X-Hooks-Token: ${HOOKS_TOKEN}" \
        "${PANEL_BASE_URL}/evolution-config-vps" 2>/dev/null || echo "000")
    case "$HTTP" in
        200) ok "evolution-config-vps respondeu 200" ;;
        404) warn "evolution-config-vps não deployada ainda (404)" ;;
        *)   warn "evolution-config-vps retornou HTTP $HTTP" ;;
    esac

    # Testa se Evolution está configurada e responde
    CFG=$(curl -s --max-time 10 \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        -H "X-Hooks-Token: ${HOOKS_TOKEN}" \
        "${PANEL_BASE_URL}/evolution-config-vps" 2>/dev/null || echo "{}")

    BASE_URL=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('base_url',''))" "$CFG" 2>/dev/null || true)
    API_KEY=$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print(d.get('api_key',''))" "$CFG" 2>/dev/null || true)

    if [[ -n "$BASE_URL" && -n "$API_KEY" ]]; then
        echo -n "Testando Evolution API em ${BASE_URL}... "
        EVO_HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
            --max-time 10 \
            -H "apikey: ${API_KEY}" \
            "${BASE_URL%/}/instance/fetchInstances" 2>/dev/null || echo "000")
        case "$EVO_HTTP" in
            200) ok "Evolution API respondeu 200" ;;
            401) err "Evolution API: apikey inválida (401)" ;;
            *)   warn "Evolution API retornou HTTP $EVO_HTTP" ;;
        esac
    else
        warn "Evolution não configurada no painel ainda"
    fi
fi

# 4. Log recente
if [[ -f "$LOG_FILE" ]]; then
    echo ""
    echo "--- Últimas 5 linhas do log ---"
    tail -5 "$LOG_FILE"
else
    warn "Log não encontrado: $LOG_FILE"
fi

echo ""
