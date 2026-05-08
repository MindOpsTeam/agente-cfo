#!/usr/bin/env bash
# connect.sh — OAuth 2.0 flow para Bling ERP v3
set -euo pipefail

SKILL_NAME="bling"
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
    if python3 "$SCRIPT_DIR/bling_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao Bling! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Bling ERP (OAuth 2.0)"
echo ""
echo "Pre-requisito: crie um app OAuth em developer.bling.com.br"
echo "  Redirect URI: urn:ietf:wg:oauth:2.0:oob"
echo "  (ou http://localhost:9876/callback se OOB nao for suportado)"
echo ""

if [[ -z "${BLING_CLIENT_ID:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Client ID do app OAuth Bling: ")" BLING_CLIENT_ID
    [[ -z "$BLING_CLIENT_ID" ]] && fail "Client ID obrigatorio."
fi

if [[ -z "${BLING_CLIENT_SECRET:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Client Secret do app OAuth Bling: ")" BLING_CLIENT_SECRET
    [[ -z "$BLING_CLIENT_SECRET" ]] && fail "Client Secret obrigatorio."
fi

STATE=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
REDIRECT_URI="urn:ietf:wg:oauth:2.0:oob"

AUTH_URL="https://www.bling.com.br/Api/v3/oauth/authorize?response_type=code&client_id=${BLING_CLIENT_ID}&state=${STATE}"

echo ""
echo -e "${CYAN}Abra esta URL no navegador e autorize o app:${NC}"
echo "$AUTH_URL"
echo ""
read -rp "$(echo -e "${CYAN}?${NC} Cole o codigo de autorizacao: ")" AUTH_CODE
[[ -z "$AUTH_CODE" ]] && fail "Codigo de autorizacao obrigatorio."

info "Trocando codigo por tokens..."
BASIC_AUTH=$(echo -n "${BLING_CLIENT_ID}:${BLING_CLIENT_SECRET}" | base64)

TOKEN_RESP=$(curl -s -X POST "https://api.bling.com.br/Api/v3/oauth/token" \
    -H "Authorization: Basic ${BASIC_AUTH}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=authorization_code&code=${AUTH_CODE}&redirect_uri=${REDIRECT_URI}")

ACCESS_TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo "")
REFRESH_TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('refresh_token',''))" 2>/dev/null || echo "")
EXPIRES_IN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('expires_in',7200))" 2>/dev/null || echo "7200")

if [[ -z "$ACCESS_TOKEN" ]]; then
    echo "Resposta: $TOKEN_RESP"
    fail "Falha ao obter tokens. Verifique Client ID, Secret e codigo."
fi

TOKEN_EXPIRY=$(python3 -c "import time; print(int(time.time() + ${EXPIRES_IN}))")

cat > "$SECRETS_FILE" << EOF
BLING_CLIENT_ID=${BLING_CLIENT_ID}
BLING_CLIENT_SECRET=${BLING_CLIENT_SECRET}
BLING_ACCESS_TOKEN=${ACCESS_TOKEN}
BLING_REFRESH_TOKEN=${REFRESH_TOKEN}
BLING_TOKEN_EXPIRY=${TOKEN_EXPIRY}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export BLING_CLIENT_ID BLING_CLIENT_SECRET BLING_ACCESS_TOKEN BLING_REFRESH_TOKEN BLING_TOKEN_EXPIRY
if OUTPUT=$(python3 "$SCRIPT_DIR/bling_client.py" company_info 2>&1); then
    ok "Conectado ao Bling com sucesso!"
    echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Empresa: {d.get(\"name\",\"?\")}')" 2>/dev/null || true
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique as credenciais."
fi
