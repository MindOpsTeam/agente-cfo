#!/usr/bin/env bash
# _emit_alerta_enviado.sh — Emite evento alerta_enviado no painel após wacli send real
# Uso: _emit_alerta_enviado.sh <prompt_name> <wacli_exit_code>
#
# Chamado pelo agente OpenClaw nos prompts alerta_manha / alerta_tarde
# DEPOIS de executar wacli send text, passando o exit code real do wacli.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

if [[ $# -lt 2 ]]; then
    echo "Uso: $0 <prompt_name> <wacli_exit_code>" >&2
    exit 1
fi

PROMPT_NAME="$1"
WACLI_EXIT="$2"

if [[ "$WACLI_EXIT" == "0" ]]; then
    SEVERITY="info"
    STATUS="ok"
else
    SEVERITY="error"
    STATUS="fail"
fi

_panel_event "alerta_enviado" "$SEVERITY" \
    "{\"prompt\":\"$PROMPT_NAME\",\"status\":\"$STATUS\",\"mode\":\"agent\",\"wacli_exit\":$WACLI_EXIT}"

echo "_emit_alerta_enviado: evento alerta_enviado[$STATUS] emitido para prompt=$PROMPT_NAME"
