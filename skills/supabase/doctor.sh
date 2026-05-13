#!/usr/bin/env bash
# doctor.sh — valida a configuração do Supabase Projects Sync

set -euo pipefail

ENV_FILE="${HOME}/.agente-cfo/.env"
OPENCLAW_CONFIG="${HOME}/.openclaw/openclaw.json"
LOG_FILE="${HOME}/.agente-cfo/logs/supabase-sync.log"
ok() { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
err() { echo "✗ $*"; }

echo ""
echo "=== Supabase Sync — Doctor ==="
echo ""

# 1. Env vars obrigatórias
if [[ -f "$ENV_FILE" ]]; then
    source "$ENV_FILE" 2>/dev/null || true
fi

[[ -n "${PANEL_BASE_URL:-}" ]] && ok "PANEL_BASE_URL definida" || err "PANEL_BASE_URL não definida"
[[ -n "${PANEL_TOKEN:-}" ]] && ok "PANEL_TOKEN definida" || err "PANEL_TOKEN não definida"
[[ -n "${HOOKS_TOKEN:-}" ]] && ok "HOOKS_TOKEN definida" || err "HOOKS_TOKEN não definida"

# 2. npx disponível
if command -v npx &>/dev/null; then
    ok "npx disponível: $(npx --version 2>/dev/null)"
else
    err "npx não encontrado — instale Node.js 18+"
fi

# 3. openclaw disponível
if command -v openclaw &>/dev/null; then
    ok "openclaw disponível: $(openclaw --version 2>/dev/null | head -1)"
else
    warn "openclaw não encontrado no PATH"
fi

# 4. Serviço systemd
if systemctl is-active cfo-supabase-sync &>/dev/null; then
    ok "cfo-supabase-sync.service está ativo"
else
    warn "cfo-supabase-sync.service não está ativo"
fi

# 5. openclaw.json tem entradas supabase_*
if [[ -f "$OPENCLAW_CONFIG" ]]; then
    count=$(grep -c '"supabase_' "$OPENCLAW_CONFIG" 2>/dev/null || echo 0)
    if [[ "$count" -gt 0 ]]; then
        ok "$count projeto(s) Supabase registrado(s) em openclaw.json"
    else
        warn "Nenhum projeto Supabase em openclaw.json ainda (aguarde o sync ou verifique o painel)"
    fi
else
    warn "openclaw.json não encontrado"
fi

# 6. Log do sync
if [[ -f "$LOG_FILE" ]]; then
    echo ""
    echo "--- Últimas 5 linhas do log ---"
    tail -5 "$LOG_FILE"
else
    warn "Log não encontrado ainda: $LOG_FILE"
fi

echo ""
echo "Para testar conectividade com o painel:"
echo "  curl -s -H 'X-Panel-Token: \${PANEL_TOKEN}' -H 'X-Hooks-Token: \${HOOKS_TOKEN}' \\"
echo "    \${PANEL_BASE_URL}/supabase-projects-vps-list"
echo ""
