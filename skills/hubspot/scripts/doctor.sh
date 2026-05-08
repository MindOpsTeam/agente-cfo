#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="hubspot"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SECRETS_FILE" ]] && source "$SECRETS_FILE" 2>/dev/null || true

echo "=== doctor.sh [${SKILL_NAME}] ==="

if [[ -z "${HUBSPOT_TOKEN:-}" ]]; then
    echo "❌ ${SKILL_NAME}: credenciais ausentes (HUBSPOT_TOKEN)"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi
echo "✅ Credenciais presentes"

if python3 "$SCRIPT_DIR/hubspot_client.py" company_info >/dev/null 2>&1; then
    echo "✅ ${SKILL_NAME}: API acessivel"
else
    echo "❌ ${SKILL_NAME}: falha na conexao"
    exit 1
fi

# Verificar cache de stages
if [[ -f "${HOME}/.openclaw/secrets/hubspot_stages.json" ]]; then
    echo "✅ Cache de stages presente"
else
    echo "⚠️  Cache de stages ausente — sera criado no primeiro uso"
fi

exit 0
