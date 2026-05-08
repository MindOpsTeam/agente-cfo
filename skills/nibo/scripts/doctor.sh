#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="nibo"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SECRETS_FILE" ]] && source "$SECRETS_FILE" 2>/dev/null || true

echo "=== doctor.sh [${SKILL_NAME}] ==="

if [[ -z "${NIBO_API_TOKEN:-}" ]]; then
    echo "❌ ${SKILL_NAME}: credenciais ausentes (NIBO_API_TOKEN)"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi
echo "✅ Credenciais presentes"

if python3 "$SCRIPT_DIR/nibo_client.py" get_balance >/dev/null 2>&1; then
    echo "✅ ${SKILL_NAME}: API acessivel"
    exit 0
else
    echo "❌ ${SKILL_NAME}: falha na conexao"
    exit 1
fi
