#!/usr/bin/env bash
# connect.sh — OAuth 2.0 flow para ContaAzul ERP
set -euo pipefail

SKILL_NAME="contaazul"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
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
    if python3 "$SCRIPT_DIR/contaazul_client.py" get_balance >/dev/null 2>&1; then
        ok "Ja conectado ao ContaAzul! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais ContaAzul ERP (OAuth 2.0)"
echo ""
echo "Pre-requisito: crie um app OAuth em developers.contaazul.com"
echo "  Tipo: Authorization Code"
echo "  Redirect URI: urn:ietf:wg:oauth:2.0:oob"
echo "  Escopos necessarios: financeiro"
echo ""

if [[ -z "${CONTAAZUL_CLIENT_ID:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Client ID do app OAuth ContaAzul: ")" CONTAAZUL_CLIENT_ID
    [[ -z "$CONTAAZUL_CLIENT_ID" ]] && fail "Client ID obrigatorio."
fi

if [[ -z "${CONTAAZUL_CLIENT_SECRET:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Client Secret do app OAuth ContaAzul: ")" CONTAAZUL_CLIENT_SECRET
    [[ -z "$CONTAAZUL_CLIENT_SECRET" ]] && fail "Client Secret obrigatorio."
fi

REDIRECT_URI="urn:ietf:wg:oauth:2.0:oob"
STATE=$(python3 -c "import secrets; print(secrets.token_hex(16))")

AUTH_URL="https://api.contaazul.com/auth/authorize?response_type=code&client_id=${CONTAAZUL_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&state=${STATE}&scope=financeiro"

echo ""
echo -e "${CYAN}Abra esta URL no navegador e autorize o app:${NC}"
echo "$AUTH_URL"
echo ""
read -rp "$(echo -e "${CYAN}?${NC} Cole o codigo de autorizacao recebido: ")" AUTH_CODE
[[ -z "$AUTH_CODE" ]] && fail "Codigo de autorizacao obrigatorio."

info "Trocando codigo por tokens..."
BASIC_AUTH=$(echo -n "${CONTAAZUL_CLIENT_ID}:${CONTAAZUL_CLIENT_SECRET}" | base64)

TOKEN_RESP=$(curl -s -X POST "https://api.contaazul.com/auth/token" \
    -H "Authorization: Basic ${BASIC_AUTH}" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=authorization_code&code=${AUTH_CODE}&redirect_uri=${REDIRECT_URI}")

ACCESS_TOKEN=$(echo "$TOKEN_RESP"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))"  2>/dev/null || echo "")
REFRESH_TOKEN=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('refresh_token',''))" 2>/dev/null || echo "")
EXPIRES_IN=$(echo "$TOKEN_RESP"    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('expires_in', 3600))" 2>/dev/null || echo "3600")

if [[ -z "$ACCESS_TOKEN" ]]; then
    echo "Resposta da API: $TOKEN_RESP"
    fail "Falha ao obter tokens. Verifique Client ID, Secret e codigo."
fi

TOKEN_EXPIRY=$(python3 -c "import time; print(int(time.time() + ${EXPIRES_IN}))")

cat > "$SECRETS_FILE" << EOF
CONTAAZUL_CLIENT_ID=${CONTAAZUL_CLIENT_ID}
CONTAAZUL_CLIENT_SECRET=${CONTAAZUL_CLIENT_SECRET}
CONTAAZUL_ACCESS_TOKEN=${ACCESS_TOKEN}
CONTAAZUL_REFRESH_TOKEN=${REFRESH_TOKEN}
CONTAAZUL_TOKEN_EXPIRY=${TOKEN_EXPIRY}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao (get_balance)..."
export CONTAAZUL_CLIENT_ID CONTAAZUL_CLIENT_SECRET CONTAAZUL_ACCESS_TOKEN CONTAAZUL_REFRESH_TOKEN CONTAAZUL_TOKEN_EXPIRY

if OUTPUT=$(python3 "$SCRIPT_DIR/contaazul_client.py" get_balance 2>&1); then
    SALDO=$(echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"R\$ {d.get('balance_brl', 0):,.2f}\")" 2>/dev/null || echo "N/A")
    ok "Conectado ao ContaAzul com sucesso!"
    ok "Saldo atual: ${SALDO}"
    ok "Setup completo!"
else
    echo "$OUTPUT"
    warn "get_balance falhou — o token pode estar ok mas a conta nao tem contas financeiras cadastradas."
    warn "Teste manual: python3 $(dirname "$0")/contaazul_client.py company_info"
fi
