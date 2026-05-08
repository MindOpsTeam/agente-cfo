#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="rd-station"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/rd_station_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao RD Station CRM! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais RD Station CRM"
echo ""

if [[ -z "${RDSTATION_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Token RD Station CRM (Meu Perfil > Token de Integracao): ")" RDSTATION_TOKEN
    [[ -z "$RDSTATION_TOKEN" ]] && fail "Token obrigatorio."
fi

# Testar URL padrao primeiro, depois tentar variantes
RDSTATION_BASE_URL="${RDSTATION_BASE_URL:-https://crm.rdstation.com/api/v1}"

cat > "$SECRETS_FILE" << EOF
RDSTATION_TOKEN=${RDSTATION_TOKEN}
RDSTATION_BASE_URL=${RDSTATION_BASE_URL}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export RDSTATION_TOKEN RDSTATION_BASE_URL
if OUTPUT=$(python3 "$SCRIPT_DIR/rd_station_client.py" company_info 2>&1); then
    ok "Conectado ao RD Station CRM com sucesso!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o token."
fi
