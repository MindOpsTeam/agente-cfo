#!/usr/bin/env bash
# heartbeat.sh — Envia heartbeat ao painel central (POST /heartbeat)
# Chamado pelo cron */5 * * * * registrado pelo setup.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

LOG_FILE="$LOG_DIR/heartbeat.log"

# Heartbeat é silencioso — só loga se falhar
_panel_heartbeat

# Log compacto (1 linha por execução, sem exec redirect para não inflar o log)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] heartbeat ok — instance=${INSTANCE_ID:-unset}" >> "$LOG_FILE"
