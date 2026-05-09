#!/usr/bin/env bash
# connect.sh — Setup do Iugu para o Agente CFO
set -euo pipefail

SKILL_NAME="iugu"
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
    if python3 "$SCRIPT_DIR/iugu_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao Iugu! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Iugu"
echo ""
echo "Onde achar o token: app.iugu.com → Configurações → API → Chaves de API"
echo "  (use a chave de teste ou produção conforme o ambiente)"
echo ""

if [[ -z "${IUGU_API_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} API Token do Iugu: ")" IUGU_API_TOKEN
    [[ -z "$IUGU_API_TOKEN" ]] && fail "API Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
IUGU_API_TOKEN=${IUGU_API_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export IUGU_API_TOKEN

if OUTPUT=$(python3 "$SCRIPT_DIR/iugu_client.py" company_info 2>&1); then
    COMPANY=$(echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','?'))" 2>/dev/null || echo "?")
    ok "Conectado ao Iugu! Conta: ${COMPANY}"
    ok "Setup completo!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o API Token."
fi
