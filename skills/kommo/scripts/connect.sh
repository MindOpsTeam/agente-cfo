#!/usr/bin/env bash
# connect.sh — Setup do Kommo CRM para o Agente CFO
set -euo pipefail

SKILL_NAME="kommo"
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
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${KOMMO_ACCESS_TOKEN:-}" "https://${KOMMO_SUBDOMAIN:-x}.kommo.com/api/v4/account" 2>/dev/null || echo "000")
    if [[ "$HTTP" == "200" ]]; then
        ok "Ja conectado ao Kommo! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Kommo CRM (formerly amoCRM)"
echo ""
echo "Pre-requisito: gere um Long-lived Access Token em"
echo "  Configuracoes → Integracoes → API"
echo ""

if [[ -z "${KOMMO_SUBDOMAIN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Subdominio Kommo (ex: minhaempresa de minhaempresa.kommo.com): ")" KOMMO_SUBDOMAIN
    [[ -z "$KOMMO_SUBDOMAIN" ]] && fail "Subdominio obrigatorio."
    KOMMO_SUBDOMAIN="${KOMMO_SUBDOMAIN%.kommo.com}"
    KOMMO_SUBDOMAIN="${KOMMO_SUBDOMAIN#https://}"
fi

if [[ -z "${KOMMO_ACCESS_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Access Token do Kommo: ")" KOMMO_ACCESS_TOKEN
    [[ -z "$KOMMO_ACCESS_TOKEN" ]] && fail "Access Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
KOMMO_SUBDOMAIN=${KOMMO_SUBDOMAIN}
KOMMO_ACCESS_TOKEN=${KOMMO_ACCESS_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${KOMMO_ACCESS_TOKEN}" "https://${KOMMO_SUBDOMAIN}.kommo.com/api/v4/account")
if [[ "$HTTP" == "200" ]]; then
    ok "Conectado ao Kommo! (HTTP $HTTP)"
    ok "Setup completo!"
else
    fail "Falha ao conectar (HTTP $HTTP). Verifique o subdominio e o Access Token."
fi
