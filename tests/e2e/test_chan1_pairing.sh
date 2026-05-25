#!/usr/bin/env bash
# test_chan1_pairing.sh — Smoke tests do Sprint CHAN-1 (pareamento WhatsApp + Telegram).
#
# Verifica entregáveis backend sem fazer chamadas de rede reais.
# Saída compatível com run_all.sh (exit 0 = pass, exit 1 = fail).
#
# Sprint CHAN-1 — 2026-05-25
#
# Uso:
#   bash tests/e2e/test_chan1_pairing.sh
#   bash tests/e2e/test_chan1_pairing.sh --verbose

set -euo pipefail

VERBOSE=0
[[ "${1:-}" == "--verbose" ]] && VERBOSE=1

# ── Cores ──────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

# ── Caminhos base ─────────────────────────────────────────────────────────────
REPO_ROOT="${BASH_SOURCE[0]%/tests/e2e/*}"
# Sobe dois níveis se rodado de dentro de tests/e2e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

PAIR_SCRIPT="${REPO_ROOT}/skills/evolution-api/scripts/whatsapp_pair_new.sh"
STATUS_SCRIPT="${REPO_ROOT}/skills/evolution-api/scripts/whatsapp_pair_status.sh"
ADMIN_SCRIPT="${REPO_ROOT}/skills/agente-cfo/scripts/admin_action.sh"
MIGRATION="${REPO_ROOT}/painel-front/supabase/migrations/20260525000001_whatsapp_qr_storage.sql"
LOVABLE_DOC="${REPO_ROOT}/docs/SPRINT-CHAN-1-LOVABLE-PROMPT.md"

# ── Contadores ────────────────────────────────────────────────────────────────
PASS=0; FAIL=0; TOTAL=0

_check() {
    local desc="$1"
    local result="$2"   # "pass" | "fail"
    local detail="${3:-}"
    TOTAL=$((TOTAL + 1))
    if [[ "$result" == "pass" ]]; then
        PASS=$((PASS + 1))
        printf '  %b✓%b %s\n' "$GREEN" "$NC" "$desc"
    else
        FAIL=$((FAIL + 1))
        printf '  %b✗%b %s\n' "$RED" "$NC" "$desc"
        [[ -n "$detail" ]] && printf '      %b→ %s%b\n' "$YELLOW" "$detail" "$NC"
    fi
}

_section() { printf '\n%b== %s ==%b\n' "$YELLOW" "$1" "$NC"; }

# ─────────────────────────────────────────────────────────────────────────────
_section "1. whatsapp_pair_new.sh — existência e sintaxe"
# ─────────────────────────────────────────────────────────────────────────────

if [[ -f "$PAIR_SCRIPT" ]]; then
    _check "whatsapp_pair_new.sh existe" "pass"
else
    _check "whatsapp_pair_new.sh existe" "fail" "não encontrado: $PAIR_SCRIPT"
fi

if [[ -f "$PAIR_SCRIPT" ]]; then
    if bash -n "$PAIR_SCRIPT" 2>/dev/null; then
        _check "whatsapp_pair_new.sh sintaxe bash válida" "pass"
    else
        _check "whatsapp_pair_new.sh sintaxe bash válida" "fail" "bash -n falhou"
    fi
fi

if [[ -f "$PAIR_SCRIPT" ]]; then
    # Verifica args obrigatórios
    if grep -q "\-\-instance" "$PAIR_SCRIPT"; then
        _check "whatsapp_pair_new.sh aceita --instance arg" "pass"
    else
        _check "whatsapp_pair_new.sh aceita --instance arg" "fail" "flag --instance não encontrada"
    fi

    # Verifica que lê Evolution API vars
    if grep -q "EVOLUTION_API_URL" "$PAIR_SCRIPT" && grep -q "EVOLUTION_API_KEY" "$PAIR_SCRIPT"; then
        _check "whatsapp_pair_new.sh referencia EVOLUTION_API_URL e EVOLUTION_API_KEY" "pass"
    else
        _check "whatsapp_pair_new.sh referencia EVOLUTION_API_URL e EVOLUTION_API_KEY" "fail"
    fi

    # Verifica que lê .env
    if grep -q "agente-cfo/.env" "$PAIR_SCRIPT"; then
        _check "whatsapp_pair_new.sh lê ~/.agente-cfo/.env" "pass"
    else
        _check "whatsapp_pair_new.sh lê ~/.agente-cfo/.env" "fail"
    fi

    # Verifica upload Supabase Storage
    if grep -q "storage/v1/object" "$PAIR_SCRIPT"; then
        _check "whatsapp_pair_new.sh faz upload pro Supabase Storage" "pass"
    else
        _check "whatsapp_pair_new.sh faz upload pro Supabase Storage" "fail"
    fi

    # Verifica upsert whatsapp_instances
    if grep -q "whatsapp_instances" "$PAIR_SCRIPT"; then
        _check "whatsapp_pair_new.sh atualiza whatsapp_instances" "pass"
    else
        _check "whatsapp_pair_new.sh atualiza whatsapp_instances" "fail"
    fi

    # Verifica output JSON
    if grep -q '"success"' "$PAIR_SCRIPT"; then
        _check "whatsapp_pair_new.sh retorna JSON com 'success'" "pass"
    else
        _check "whatsapp_pair_new.sh retorna JSON com 'success'" "fail"
    fi

    # Teste de validação de nome inválido (sem rede)
    VALIDATION_ERR=$(bash "$PAIR_SCRIPT" --instance "nome inválido com espaços" 2>&1 || true)
    if echo "$VALIDATION_ERR" | grep -q "inválido\|invalido\|success.*false\|error"; then
        _check "whatsapp_pair_new.sh rejeita nome com espaços" "pass"
    else
        _check "whatsapp_pair_new.sh rejeita nome com espaços" "fail" "esperado erro, got: ${VALIDATION_ERR:0:80}"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "2. whatsapp_pair_status.sh — existência e sintaxe"
# ─────────────────────────────────────────────────────────────────────────────

if [[ -f "$STATUS_SCRIPT" ]]; then
    _check "whatsapp_pair_status.sh existe" "pass"
else
    _check "whatsapp_pair_status.sh existe" "fail" "não encontrado: $STATUS_SCRIPT"
fi

if [[ -f "$STATUS_SCRIPT" ]]; then
    if bash -n "$STATUS_SCRIPT" 2>/dev/null; then
        _check "whatsapp_pair_status.sh sintaxe bash válida" "pass"
    else
        _check "whatsapp_pair_status.sh sintaxe bash válida" "fail" "bash -n falhou"
    fi
fi

if [[ -f "$STATUS_SCRIPT" ]]; then
    if grep -q "\-\-instance" "$STATUS_SCRIPT"; then
        _check "whatsapp_pair_status.sh aceita --instance arg" "pass"
    else
        _check "whatsapp_pair_status.sh aceita --instance arg" "fail"
    fi

    if grep -q "connectionState" "$STATUS_SCRIPT"; then
        _check "whatsapp_pair_status.sh chama /instance/connectionState" "pass"
    else
        _check "whatsapp_pair_status.sh chama /instance/connectionState" "fail"
    fi

    # Verifica que retorna JSON com "state"
    if grep -q '"state"' "$STATUS_SCRIPT"; then
        _check "whatsapp_pair_status.sh retorna JSON com 'state'" "pass"
    else
        _check "whatsapp_pair_status.sh retorna JSON com 'state'" "fail"
    fi

    # Erro sem --instance
    NO_INSTANCE=$(bash "$STATUS_SCRIPT" 2>&1 || true)
    if echo "$NO_INSTANCE" | grep -qE '"state"|obrigatorio|unknown'; then
        _check "whatsapp_pair_status.sh falha graciosamente sem --instance" "pass"
    else
        _check "whatsapp_pair_status.sh falha graciosamente sem --instance" "fail" "got: ${NO_INSTANCE:0:80}"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "3. admin_action.sh — whitelist com novas actions"
# ─────────────────────────────────────────────────────────────────────────────

if [[ -f "$ADMIN_SCRIPT" ]]; then
    _check "admin_action.sh existe" "pass"
else
    _check "admin_action.sh existe" "fail" "não encontrado: $ADMIN_SCRIPT"
fi

if [[ -f "$ADMIN_SCRIPT" ]]; then
    if bash -n "$ADMIN_SCRIPT" 2>/dev/null; then
        _check "admin_action.sh sintaxe bash válida" "pass"
    else
        _check "admin_action.sh sintaxe bash válida" "fail"
    fi

    if grep -q "whatsapp_pair_new" "$ADMIN_SCRIPT"; then
        _check "admin_action.sh tem action whatsapp_pair_new" "pass"
    else
        _check "admin_action.sh tem action whatsapp_pair_new" "fail"
    fi

    if grep -q "whatsapp_pair_status" "$ADMIN_SCRIPT"; then
        _check "admin_action.sh tem action whatsapp_pair_status" "pass"
    else
        _check "admin_action.sh tem action whatsapp_pair_status" "fail"
    fi

    # Verifica que actions antigas NÃO foram removidas
    REQUIRED_ACTIONS=(
        "openclaw_config_get"
        "openclaw_config_set"
        "openclaw_status"
        "systemctl_restart"
        "service_logs"
        "mcp_sync_now"
        "self_update"
    )
    for action in "${REQUIRED_ACTIONS[@]}"; do
        if grep -q "\"$action\"" "$ADMIN_SCRIPT" || grep -q "$action)" "$ADMIN_SCRIPT"; then
            _check "admin_action.sh preserva action existente: $action" "pass"
        else
            _check "admin_action.sh preserva action existente: $action" "fail" "action removida ou não encontrada"
        fi
    done

    # Testa nova action via JSON: action inválida deve retornar erro com lista de válidas
    UNKNOWN_OUT=$(echo '{"action":"unknown_test_xyz"}' | bash "$ADMIN_SCRIPT" 2>&1 || true)
    if echo "$UNKNOWN_OUT" | grep -q "whatsapp_pair_new\|whatsapp_pair_status"; then
        _check "admin_action.sh lista novas actions na msg de erro de action desconhecida" "pass"
    else
        _check "admin_action.sh lista novas actions na msg de erro de action desconhecida" "fail" \
               "esperado whatsapp_pair_new/status na listagem. got: ${UNKNOWN_OUT:0:200}"
    fi

    # Testa que instance_name inválido é rejeitado
    INVALID_OUT=$(echo '{"action":"whatsapp_pair_new","instance_name":"inj; rm -rf /"}' | bash "$ADMIN_SCRIPT" 2>&1 || true)
    if echo "$INVALID_OUT" | grep -qE '"ok":false|inválido|invalido'; then
        _check "admin_action.sh rejeita instance_name com injection" "pass"
    else
        _check "admin_action.sh rejeita instance_name com injection" "fail" \
               "esperado erro de validação. got: ${INVALID_OUT:0:100}"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "4. Migration SQL — whatsapp_qr_storage"
# ─────────────────────────────────────────────────────────────────────────────

if [[ -f "$MIGRATION" ]]; then
    _check "migration 20260525000001_whatsapp_qr_storage.sql existe" "pass"
else
    _check "migration 20260525000001_whatsapp_qr_storage.sql existe" "fail" "não encontrado: $MIGRATION"
fi

if [[ -f "$MIGRATION" ]]; then
    if grep -q "qr_code_b64" "$MIGRATION"; then
        _check "migration adiciona coluna qr_code_b64" "pass"
    else
        _check "migration adiciona coluna qr_code_b64" "fail"
    fi

    if grep -q "whatsapp_instances" "$MIGRATION"; then
        _check "migration referencia tabela whatsapp_instances" "pass"
    else
        _check "migration referencia tabela whatsapp_instances" "fail"
    fi

    if grep -q "IF NOT EXISTS" "$MIGRATION"; then
        _check "migration usa IF NOT EXISTS (seguro para re-run)" "pass"
    else
        _check "migration usa IF NOT EXISTS (seguro para re-run)" "fail"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "5. Documentação — SPRINT-CHAN-1-LOVABLE-PROMPT.md"
# ─────────────────────────────────────────────────────────────────────────────

if [[ -f "$LOVABLE_DOC" ]]; then
    _check "docs/SPRINT-CHAN-1-LOVABLE-PROMPT.md existe" "pass"
else
    _check "docs/SPRINT-CHAN-1-LOVABLE-PROMPT.md existe" "fail" "não encontrado: $LOVABLE_DOC"
fi

if [[ -f "$LOVABLE_DOC" ]]; then
    # Verifica que tem 3 prompts
    PROMPT_COUNT=$(grep -cE '^## Prompt [0-9]' "$LOVABLE_DOC" 2>/dev/null || echo "0")
    if [[ "$PROMPT_COUNT" -ge 3 ]]; then
        _check "doc tem 3 prompts Lovable (## Prompt 1/2/3)" "pass"
    else
        _check "doc tem 3 prompts Lovable (## Prompt 1/2/3)" "fail" "encontrado $PROMPT_COUNT prompt(s)"
    fi

    if grep -q "telegram-webhook" "$LOVABLE_DOC"; then
        _check "Prompt 1: referencia telegram-webhook (deploy)" "pass"
    else
        _check "Prompt 1: referencia telegram-webhook (deploy)" "fail"
    fi

    if grep -q "whatsapp-pair-start" "$LOVABLE_DOC"; then
        _check "Prompt 2: referencia edge fn whatsapp-pair-start" "pass"
    else
        _check "Prompt 2: referencia edge fn whatsapp-pair-start" "fail"
    fi

    if grep -q "telegram-webhook-register" "$LOVABLE_DOC"; then
        _check "Prompt 2: referencia edge fn telegram-webhook-register" "pass"
    else
        _check "Prompt 2: referencia edge fn telegram-webhook-register" "fail"
    fi

    if grep -q "qr_code_b64\|QR" "$LOVABLE_DOC"; then
        _check "Prompt 3: referencia polling QR code na UI" "pass"
    else
        _check "Prompt 3: referencia polling QR code na UI" "fail"
    fi

    if grep -q "banner\|Banner\|offline\|Offline" "$LOVABLE_DOC"; then
        _check "Prompt 3: referencia banner offline no dashboard" "pass"
    else
        _check "Prompt 3: referencia banner offline no dashboard" "fail"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "6. Anti-regressão — pipeline ativo intacto"
# ─────────────────────────────────────────────────────────────────────────────

# Verifica que scripts críticos do pipeline não foram tocados
CRITICAL_SCRIPTS=(
    "${REPO_ROOT}/skills/agente-cfo/scripts/erp_gateway.py"
    "${REPO_ROOT}/skills/agente-cfo/scripts/erp_sync.py"
    "${REPO_ROOT}/skills/agente-cfo/scripts/heartbeat.sh"
)
for script in "${CRITICAL_SCRIPTS[@]}"; do
    if [[ -f "$script" ]]; then
        _check "$(basename "$script") intacto (existe)" "pass"
    else
        _check "$(basename "$script") intacto (existe)" "fail" "não encontrado: $script"
    fi
done

# Verifica edge fns do pipeline no painel-front
PANEL_FN_DIR="${REPO_ROOT}/painel-front/supabase/functions"
# Nota: whatsapp-evolution-webhook e channel-send vivem na VPS (não são edge fns do painel)
CRITICAL_FNS=("incoming-message" "hooks-dedup-check" "cfo-write-event" "telegram-webhook")
for fn in "${CRITICAL_FNS[@]}"; do
    if [[ -d "${PANEL_FN_DIR}/${fn}" ]]; then
        _check "edge fn $fn intacta (dir existe)" "pass"
    else
        _check "edge fn $fn intacta (dir existe)" "fail" "dir não encontrado: ${PANEL_FN_DIR}/${fn}"
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"
printf 'CHAN-1 Smoke: %b%d/%d PASS%b' "$GREEN" "$PASS" "$TOTAL" "$NC"
if [[ $FAIL -gt 0 ]]; then
    printf ' | %b%d FAIL%b' "$RED" "$FAIL" "$NC"
fi
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
