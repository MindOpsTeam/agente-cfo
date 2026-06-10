#!/usr/bin/env bash
# connect.sh — configura a API Key do Holdprint (Holdworks) ERP.
# Token pessoal: Holdprint → Ajustes → API → Copiar. NÃO há sandbox.
set -euo pipefail

SKILL_NAME="holdprint"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $*"; }
fail() { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

mkdir -p "$(dirname "$SECRETS_FILE")"

# Já conectado? (a menos que --force)
if [[ -f "$SECRETS_FILE" ]] && [[ "${1:-}" != "--force" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    if python3 "$SCRIPT_DIR/holdprint_client.py" company_info >/dev/null 2>&1; then
        ok "Já conectado ao Holdprint! Use 'bash connect.sh --force' para reconfigurar."
        exit 0
    fi
fi

info "Configurando API Key do Holdprint (Holdworks)"
echo ""
echo "Onde obter: no Holdprint, menu lateral → Ajustes → API → botão Copiar."
echo "(Se necessário, 'Gerar novo token' — isso invalida o anterior.)"
echo ""

# A credencial pode vir do ambiente (sincronizada do painel via Vault) ou ser pedida.
if [[ -z "${HOLDPRINT_API_KEY:-}" ]]; then
    if [[ -r /dev/tty ]]; then
        read -rp "$(echo -e "${CYAN}?${NC} API Key do Holdprint: ")" HOLDPRINT_API_KEY </dev/tty
    fi
    [[ -z "${HOLDPRINT_API_KEY:-}" ]] && fail "API Key obrigatória."
fi

cat > "$SECRETS_FILE" <<EOF
HOLDPRINT_API_KEY=${HOLDPRINT_API_KEY}
EOF
chmod 600 "$SECRETS_FILE"

info "Testando conexão com https://api.holdworks.ai ..."
export HOLDPRINT_API_KEY
if OUTPUT=$(python3 "$SCRIPT_DIR/holdprint_client.py" company_info 2>&1); then
    ok "Conectado ao Holdprint com sucesso!"
    echo "$OUTPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Clientes cadastrados: {d.get(\"customers_total\",\"?\")}')" 2>/dev/null || true
else
    echo "$OUTPUT"
    fail "Falha ao conectar. Verifique a API Key (Holdprint → Ajustes → API)."
fi
