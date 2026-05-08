#!/usr/bin/env bash
# connect.sh — Configura credenciais para a skill omie
# Uso: bash connect.sh [--force]
set -euo pipefail

SKILL_NAME="omie"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

# Verificar se ja esta conectado (a menos que --force)
if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/omie_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao Omie! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Omie ERP"
echo ""

# Pedir credenciais
if [[ -z "${OMIE_APP_KEY:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Omie App Key: ")" OMIE_APP_KEY
    [[ -z "$OMIE_APP_KEY" ]] && fail "App Key obrigatoria."
fi

if [[ -z "${OMIE_APP_SECRET:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Omie App Secret: ")" OMIE_APP_SECRET
    [[ -z "$OMIE_APP_SECRET" ]] && fail "App Secret obrigatoria."
fi

# Persistir
cat > "$SECRETS_FILE" << EOF
OMIE_APP_KEY=${OMIE_APP_KEY}
OMIE_APP_SECRET=${OMIE_APP_SECRET}
EOF
chmod 600 "$SECRETS_FILE"

# Testar conexao
info "Testando conexao com Omie..."
export OMIE_APP_KEY OMIE_APP_SECRET
if OUTPUT=$(python3 "$SCRIPT_DIR/omie_client.py" resumo_financeiro 2>&1); then
    ok "Conectado ao Omie com sucesso!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique App Key e App Secret."
fi
