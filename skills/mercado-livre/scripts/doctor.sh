#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="mercado-livre"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SECRETS_FILE" ]] && source "$SECRETS_FILE" 2>/dev/null || true

echo "=== doctor.sh [${SKILL_NAME}] ==="

if [[ -z "${ML_CLIENT_ID:-}" ]] || [[ -z "${ML_CLIENT_SECRET:-}" ]]; then
    echo "❌ ${SKILL_NAME}: credenciais OAuth ausentes (ML_CLIENT_ID / ML_CLIENT_SECRET)"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi

if [[ -z "${ML_ACCESS_TOKEN:-}" ]] || [[ -z "${ML_REFRESH_TOKEN:-}" ]]; then
    echo "❌ ${SKILL_NAME}: tokens ausentes"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi
echo "✅ Credenciais presentes (user_id: ${ML_USER_ID:-N/A})"

EXPIRY="${ML_TOKEN_EXPIRY:-0}"
NOW=$(python3 -c "import time; print(int(time.time()))")
if [[ "$NOW" -gt "$EXPIRY" ]]; then
    echo "⚠️  Token expirado — sera renovado automaticamente no proximo uso"
else
    TTL=$(( EXPIRY - NOW ))
    echo "✅ Token valido por mais ${TTL}s"
fi

if python3 "$SCRIPT_DIR/mercado_livre_client.py" company_info >/dev/null 2>&1; then
    echo "✅ ${SKILL_NAME}: API acessivel"
    exit 0
else
    echo "❌ ${SKILL_NAME}: falha na conexao"
    exit 1
fi
