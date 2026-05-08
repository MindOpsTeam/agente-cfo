#!/usr/bin/env bash
# connect.sh — Configura credenciais para a skill granatum
set -euo pipefail

SKILL_NAME="granatum"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/granatum_client.py" get_balance >/dev/null 2>&1; then
        ok "Ja conectado ao Granatum! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Granatum"
echo ""

if [[ -z "${GRANATUM_ACCESS_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Token de acesso Granatum (Configuracoes > Minha Empresa > API): ")" GRANATUM_ACCESS_TOKEN
    [[ -z "$GRANATUM_ACCESS_TOKEN" ]] && fail "Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
GRANATUM_ACCESS_TOKEN=${GRANATUM_ACCESS_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export GRANATUM_ACCESS_TOKEN
if OUTPUT=$(python3 "$SCRIPT_DIR/granatum_client.py" get_balance 2>&1); then
    ok "Conectado ao Granatum com sucesso!"
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o token."
fi
