#!/usr/bin/env bash
# mcp_sync_now.sh — Força execução imediata dos daemons de sync sem esperar o loop.
#
# Uso: bash mcp_sync_now.sh [--verbose]
# Útil para debug após adicionar/remover integração no painel.

set -euo pipefail

WORKSPACE="${HOME}/.openclaw/workspace/skills"
ENV_FILE="${HOME}/.agente-cfo/.env"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

[[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true

echo ""
echo "=== mcp_sync_now.sh — Forçando sync MCP ==="
echo ""

# 1. credentials_sync — skills integrations
CREDS_SCRIPT="${WORKSPACE}/agente-cfo/scripts/credentials_sync.py"
if [[ -f "$CREDS_SCRIPT" ]]; then
    log "Rodando credentials_sync.py (1 ciclo)..."
    python3 - <<PYEOF
import sys, os
sys.path.insert(0, '${WORKSPACE}/agente-cfo/scripts')
# Carrega env
if os.path.exists('${ENV_FILE}'):
    with open('${ENV_FILE}') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())
import credentials_sync as cs
cs.load_env()
cs.sync()
print('[credentials_sync] Ciclo único concluído')
PYEOF
else
    log "AVISO: credentials_sync.py não encontrado em $CREDS_SCRIPT"
fi

echo ""

# 2. supabase_sync — supabase projects
SUPA_SCRIPT="${WORKSPACE}/supabase/scripts/supabase_sync.py"
if [[ -f "$SUPA_SCRIPT" ]]; then
    log "Rodando supabase_sync.py (1 ciclo)..."
    python3 - <<PYEOF
import sys, os
sys.path.insert(0, '${WORKSPACE}/supabase/scripts')
sys.path.insert(0, '${WORKSPACE}/agente-cfo/scripts')
if os.path.exists('${ENV_FILE}'):
    with open('${ENV_FILE}') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())
import supabase_sync as ss
ss.load_env()
ss.sync()
print('[supabase_sync] Ciclo único concluído')
PYEOF
else
    log "AVISO: supabase_sync.py não encontrado em $SUPA_SCRIPT"
fi

echo ""

# 3. Mostra estado atual dos MCPs
log "MCPs registrados atualmente:"
openclaw config get mcp.servers 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin) if sys.stdin.read(1) != '' else {}
" 2>/dev/null || true

python3 - <<PYEOF 2>/dev/null || true
import sys, json
from pathlib import Path
config_file = Path.home() / '.openclaw' / 'openclaw.json'
if config_file.exists():
    data = json.loads(config_file.read_text())
    servers = data.get('mcp', {}).get('servers', {})
    if servers:
        for name in sorted(servers.keys()):
            cmd = servers[name].get('command','?')
            args = ' '.join(servers[name].get('args',[]))[:60]
            print(f'  ✓ {name}: {cmd} {args}')
    else:
        print('  (nenhum MCP server registrado)')
PYEOF

echo ""
echo "Para ver logs detalhados:"
echo "  tail -50 ~/.agente-cfo/logs/credentials-sync.log"
echo "  tail -50 ~/.agente-cfo/logs/supabase-sync.log"
echo "  tail -50 ~/.agente-cfo/logs/mcp-sync.log"
echo ""

# Status final de todas as integrações
STATUS_SCRIPT="${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/integration_status.sh"
if [[ -f "$STATUS_SCRIPT" ]]; then
    bash "$STATUS_SCRIPT"
fi
