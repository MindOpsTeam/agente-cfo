#!/usr/bin/env bash
# doctor.sh — Diagnóstico completo do Agente CFO
# Saída: tabela ASCII de status. Exit 0 = tudo ok. Exit 1 = alguma falha.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

LOG_FILE="$LOG_DIR/doctor.log"
OMIE_SCRIPT="$OMIE_SKILL_PATH/scripts/omie_client.py"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== doctor.sh iniciado em $TIMESTAMP ==="

# ── Helpers ───────────────────────────────────────────────────────────────────
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
# Bug 12b: grep -qi "connected" casava "disconnected" (substring match).
# Fix: check estrito em AUTHENTICATED=true + CONNECTION_STATE=connected|locked_by_other_process.
# "locked_by_other_process" = wacli-sync tem o lock = bom, está conectado.
echo "[1/6] Verificando WhatsApp..."
_wacli_out=$(wacli doctor 2>&1 || true)
if echo "$_wacli_out" | grep -qE 'AUTHENTICATED[[:space:]]+true|"authenticated":[[:space:]]*true'; then
    if echo "$_wacli_out" | grep -qE 'CONNECTION_STATE[[:space:]]+(connected|locked_by_other_process)|"connected":[[:space:]]*true'; then
        register "WhatsApp (wacli)" "$PASS" "conectado"
    else
        register "WhatsApp (wacli)" "$WARN" "autenticado mas desconectado — systemctl status wacli-sync"
    fi
else
    register "WhatsApp (wacli)" "$FAIL" "não autenticado — execute repare.sh"
fi

# ── 2. Omie ERP (ping via resumo_financeiro, timeout 15s) ─────────────────────
echo "[2/6] Verificando Omie ERP..."
if [[ -z "${OMIE_APP_KEY:-}" || -z "${OMIE_APP_SECRET:-}" ]]; then
    register "Omie ERP" "$FAIL" "OMIE_APP_KEY ou OMIE_APP_SECRET não definidos"
else
    if [[ ! -f "$OMIE_SCRIPT" ]]; then
        register "Omie ERP" "$FAIL" "omie_client.py não encontrado em $OMIE_SCRIPT"
    else
        if timeout 15 python3 "$OMIE_SCRIPT" resumo_financeiro > /dev/null 2>&1; then
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

# ── 3. PANEL_TOKEN + conectividade com painel ────────────────────────────────
echo "[3/6] Verificando painel..."
if [[ -z "${PANEL_TOKEN:-}" ]]; then
    register "Painel (PANEL_TOKEN)" "$FAIL" "PANEL_TOKEN não definido no ambiente"
else
    register "Painel (PANEL_TOKEN)" "$PASS" "presente"
fi

# Verificar conectividade com instance-register (HEAD ou GET — apenas checa se responde)
if [[ -n "${PANEL_BASE_URL:-}" ]]; then
    PANEL_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        -X HEAD "${PANEL_BASE_URL}/instance-register" \
        -H "X-Panel-Token: ${PANEL_TOKEN:-}" 2>/dev/null || echo "000")
    if [[ "$PANEL_HTTP" =~ ^(200|204|401|405)$ ]]; then
        register "Painel (instance-register)" "$PASS" "respondendo (HTTP $PANEL_HTTP)"
    elif [[ "$PANEL_HTTP" == "000" ]]; then
        register "Painel (instance-register)" "$FAIL" "timeout ou sem conectividade"
    else
        register "Painel (instance-register)" "$WARN" "HTTP inesperado: $PANEL_HTTP"
    fi
else
    register "Painel (instance-register)" "$WARN" "PANEL_BASE_URL não definido — pulando"
fi

# ── 4. Endpoint /hooks/agent (OpenClaw Gateway na porta 18789) ───────────────
# Bug 12a: corpo vazio {} retorna 400 (body obrigatório); precisamos de um body
#   com "message" + "name" para o endpoint rejeitar por auth (401) e não por body.
echo "[4/6] Verificando /hooks/agent..."
HOOKS_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    -X POST "http://localhost:18789/hooks/agent" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer wrong-token-doctor-healthcheck" \
    -d '{"message":"healthcheck","name":"doctor"}' \
    2>/dev/null || echo "000")
if [[ "$HOOKS_HTTP" == "401" ]]; then
    register "OpenClaw /hooks/agent" "$PASS" "respondendo (401 auth — esperado)"
elif [[ "$HOOKS_HTTP" == "200" ]]; then
    register "OpenClaw /hooks/agent" "$WARN" "respondendo sem auth — verifique hooks.token"
elif [[ "$HOOKS_HTTP" == "000" ]]; then
    register "OpenClaw /hooks/agent" "$FAIL" "não responde — gateway rodando? (porta 18789)"
else
    # Qualquer 4xx/5xx != 000 significa que o endpoint está respondendo
    register "OpenClaw /hooks/agent" "$WARN" "HTTP $HOOKS_HTTP (endpoint responde — verifique hooks.token)"
fi

# ── 5. Webhook receiver legado (porta 8089) — opcional ───────────────────────
echo "[5/6] Verificando webhook receiver legado..."
if curl -fs --max-time 5 "http://127.0.0.1:8089/health" > /dev/null 2>&1; then
    register "Webhook receiver legado (8089)" "$PASS" "respondendo"
else
    register "Webhook receiver legado (8089)" "$WARN" "não está rodando (opcional)"
fi

# ── 6. wacli-inbound listener ────────────────────────────────────────────────
echo "[6/7] Verificando wacli-inbound..."
if systemctl is-active --quiet wacli-inbound 2>/dev/null; then
    register "wacli-inbound listener" "$PASS" "ativo (escutando mensagens do dono)"
else
    register "wacli-inbound listener" "$WARN" "inativo — systemctl start wacli-inbound"
fi

# ── 7. cfo-proactive watcher ─────────────────────────────────────────────────
echo "[7/7] Verificando cfo-proactive watcher..."
if systemctl is-active --quiet cfo-proactive 2>/dev/null; then
    # Verificar quando foi o último ciclo (última linha do log)
    _PROACTIVE_LOG="${HOME}/.agente-cfo/logs/proactive.log"
    _LAST_CYCLE=""
    if [[ -f "$_PROACTIVE_LOG" ]]; then
        _LAST_CYCLE=$(grep "Início do ciclo\|ciclo concluído\|started" "$_PROACTIVE_LOG" 2>/dev/null | tail -1 | cut -c1-19 || echo "")
    fi
    _MSG="ativo"
    [[ -n "$_LAST_CYCLE" ]] && _MSG="ativo — último ciclo: ${_LAST_CYCLE}"
    register "Proactive Watcher (cfo-proactive)" "$PASS" "$_MSG"
else
    register "Proactive Watcher (cfo-proactive)" "$WARN" "inativo — systemctl start cfo-proactive"
fi

# ── Tabela de resultado ───────────────────────────────────────────────────────
echo ""
echo "┌──────────────────────────────────────────────────┬──────────┬──────────────────────────────────────────────┐"
printf "│ %-48s │ %-8s │ %-44s │\n" "Componente" "Status" "Mensagem"
echo "├──────────────────────────────────────────────────┼──────────┼──────────────────────────────────────────────┤"

OVERALL=0
declare -A COMPONENTS=()

for i in "${!CHECK_NAMES[@]}"; do
    name="${CHECK_NAMES[$i]}"
    status="${CHECK_STATUS[$i]}"
    msg="${CHECK_MSGS[$i]}"
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

    # Mapear para chaves do payload do painel
    case "$name" in
        *WhatsApp*)            COMPONENTS["whatsapp"]="${status,,}" ;;
        *Omie*)                COMPONENTS["omie"]="${status,,}" ;;
        *PANEL_TOKEN*)         COMPONENTS["panel_token"]="${status,,}" ;;
        *instance-register*)   COMPONENTS["panel_connect"]="${status,,}" ;;
        */hooks/agent*)        COMPONENTS["hooks_agent"]="${status,,}" ;;
        *Webhook*legado*)      COMPONENTS["webhook_legacy"]="${status,,}" ;;
        *Proactive*)           COMPONENTS["proactive_watcher"]="${status,,}" ;;
    esac
done

echo "└──────────────────────────────────────────────────┴──────────┴──────────────────────────────────────────────┘"
echo ""

if [[ $OVERALL -eq 0 ]]; then
    echo "✅ Sistema operando normalmente."
else
    echo "❌ Uma ou mais verificações falharam. Veja a tabela acima."
fi

# ── Reportar ao painel central ────────────────────────────────────────────────
OVERALL_STR=$([ $OVERALL -eq 0 ] && echo "ok" || echo "fail")
SEVERITY=$([ $OVERALL -eq 0 ] && echo "info" || echo "critical")

PAYLOAD=$(printf '{"overall":"%s","components":{"whatsapp":"%s","omie":"%s","panel_token":"%s","panel_connect":"%s","hooks_agent":"%s","proactive_watcher":"%s"}}' \
    "$OVERALL_STR" \
    "${COMPONENTS[whatsapp]:-unknown}" \
    "${COMPONENTS[omie]:-unknown}" \
    "${COMPONENTS[panel_token]:-unknown}" \
    "${COMPONENTS[panel_connect]:-unknown}" \
    "${COMPONENTS[hooks_agent]:-unknown}" \
    "${COMPONENTS[proactive_watcher]:-unknown}")

_panel_event "doctor" "$SEVERITY" "$PAYLOAD"

echo "=== doctor.sh encerrado — exit $OVERALL ==="
exit $OVERALL
