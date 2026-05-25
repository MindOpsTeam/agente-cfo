#!/usr/bin/env bash
# integrations_health_monthly.sh — Saúde mensal de integrações. Sprint INT-2.
#
# Chama integration-credentials-test para cada skill via painel e reporta resultado.
# Uso: bash integrations_health_monthly.sh
# Cron: "0 9 1 * *" (dia 1 de cada mês às 09:00 America/Sao_Paulo)
# Exit 0 sempre.

set -euo pipefail

ENV_FILE="${HOME}/.agente-cfo/.env"
LOG_FILE="${HOME}/.agente-cfo/logs/integrations-health-monthly.log"
RESULT_FILE="${HOME}/.agente-cfo/logs/integrations-health-monthly-$(date +%Y-%m).json"

mkdir -p "$(dirname "$LOG_FILE")"

[[ -f "$ENV_FILE" ]] && { set -a; source "$ENV_FILE"; set +a; }

PANEL_BASE_URL="${PANEL_BASE_URL:-}"
PANEL_TOKEN="${PANEL_TOKEN:-}"

_log() {
    local msg="$*"
    printf '[%s] %s\n' "$(date +%FT%T)" "$msg" | tee -a "$LOG_FILE"
}

# Skills a testar (todas as 17 integrações gerenciadas)
SKILLS=(
    omie bling contaazul tiny granatum vhsys nibo
    asaas iugu
    hubspot rd-station piperun pipedrive kommo
    mercado-livre nuvemshop
)

_log "=== Iniciando saúde mensal de integrações — $(date +%Y-%m) ==="

RESULTS_JSON="["
SKILLS_OK=()
SKILLS_FAIL=()
SKILLS_SKIP=()
FIRST=true

for skill in "${SKILLS[@]}"; do
    _log "Testando: $skill"

    if [[ -z "$PANEL_BASE_URL" || -z "$PANEL_TOKEN" ]]; then
        _log "  SKIP $skill — PANEL_BASE_URL ou PANEL_TOKEN não definidos"
        SKILLS_SKIP+=("$skill")
        ENTRY="{\"skill\":\"$skill\",\"status\":\"skipped\",\"detail\":\"no panel config\",\"tested_at\":null}"
    else
        # Chama edge fn integration-credentials-test
        RAW_RESP=$(curl -s \
            -X POST "${PANEL_BASE_URL%/}/functions/v1/integration-credentials-test" \
            -H "Authorization: Bearer ${PANEL_TOKEN}" \
            -H "Content-Type: application/json" \
            -d "{\"skill_name\":\"${skill}\"}" \
            --max-time 30 2>/dev/null || echo '{"error":"curl_failed"}')

        # Parseia status da resposta
        STATUS=$(printf '%s' "$RAW_RESP" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read().strip())
    print(d.get('status', 'unknown'))
except Exception:
    print('error')
" 2>/dev/null || echo "error")

        TS_NOW=$(python3 -c "
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat(timespec='seconds'))
" 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)

        _log "  $skill → status=$STATUS"

        # JSON sem aspas no skill (já validado — só alnum/-)
        ENTRY="{\"skill\":\"$skill\",\"status\":\"${STATUS}\",\"tested_at\":\"${TS_NOW}\"}"

        if [[ "$STATUS" == "ok" ]]; then
            SKILLS_OK+=("$skill")
        else
            SKILLS_FAIL+=("$skill")
        fi
    fi

    [[ "$FIRST" == "true" ]] && FIRST=false || RESULTS_JSON+=","
    RESULTS_JSON+="$ENTRY"
done

RESULTS_JSON+="]"

# Salva resultado JSON
printf '%s\n' "$RESULTS_JSON" > "$RESULT_FILE" 2>/dev/null || true

# ── Resumo ────────────────────────────────────────────────────────────────────
echo ""
echo "=== Saúde de Integrações — $(date +%Y-%m) ==="
echo "OK (${#SKILLS_OK[@]}): ${SKILLS_OK[*]:-nenhuma}"
echo "PROBLEMA (${#SKILLS_FAIL[@]}): ${SKILLS_FAIL[*]:-nenhum}"
[[ ${#SKILLS_SKIP[@]} -gt 0 ]] && echo "PULADAS (${#SKILLS_SKIP[@]}): ${SKILLS_SKIP[*]}"
echo "Resultado salvo em: $RESULT_FILE"

_log "Resumo: OK=${#SKILLS_OK[@]} FAIL=${#SKILLS_FAIL[@]} SKIP=${#SKILLS_SKIP[@]}"

# ── Notificação WA/TG se há falhas ───────────────────────────────────────────
if [[ ${#SKILLS_FAIL[@]} -gt 0 ]]; then
    FAIL_LIST="${SKILLS_FAIL[*]}"
    FAIL_COUNT="${#SKILLS_FAIL[@]}"

    MSG="⚠️ *Saúde Mensal de Integrações ($(date +%B/%Y))*

${FAIL_COUNT} integração(ões) com problema: ${FAIL_LIST}

Por favor verifique em Configurações → Integrações no painel e reconecte as integrações afetadas.

_Verificação automática — $(date +"%d/%m/%Y %H:%M")_"

    _log "Enviando notificação de falhas..."

    # Tenta panel_write_event.sh
    PANEL_WRITE="${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/panel_write_event.sh"
    [[ ! -f "$PANEL_WRITE" ]] && PANEL_WRITE="${HOME}/agente-cfo/skills/agente-cfo/scripts/panel_write_event.sh"

    if [[ -f "$PANEL_WRITE" && -n "$PANEL_BASE_URL" && -n "$PANEL_TOKEN" ]]; then
        MSG_JSON=$(printf '%s' "$MSG" | python3 -c "
import sys,json
print(json.dumps(sys.stdin.read()))
" 2>/dev/null || echo '"Falhas nas integrações"')
        bash "$PANEL_WRITE" "integrations_health_alert" "$MSG_JSON" 2>>"$LOG_FILE" || \
            _log "WARN: panel_write_event.sh falhou"
        _log "Notificação enviada"
    else
        _log "SKIP notificação — panel_write_event.sh não encontrado ou panel não configurado"
    fi
fi

_log "=== Saúde mensal concluída ==="
exit 0
