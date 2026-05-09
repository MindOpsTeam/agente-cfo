#!/usr/bin/env bash
# connect.sh — Setup do Pipedrive CRM para o Agente CFO
set -euo pipefail

SKILL_NAME="pipedrive"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
STAGES_FILE="${HOME}/.openclaw/secrets/pipedrive_stages.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

# Se já conectado e não forçando reconexão, sai cedo
if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/pipedrive_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao Pipedrive! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Pipedrive CRM"
echo ""
echo "Pre-requisito: gere uma API Token em"
echo "  Perfil → Configuracoes → API → Sua chave de API pessoal"
echo "  (ou crie um Personal Token em Settings > Personal Preferences > API)"
echo ""

if [[ -z "${PIPEDRIVE_COMPANY_DOMAIN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Subdominio da empresa no Pipedrive (ex: minhaempresa → minhaempresa.pipedrive.com): ")" PIPEDRIVE_COMPANY_DOMAIN
    [[ -z "$PIPEDRIVE_COMPANY_DOMAIN" ]] && fail "Subdominio obrigatorio."
    # Remove .pipedrive.com se o usuario copiou a URL inteira
    PIPEDRIVE_COMPANY_DOMAIN="${PIPEDRIVE_COMPANY_DOMAIN%.pipedrive.com}"
    PIPEDRIVE_COMPANY_DOMAIN="${PIPEDRIVE_COMPANY_DOMAIN#https://}"
fi

if [[ -z "${PIPEDRIVE_API_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} API Token do Pipedrive: ")" PIPEDRIVE_API_TOKEN
    [[ -z "$PIPEDRIVE_API_TOKEN" ]] && fail "API Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
PIPEDRIVE_COMPANY_DOMAIN=${PIPEDRIVE_COMPANY_DOMAIN}
PIPEDRIVE_API_TOKEN=${PIPEDRIVE_API_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export PIPEDRIVE_COMPANY_DOMAIN PIPEDRIVE_API_TOKEN

if OUTPUT=$(python3 "$SCRIPT_DIR/pipedrive_client.py" company_info 2>&1); then
    COMPANY=$(echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','?'))" 2>/dev/null || echo "?")
    ok "Conectado ao Pipedrive! Empresa: ${COMPANY}"

    # Buscar e cachear os stages do pipeline
    info "Buscando pipeline stages..."
    STAGE_COUNT=$(python3 -c "
import os, sys, json
sys.path.insert(0, '$SCRIPT_DIR')
sys.path.insert(0, os.path.join('$SCRIPT_DIR', '..', '..', '_lib'))
os.environ['PIPEDRIVE_COMPANY_DOMAIN'] = '$PIPEDRIVE_COMPANY_DOMAIN'
os.environ['PIPEDRIVE_API_TOKEN'] = '$PIPEDRIVE_API_TOKEN'
from pipedrive_client import PipedriveClient
c = PipedriveClient()
stages = c.fetch_stages()
print(len(stages))
" 2>/dev/null || echo "0")
    ok "${STAGE_COUNT} stage(s) mapeados e salvos em ${STAGES_FILE}."
    ok "Setup completo!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o subdominio e o API Token."
fi
