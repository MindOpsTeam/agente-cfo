#!/usr/bin/env bash
# connect.sh — Setup do Asaas para o Agente CFO
set -euo pipefail

SKILL_NAME="asaas"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/asaas_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao Asaas! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Asaas"
echo ""
echo "Onde achar o token: Minha Conta → Configurações → Integrações → API"
echo "URL: https://www.asaas.com/config/index"
echo ""

if [[ -z "${ASAAS_ENV:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Ambiente (prod/sandbox) [prod]: ")" _env
    ASAAS_ENV="${_env:-prod}"
fi

if [[ -z "${ASAAS_API_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} API Token do Asaas ($ASAAS_ENV): ")" ASAAS_API_TOKEN
    [[ -z "$ASAAS_API_TOKEN" ]] && fail "API Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
ASAAS_API_TOKEN=${ASAAS_API_TOKEN}
ASAAS_ENV=${ASAAS_ENV}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao ($ASAAS_ENV)..."
export ASAAS_API_TOKEN ASAAS_ENV

if OUTPUT=$(python3 "$SCRIPT_DIR/asaas_client.py" company_info 2>&1); then
    COMPANY=$(echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','?'))" 2>/dev/null || echo "?")
    ok "Conectado ao Asaas! Conta: ${COMPANY}"
    ok "Setup completo! (ambiente: $ASAAS_ENV)"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o token e o ambiente (prod/sandbox)."
fi
