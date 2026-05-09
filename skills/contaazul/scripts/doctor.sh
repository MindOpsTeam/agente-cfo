#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="contaazul"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SECRETS_FILE" ]] && source "$SECRETS_FILE" 2>/dev/null || true

echo "=== doctor.sh [${SKILL_NAME}] ==="

if [[ -z "${CONTAAZUL_CLIENT_ID:-}" ]] || [[ -z "${CONTAAZUL_CLIENT_SECRET:-}" ]]; then
    echo "❌ ${SKILL_NAME}: credenciais OAuth ausentes (CONTAAZUL_CLIENT_ID / CONTAAZUL_CLIENT_SECRET)"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi

if [[ -z "${CONTAAZUL_ACCESS_TOKEN:-}" ]] || [[ -z "${CONTAAZUL_REFRESH_TOKEN:-}" ]]; then
    echo "❌ ${SKILL_NAME}: tokens ausentes (CONTAAZUL_ACCESS_TOKEN / CONTAAZUL_REFRESH_TOKEN)"
    echo "   Execute: bash $(dirname "$0")/connect.sh"
    exit 1
fi
echo "✅ Credenciais presentes"

# Verificar expiração do token
EXPIRY="${CONTAAZUL_TOKEN_EXPIRY:-0}"
NOW=$(python3 -c "import time; print(int(time.time()))")
if [[ "$NOW" -gt "$EXPIRY" ]]; then
    echo "⚠️  Access token expirado — sera renovado automaticamente no proximo uso"
else
    TTL=$(( EXPIRY - NOW ))
    echo "✅ Token valido por mais ${TTL}s"
fi

if python3 "$SCRIPT_DIR/contaazul_client.py" get_balance >/dev/null 2>&1; then
    echo "✅ ${SKILL_NAME}: API acessivel (get_balance ok)"
    exit 0
elif python3 "$SCRIPT_DIR/contaazul_client.py" company_info >/dev/null 2>&1; then
    echo "✅ ${SKILL_NAME}: API acessivel (company_info ok, sem contas financeiras?)"
    exit 0
else
    echo "❌ ${SKILL_NAME}: falha na conexao — reconecte com bash connect.sh --force"
    exit 1
fi
