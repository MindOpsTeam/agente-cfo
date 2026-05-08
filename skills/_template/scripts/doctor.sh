#!/usr/bin/env bash
# doctor.sh — Health check da skill <nome>
set -euo pipefail

SKILL_NAME="<nome>"
SECRETS_FILE="${HOME}/.openclaw/secrets/${SKILL_NAME}.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$SECRETS_FILE" ]] && source "$SECRETS_FILE" 2>/dev/null || true

echo "=== doctor.sh [${SKILL_NAME}] ==="

# 1. Credenciais presentes?
# TODO: checar variaveis obrigatorias

# 2. Conexao OK?
if python3 "$SCRIPT_DIR/<nome>_client.py" company_info >/dev/null 2>&1; then
    echo "✅ ${SKILL_NAME}: API acessivel"
    exit 0
else
    echo "❌ ${SKILL_NAME}: falha na conexao"
    exit 1
fi
