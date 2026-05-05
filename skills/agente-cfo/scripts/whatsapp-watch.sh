#!/usr/bin/env bash
# whatsapp-watch.sh — Monitor de conexão WhatsApp via polling de `wacli doctor`
# Detecta QR expirado e alerta o painel central.
# Rode como processo background ou cron separado (ex: a cada 30 min).
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
LOG_DIR="${CFO_LOG_DIR:-$HOME/.agente-cfo/logs}"
STATE_DIR="${CFO_STATE_DIR:-$HOME/.agente-cfo}"
LOG_FILE="$LOG_DIR/whatsapp-watch.log"
STATE_FILE="$STATE_DIR/whatsapp-watch-state.json"

# Intervalo de polling quando rodando em loop contínuo (segundos)
POLL_INTERVAL="${WHATSAPP_WATCH_INTERVAL:-1800}"  # padrão: 30 minutos
# Modo: "once" (executa uma vez, para uso com cron) ou "loop" (contínuo)
WATCH_MODE="${WHATSAPP_WATCH_MODE:-once}"

mkdir -p "$LOG_DIR" "$STATE_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== whatsapp-watch.sh iniciado em $TIMESTAMP (modo: $WATCH_MODE) ==="

# ── Função: checar status WhatsApp ───────────────────────────────────────────
check_whatsapp() {
    local status="unknown"
    local detail=""

    # Tentar com --json primeiro
    if wacli_json=$(wacli doctor --json 2>/dev/null); then
        status=$(echo "$wacli_json" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('status', 'unknown'))
except:
    print('parse_error')
" 2>/dev/null || echo "parse_error")
        detail="$wacli_json"
    else
        # Fallback: parsear saída texto
        wacli_text=$(wacli doctor 2>&1 || true)
        if echo "$wacli_text" | grep -qi "connected\|ok\|pareado\|logged in"; then
            status="ok"
        elif echo "$wacli_text" | grep -qi "not logged\|logged out\|QR\|disconnected\|desconectado"; then
            status="disconnected"
        else
            status="unknown"
        fi
        detail="$wacli_text"
    fi

    echo "$status"
}

# ── Função: alertar desconexão ────────────────────────────────────────────────
alert_disconnected() {
    local reason="${1:-desconhecido}"

    echo "⚠️ WhatsApp DESCONECTADO — motivo: $reason"

    # Salvar estado
    cat > "$STATE_FILE" << EOF
{
  "status": "disconnected",
  "reason": "$reason",
  "last_check": "$TIMESTAMP",
  "alerted": true
}
EOF

    # Reportar ao painel central
    if [[ -n "${PANEL_WEBHOOK_URL:-}" ]]; then
        curl -s --max-time 10 -X POST "$PANEL_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -H "X-License: ${LICENSE_KEY:-}" \
            -d "{\"event\":\"whatsapp_disconnected\",\"reason\":\"$reason\",\"tenant\":\"${TENANT_ID:-unknown}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
            > /dev/null 2>&1 || true
        echo "Painel notificado."
    fi

    # Log no terminal (não envia WhatsApp porque WhatsApp está offline)
    echo "AÇÃO NECESSÁRIA: execute repare.sh no servidor para reconectar."
    echo "  bash ~/.openclaw/workspace/skills/agente-cfo/scripts/repare.sh"
}

# ── Função: registrar status OK ──────────────────────────────────────────────
record_ok() {
    cat > "$STATE_FILE" << EOF
{
  "status": "connected",
  "last_check": "$TIMESTAMP",
  "alerted": false
}
EOF
    echo "✅ WhatsApp conectado."
}

# ── Verificar estado anterior (evitar spam de alertas) ───────────────────────
was_alerted=false
if [[ -f "$STATE_FILE" ]]; then
    prev_alerted=$(python3 -c "
import sys, json
try:
    d = json.load(open('$STATE_FILE'))
    print('true' if d.get('alerted', False) else 'false')
except:
    print('false')
" 2>/dev/null || echo "false")
    was_alerted="$prev_alerted"
fi

# ── Execução principal ────────────────────────────────────────────────────────
run_check() {
    local check_time
    check_time=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$check_time] Verificando WhatsApp..."

    WA_STATUS=$(check_whatsapp)
    echo "Status: $WA_STATUS"

    case "$WA_STATUS" in
        "ok"|"connected"|"logged_in")
            record_ok
            # Se estava alertado e voltou, notificar recuperação
            if [[ "$was_alerted" == "true" ]]; then
                if [[ -n "${PANEL_WEBHOOK_URL:-}" ]]; then
                    curl -s --max-time 10 -X POST "$PANEL_WEBHOOK_URL" \
                        -H "Content-Type: application/json" \
                        -H "X-License: ${LICENSE_KEY:-}" \
                        -d "{\"event\":\"whatsapp_reconnected\",\"tenant\":\"${TENANT_ID:-unknown}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
                        > /dev/null 2>&1 || true
                fi
                was_alerted=false
                echo "✅ WhatsApp reconectado — painel notificado."
            fi
            ;;
        "disconnected"|"logged_out"|"qr_required")
            if [[ "$was_alerted" == "false" ]]; then
                alert_disconnected "$WA_STATUS"
                was_alerted=true
            else
                echo "⚠️ Ainda desconectado (alerta já enviado). AÇÃO: execute repare.sh"
            fi
            ;;
        "parse_error"|"unknown")
            echo "⚠️ Status indeterminado ($WA_STATUS). Verificar manualmente: wacli doctor"
            # Não alerta em status desconhecido para evitar falso-positivo
            ;;
        *)
            echo "⚠️ Status inesperado: $WA_STATUS"
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
    # Modo padrão: executa uma vez (para uso com cron externo)
    run_check
fi

echo "=== whatsapp-watch.sh encerrado ==="
