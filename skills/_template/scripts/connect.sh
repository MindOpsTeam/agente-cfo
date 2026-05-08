#!/usr/bin/env bash
# connect.sh — Configura credenciais para a skill <nome>
# Uso: bash connect.sh [--non-interactive]
set -euo pipefail

SKILL_NAME="<nome>"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[${SKILL_NAME}]${NC} $*"; }

mkdir -p "$(dirname "$SECRETS_FILE")"

# Verificar se ja esta conectado
if [[ -f "$SECRETS_FILE" ]]; then
    source "$SECRETS_FILE" 2>/dev/null || true
    # TODO: testar conexao com credenciais existentes
    if python3 "$SCRIPT_DIR/<nome>_client.py" company_info >/dev/null 2>&1; then
        ok "Ja conectado! Use 'bash connect.sh --force' para reconectar."
        exit 0
    fi
fi

# TODO: pedir credenciais via read -rp ou aceitar via env var
# TODO: testar conexao
# TODO: persistir em $SECRETS_FILE com chmod 600
# TODO: confirmar com nome da empresa
