#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="nibo"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/nibo_client.py" get_balance >/dev/null 2>&1; then
        ok "Ja conectado ao Nibo! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Nibo"
echo ""

if [[ -z "${NIBO_API_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Token Nibo (Empresa > Configuracoes > API): ")" NIBO_API_TOKEN
    [[ -z "$NIBO_API_TOKEN" ]] && fail "Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
NIBO_API_TOKEN=${NIBO_API_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export NIBO_API_TOKEN
if OUTPUT=$(python3 "$SCRIPT_DIR/nibo_client.py" get_balance 2>&1); then
    ok "Conectado ao Nibo com sucesso!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o token."
fi
