#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="vhsys"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/vhsys_client.py" get_balance >/dev/null 2>&1; then
        ok "Ja conectado ao VHSYS! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais VHSYS"
echo ""

if [[ -z "${VHSYS_ACCESS_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Access Token VHSYS (Integracoes > API): ")" VHSYS_ACCESS_TOKEN
    [[ -z "$VHSYS_ACCESS_TOKEN" ]] && fail "Access Token obrigatorio."
fi

if [[ -z "${VHSYS_SECRET_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Secret Access Token VHSYS: ")" VHSYS_SECRET_TOKEN
    [[ -z "$VHSYS_SECRET_TOKEN" ]] && fail "Secret Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
VHSYS_ACCESS_TOKEN=${VHSYS_ACCESS_TOKEN}
VHSYS_SECRET_TOKEN=${VHSYS_SECRET_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export VHSYS_ACCESS_TOKEN VHSYS_SECRET_TOKEN
if OUTPUT=$(python3 "$SCRIPT_DIR/vhsys_client.py" get_balance 2>&1); then
    ok "Conectado ao VHSYS com sucesso!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique os tokens."
fi
