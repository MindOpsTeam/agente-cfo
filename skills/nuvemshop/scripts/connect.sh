#!/usr/bin/env bash
# connect.sh — OAuth 2.0 flow para Nuvemshop
set -euo pipefail

SKILL_NAME="nuvemshop"
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
    if python3 "$SCRIPT_DIR/nuvemshop_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado a Nuvemshop! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Nuvemshop (OAuth 2.0)"
echo ""
echo "Pre-requisito: crie um app parceiro em partners.nuvemshop.com.br"
echo "  Redirect URI: https://localhost"
echo ""
echo "ALTERNATIVA mais simples (app privado/interno):"
echo "  1. Acesse sua loja Nuvemshop como admin"
echo "  2. Va em: Minha Conta → Aplicativos → Seu App"
echo "  3. Use o fluxo de Authorization Code abaixo"
echo ""

if [[ -z "${NS_CLIENT_ID:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Client ID (App ID) do app Nuvemshop: ")" NS_CLIENT_ID
    [[ -z "$NS_CLIENT_ID" ]] && fail "Client ID obrigatorio."
fi

if [[ -z "${NS_CLIENT_SECRET:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Client Secret do app: ")" NS_CLIENT_SECRET
    [[ -z "$NS_CLIENT_SECRET" ]] && fail "Client Secret obrigatorio."
fi

AUTH_URL="https://www.nuvemshop.com.br/apps/${NS_CLIENT_ID}/authorize"

echo ""
echo -e "${CYAN}Abra esta URL no navegador (logado como dono da loja) e autorize:${NC}"
echo "$AUTH_URL"
echo ""
echo "Após autorizar, o browser redireciona para https://localhost?code=XXXXX"
echo "Copie o valor do code."
echo ""
read -rp "$(echo -e "${CYAN}?${NC} Cole o codigo de autorizacao: ")" AUTH_CODE
[[ -z "$AUTH_CODE" ]] && fail "Codigo obrigatorio."

info "Trocando codigo por token..."
TOKEN_RESP=$(curl -s -X POST "https://www.nuvemshop.com.br/apps/authorize/token" \
    -H "Content-Type: application/json" \
    -d "{\"client_id\":\"${NS_CLIENT_ID}\",\"client_secret\":\"${NS_CLIENT_SECRET}\",\"grant_type\":\"authorization_code\",\"code\":\"${AUTH_CODE}\"}")

ACCESS_TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))"  2>/dev/null || echo "")
STORE_ID=$(echo "$TOKEN_RESP"     | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('user_id',''))"         2>/dev/null || echo "")

if [[ -z "$ACCESS_TOKEN" ]]; then
    echo "Resposta: $TOKEN_RESP"
    fail "Falha ao obter token. Verifique Client ID, Secret e codigo."
fi

cat > "$SECRETS_FILE" << EOF
NS_CLIENT_ID=${NS_CLIENT_ID}
NS_CLIENT_SECRET=${NS_CLIENT_SECRET}
NS_ACCESS_TOKEN=${ACCESS_TOKEN}
NS_STORE_ID=${STORE_ID}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export NS_CLIENT_ID NS_CLIENT_SECRET NS_ACCESS_TOKEN NS_STORE_ID

if OUTPUT=$(python3 "$SCRIPT_DIR/nuvemshop_client.py" company_info 2>&1); then
    STORE=$(echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','?'))" 2>/dev/null || echo "?")
    ok "Conectado a Nuvemshop! Loja: ${STORE} (store_id: ${STORE_ID})"
    ok "Setup completo! Token Nuvemshop é long-lived (sem refresh necessário)."
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique as credenciais."
fi
