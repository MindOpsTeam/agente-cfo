#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="tiny"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/tiny_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado ao Tiny! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

info "Configurando credenciais Tiny ERP"
echo ""

if [[ -z "${TINY_TOKEN:-}" ]]; then
    read -rp "$(echo -e "${CYAN}?${NC} Token Tiny (Configuracoes > Integracoes > Token da API v2): ")" TINY_TOKEN
    [[ -z "$TINY_TOKEN" ]] && fail "Token obrigatorio."
fi

cat > "$SECRETS_FILE" << EOF
TINY_TOKEN=${TINY_TOKEN}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexao..."
export TINY_TOKEN
if OUTPUT=$(python3 "$SCRIPT_DIR/tiny_client.py" company_info 2>&1); then
    ok "Conectado ao Tiny com sucesso!"
    echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Empresa: {d.get(\"name\",\"?\")}')" 2>/dev/null || true
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique o token."
fi
