#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="pipedrive"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
STAGES_FILE="${HOME}/.openclaw/secrets/pipedrive_stages.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SECRETS_FILE" ]] && source "$SECRETS_FILE" 2>/dev/null || true

echo "=== doctor.sh [${SKILL_NAME}] ==="

if [[ -z "${PIPEDRIVE_API_TOKEN:-}" ]]; then
    echo "❌ ${SKILL_NAME}: PIPEDRIVE_API_TOKEN ausente"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi

if [[ -z "${PIPEDRIVE_COMPANY_DOMAIN:-}" ]]; then
    echo "❌ ${SKILL_NAME}: PIPEDRIVE_COMPANY_DOMAIN ausente"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi
echo "✅ Credenciais presentes (dominio: ${PIPEDRIVE_COMPANY_DOMAIN})"

if python3 "$SCRIPT_DIR/pipedrive_client.py" company_info >/dev/null 2>&1; then
    echo "✅ ${SKILL_NAME}: API acessivel"
else
    echo "❌ ${SKILL_NAME}: falha na conexao — verifique token e dominio"
    exit 1
fi

if [[ -f "$STAGES_FILE" ]]; then
    STAGE_COUNT=$(python3 -c "import json; d=json.load(open('$STAGES_FILE')); print(len(d))" 2>/dev/null || echo "?")
    echo "✅ Cache de stages presente (${STAGE_COUNT} stages)"
else
    echo "⚠️  Cache de stages ausente — sera criado no primeiro uso"
fi

exit 0
