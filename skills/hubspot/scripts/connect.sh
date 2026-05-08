#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="hubspot"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
STAGES_FILE="${HOME}/.openclaw/secrets/hubspot_stages.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/hubspot_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao HubSpot! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais HubSpot CRM"
echo ""

if [[ -z "${HUBSPOT_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Private App Token HubSpot (Configuracoes > Integracoes > Private Apps): ")" HUBSPOT_TOKEN
    [[ -z "$HUBSPOT_TOKEN" ]] && fail "Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
HUBSPOT_TOKEN=${HUBSPOT_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export HUBSPOT_TOKEN

if OUTPUT=$(python3 "$SCRIPT_DIR/hubspot_client.py" company_info 2>&1); then
    ok "Conectado ao HubSpot com sucesso!"
    # Fetch pipeline stages
    info "Buscando pipeline stages..."
    python3 -c "
import os, sys
sys.path.insert(0, '$SCRIPT_DIR')
sys.path.insert(0, os.path.join('$SCRIPT_DIR', '..', '..', '_lib'))
os.environ['HUBSPOT_TOKEN'] = '$HUBSPOT_TOKEN'
from hubspot_client import HubSpotClient
c = HubSpotClient()
stages = c._fetch_stages()
print(f'Pipeline com {len(stages)} stages mapeados.')
" 2>/dev/null || true
    ok "Setup completo!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o token."
fi
