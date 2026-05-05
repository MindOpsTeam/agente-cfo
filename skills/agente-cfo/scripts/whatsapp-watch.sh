#!/usr/bin/env bash
# whatsapp-watch.sh — Monitor de conexão WhatsApp via polling de `wacli doctor`
# Modo padrão: "once" (para uso com cron). Modo "loop": contínuo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

LOG_FILE="$LOG_DIR/whatsapp-watch.log"
STATE_FILE="$STATE_DIR/whatsapp-watch-state.json"

POLL_INTERVAL="${WHATSAPP_WATCH_INTERVAL:-1800}"
WATCH_MODE="${WHATSAPP_WATCH_MODE:-once}"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== whatsapp-watch.sh iniciado em $TIMESTAMP (modo: $WATCH_MODE) ==="

# ── Checar status WhatsApp ────────────────────────────────────────────────────
check_whatsapp() {
    local status="unknown"

    if wacli_json=$(wacli doctor --json 2>/dev/null); then
        status=$(echo "$wacli_json" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('status', 'unknown'))
except:
    print('parse_error')
" 2>/dev/null || echo "parse_error")
    else
        wacli_text=$(wacli doctor 2>&1 || true)
        if echo "$wacli_text" | grep -qi "connected\|ok\|pareado\|logged in"; then
            status="ok"
        elif echo "$wacli_text" | grep -qi "not logged\|logged out\|QR\|disconnected\|desconectado"; then
            status="disconnected"
        fi
    fi

    echo "$status"
}

# ── Salvar estado ─────────────────────────────────────────────────────────────
save_state() {
    local status="$1" alerted="$2"
    cat > "$STATE_FILE" << EOF
{"status":"$status","last_check":"$TIMESTAMP","alerted":$alerted}
EOF
}

# ── Verificar estado anterior ─────────────────────────────────────────────────
was_alerted=false
if [[ -f "$STATE_FILE" ]]; then
    prev=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    print('true' if d.get('alerted', False) else 'false')
except:
    print('false')
" 2>/dev/null || echo "false")
    was_alerted="$prev"
fi

# ── Check principal ───────────────────────────────────────────────────────────
run_check() {
    local check_time
    check_time=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$check_time] Verificando WhatsApp..."

    WA_STATUS=$(check_whatsapp)
    echo "Status: $WA_STATUS"

    case "$WA_STATUS" in
        "ok"|"connected"|"logged_in")
            save_state "connected" "false"
            if [[ "$was_alerted" == "true" ]]; then
                _panel_event "whatsapp_reconnected" "info" \
                    "{\"detail\":\"reconectado detectado pelo watcher\"}"
                was_alerted=false
                echo "✅ WhatsApp reconectado — painel notificado."
            else
                echo "✅ WhatsApp conectado."
            fi
            ;;
        "disconnected"|"logged_out"|"qr_required")
            if [[ "$was_alerted" == "false" ]]; then
                echo "⚠️ WhatsApp DESCONECTADO — notificando painel."
                save_state "disconnected" "true"
                _panel_event "whatsapp_disconnected" "warn" \
                    "{\"reason\":\"$WA_STATUS\",\"detail\":\"detectado pelo watcher\"}"
                was_alerted=true
                echo "AÇÃO NECESSÁRIA: execute repare.sh no servidor."
            else
                echo "⚠️ Ainda desconectado (alerta já enviado). AÇÃO: execute repare.sh"
            fi
            ;;
        *)
            echo "⚠️ Status indeterminado ($WA_STATUS) — sem alerta (evita falso-positivo)."
            ;;
    esac
}

# ── Loop ou execução única ────────────────────────────────────────────────────
if [[ "$WATCH_MODE" == "loop" ]]; then
    echo "Modo loop: verificação a cada ${POLL_INTERVAL}s. Ctrl+C para parar."
    while true; do
        run_check
        echo "Próxima verificação em ${POLL_INTERVAL}s..."
        sleep "$POLL_INTERVAL"
    done
else
    run_check
fi

echo "=== whatsapp-watch.sh encerrado ==="
