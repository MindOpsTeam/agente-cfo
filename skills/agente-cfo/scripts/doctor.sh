#!/usr/bin/env bash
# doctor.sh — Diagnóstico completo do Agente CFO
# Saída: tabela ASCII de status. Exit 0 = tudo ok. Exit 1 = alguma falha.
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
LOG_DIR="${CFO_LOG_DIR:-$HOME/.agente-cfo/logs}"
STATE_DIR="${CFO_STATE_DIR:-$HOME/.agente-cfo}"
OMIE_SKILL_PATH="${OMIE_SKILL_PATH:-$HOME/.openclaw/workspace/skills/omie}"
LOG_FILE="$LOG_DIR/doctor.log"

mkdir -p "$LOG_DIR" "$STATE_DIR"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== doctor.sh iniciado em $TIMESTAMP ==="

# ── Helpers ───────────────────────────────────────────────────────────────────
COL_W=42
PASS="OK"
FAIL="FALHA"
WARN="AVISO"

declare -a CHECK_NAMES=()
declare -a CHECK_STATUS=()
declare -a CHECK_MSGS=()

register() {
    local name="$1" status="$2" msg="$3"
    CHECK_NAMES+=("$name")
    CHECK_STATUS+=("$status")
    CHECK_MSGS+=("$msg")
}

# ── 1. WhatsApp (wacli doctor) ────────────────────────────────────────────────
echo "[1/4] Verificando WhatsApp..."
if wacli_out=$(wacli doctor --json 2>/dev/null); then
    wa_status=$(echo "$wacli_out" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")
    if [[ "$wa_status" == "ok" || "$wa_status" == "connected" ]]; then
        register "WhatsApp (wacli)" "$PASS" "conectado"
    else
        register "WhatsApp (wacli)" "$FAIL" "status: $wa_status — execute repare.sh"
    fi
else
    # wacli doctor sem --json pode retornar exit != 0 quando desconectado
    if wacli doctor 2>&1 | grep -qi "connected\|ok\|pareado\|logged"; then
        register "WhatsApp (wacli)" "$PASS" "conectado"
    else
        register "WhatsApp (wacli)" "$FAIL" "wacli doctor falhou — execute repare.sh"
    fi
fi

# ── 2. Omie ERP (ping via resumo_financeiro, timeout 15s) ─────────────────────
echo "[2/4] Verificando Omie ERP..."
if [[ -z "${OMIE_APP_KEY:-}" || -z "${OMIE_APP_SECRET:-}" ]]; then
    register "Omie ERP" "$FAIL" "OMIE_APP_KEY ou OMIE_APP_SECRET não definidos"
else
    omie_script="$OMIE_SKILL_PATH/scripts/omie_client.py"
    if [[ ! -f "$omie_script" ]]; then
        register "Omie ERP" "$FAIL" "omie_client.py não encontrado em $omie_script"
    else
        if timeout 15 python3 "$omie_script" resumo_financeiro > /dev/null 2>&1; then
            register "Omie ERP" "$PASS" "API acessível"
        else
            EXIT_CODE=$?
            if [[ $EXIT_CODE -eq 124 ]]; then
                register "Omie ERP" "$FAIL" "timeout após 15s — verifique conectividade"
            else
                register "Omie ERP" "$FAIL" "erro HTTP (exit $EXIT_CODE) — verifique credenciais"
            fi
        fi
    fi
fi

# ── 3. LICENSE_KEY presente ───────────────────────────────────────────────────
echo "[3/4] Verificando licença..."
if [[ -n "${LICENSE_KEY:-}" ]]; then
    # Validação básica de formato (prefixo lk_)
    if [[ "$LICENSE_KEY" == lk_* ]]; then
        register "Licença (LICENSE_KEY)" "$PASS" "presente e formato válido"
    else
        register "Licença (LICENSE_KEY)" "$WARN" "presente mas formato inesperado"
    fi
else
    register "Licença (LICENSE_KEY)" "$FAIL" "LICENSE_KEY não definido no ambiente"
fi

# ── 4. Webhook receiver (porta 8089) ─────────────────────────────────────────
echo "[4/4] Verificando webhook receiver..."
if curl -fs --max-time 5 "http://127.0.0.1:8089/health" > /dev/null 2>&1; then
    register "Webhook receiver (8089)" "$PASS" "respondendo"
else
    register "Webhook receiver (8089)" "$WARN" "não está rodando (opcional para operação básica)"
fi

# ── Tabela de resultado ───────────────────────────────────────────────────────
echo ""
echo "┌──────────────────────────────────────────────────┬──────────┬──────────────────────────────────────────────┐"
printf "│ %-48s │ %-8s │ %-44s │\n" "Componente" "Status" "Mensagem"
echo "├──────────────────────────────────────────────────┼──────────┼──────────────────────────────────────────────┤"

OVERALL=0
for i in "${!CHECK_NAMES[@]}"; do
    name="${CHECK_NAMES[$i]}"
    status="${CHECK_STATUS[$i]}"
    msg="${CHECK_MSGS[$i]}"

    # Truncar strings longas para caber na tabela
    name_fmt="${name:0:48}"
    msg_fmt="${msg:0:44}"

    if [[ "$status" == "$FAIL" ]]; then
        OVERALL=1
        icon="❌"
    elif [[ "$status" == "$WARN" ]]; then
        icon="⚠️ "
    else
        icon="✅"
    fi

    printf "│ %-48s │ %s %-6s │ %-44s │\n" "$name_fmt" "$icon" "$status" "$msg_fmt"
done

echo "└──────────────────────────────────────────────────┴──────────┴──────────────────────────────────────────────┘"
echo ""

if [[ $OVERALL -eq 0 ]]; then
    echo "✅ Sistema operando normalmente."
else
    echo "❌ Uma ou mais verificações falharam. Veja a tabela acima."
fi

# ── Reportar ao painel central (tolerante a falha) ────────────────────────────
if [[ -n "${PANEL_WEBHOOK_URL:-}" ]]; then
    STATUS_JSON=$(printf '{"event":"doctor","overall":"%s","tenant":"%s","timestamp":"%s"}' \
        "$([ $OVERALL -eq 0 ] && echo 'ok' || echo 'fail')" \
        "${TENANT_ID:-unknown}" \
        "$TIMESTAMP")
    curl -s --max-time 10 -X POST "$PANEL_WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -H "X-License: ${LICENSE_KEY:-}" \
        -d "$STATUS_JSON" > /dev/null 2>&1 || true
fi

echo "=== doctor.sh encerrado — exit $OVERALL ==="
exit $OVERALL
