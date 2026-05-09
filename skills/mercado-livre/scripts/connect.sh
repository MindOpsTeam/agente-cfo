#!/usr/bin/env bash
# connect.sh — OAuth 2.0 flow para Mercado Livre
set -euo pipefail

SKILL_NAME="mercado-livre"
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
    if python3 "$SCRIPT_DIR/mercado_livre_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao Mercado Livre! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Mercado Livre (OAuth 2.0)"
echo ""
echo "Pre-requisito: crie um app em developers.mercadolivre.com.br"
echo "  Redirect URI: https://localhost"
echo "  (qualquer URI — vamos usar OOB: o code aparece na URL de redirect)"
echo ""

if [[ -z "${ML_CLIENT_ID:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} App ID (Client ID) do Mercado Livre: ")" ML_CLIENT_ID
    [[ -z "$ML_CLIENT_ID" ]] && fail "App ID obrigatorio."
fi

if [[ -z "${ML_CLIENT_SECRET:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Client Secret (Secret Key) do app: ")" ML_CLIENT_SECRET
    [[ -z "$ML_CLIENT_SECRET" ]] && fail "Client Secret obrigatorio."
fi

# Montar URL de autorização (site_id=MLB = Brasil)
AUTH_URL="https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=${ML_CLIENT_ID}&redirect_uri=https://localhost"

echo ""
echo -e "${CYAN}Abra esta URL no navegador e autorize o app:${NC}"
echo "$AUTH_URL"
echo ""
echo "Após autorizar, o browser redireciona para https://localhost?code=TG-XXXXX"
echo "Copie apenas o valor do code (ex: TG-6831aac5...)"
echo ""
read -rp "$(echo -e "${CYAN}?${NC} Cole o codigo de autorizacao (code=...): ")" AUTH_CODE
[[ -z "$AUTH_CODE" ]] && fail "Codigo de autorizacao obrigatorio."

info "Trocando codigo por tokens..."
TOKEN_RESP=$(curl -s -X POST "https://api.mercadolibre.com/oauth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "Accept: application/json" \
    -d "grant_type=authorization_code&client_id=${ML_CLIENT_ID}&client_secret=${ML_CLIENT_SECRET}&code=${AUTH_CODE}&redirect_uri=https://localhost")

ACCESS_TOKEN=$(echo "$TOKEN_RESP"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))"  2>/dev/null || echo "")
REFRESH_TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('refresh_token',''))" 2>/dev/null || echo "")
USER_ID=$(echo "$TOKEN_RESP"       | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('user_id',''))"        2>/dev/null || echo "")
EXPIRES_IN=$(echo "$TOKEN_RESP"    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('expires_in',21600))"  2>/dev/null || echo "21600")

if [[ -z "$ACCESS_TOKEN" ]]; then
    echo "Resposta: $TOKEN_RESP"
    fail "Falha ao obter tokens. Verifique App ID, Secret e codigo."
fi

TOKEN_EXPIRY=$(python3 -c "import time; print(int(time.time() + ${EXPIRES_IN}))")

cat > "$SECRETS_FILE" << EOF
ML_CLIENT_ID=${ML_CLIENT_ID}
ML_CLIENT_SECRET=${ML_CLIENT_SECRET}
ML_ACCESS_TOKEN=${ACCESS_TOKEN}
ML_REFRESH_TOKEN=${REFRESH_TOKEN}
ML_USER_ID=${USER_ID}
ML_TOKEN_EXPIRY=${TOKEN_EXPIRY}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export ML_CLIENT_ID ML_CLIENT_SECRET ML_ACCESS_TOKEN ML_REFRESH_TOKEN ML_USER_ID ML_TOKEN_EXPIRY

if OUTPUT=$(python3 "$SCRIPT_DIR/mercado_livre_client.py" company_info 2>&1); then
    STORE=$(echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name','?'))" 2>/dev/null || echo "?")
    ok "Conectado ao Mercado Livre! Loja: ${STORE} (user_id: ${USER_ID})"
    ok "Setup completo!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique as credenciais e o codigo."
fi
