#!/usr/bin/env bash
# test_ship1_distribution.sh — Smoke tests Sprint SHIP-1 (Launch público).
# Verifica todos os entregáveis de distribuição sem chamadas de rede reais.
# Exit 0 = all pass, Exit 1 = failures.
#
# Uso: bash tests/e2e/test_ship1_distribution.sh
# Sprint SHIP-1 — 2026-05-25

set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0; FAIL=0; TOTAL=0

_check() {
    local desc="$1" result="$2" detail="${3:-}"
    TOTAL=$((TOTAL+1))
    if [[ "$result" == "pass" ]]; then
        PASS=$((PASS+1)); printf '  %b✓%b %s\n' "$GREEN" "$NC" "$desc"
    else
        FAIL=$((FAIL+1)); printf '  %b✗%b %s\n' "$RED" "$NC" "$desc"
        [[ -n "$detail" ]] && printf '      %b→ %s%b\n' "$YELLOW" "$detail" "$NC"
    fi
}

_section() { printf '\n%b== %s ==%b\n' "$CYAN" "$1" "$NC"; }

printf '\n%b╔══════════════════════════════════════════════════════╗%b\n' "$CYAN" "$NC"
printf '%b║   SHIP-1 Distribution Smoke Tests                   ║%b\n' "$CYAN" "$NC"
printf '%b╚══════════════════════════════════════════════════════╝%b\n\n' "$CYAN" "$NC"

# ─────────────────────────────────────────────────────────────────────────────
_section "1. Edge fn report-issue"
# ─────────────────────────────────────────────────────────────────────────────

REPORT_FN="${REPO_ROOT}/painel-front/supabase/functions/report-issue/index.ts"

if [[ -f "$REPORT_FN" ]]; then
    _check "report-issue/index.ts existe" "pass"
else
    _check "report-issue/index.ts existe" "fail" "não encontrado: $REPORT_FN"
fi

if [[ -f "$REPORT_FN" ]]; then
    # Verifica estrutura da edge fn
    grep -q "verify_jwt\|Authorization\|auth.getUser\|JWT" "$REPORT_FN" 2>/dev/null && \
        _check "report-issue: requer JWT (auth)" "pass" || \
        _check "report-issue: requer JWT (auth)" "fail"

    grep -q "GITHUB_REPORT_ISSUE_TOKEN" "$REPORT_FN" 2>/dev/null && \
        _check "report-issue: usa GITHUB_REPORT_ISSUE_TOKEN" "pass" || \
        _check "report-issue: usa GITHUB_REPORT_ISSUE_TOKEN" "fail"

    grep -q "sanitize\|REDACTED\|SENSITIVE" "$REPORT_FN" 2>/dev/null && \
        _check "report-issue: sanitiza dados sensíveis" "pass" || \
        _check "report-issue: sanitiza dados sensíveis" "fail"

    grep -q "rate.limit\|rateLimit\|checkRateLimit\|429\|report_issues_log" "$REPORT_FN" 2>/dev/null && \
        _check "report-issue: implementa rate limiting" "pass" || \
        _check "report-issue: implementa rate limiting" "fail"

    grep -q "github.com/repos\|MindOpsTeam/agente-cfo/issues" "$REPORT_FN" 2>/dev/null && \
        _check "report-issue: envia para GitHub Issues" "pass" || \
        _check "report-issue: envia para GitHub Issues" "fail"

    grep -q "include_telemetry\|telemetry\|collectTelemetry" "$REPORT_FN" 2>/dev/null && \
        _check "report-issue: suporta include_telemetry" "pass" || \
        _check "report-issue: suporta include_telemetry" "fail"

    grep -q "html_url\|issue_url" "$REPORT_FN" 2>/dev/null && \
        _check "report-issue: retorna issue_url no response" "pass" || \
        _check "report-issue: retorna issue_url no response" "fail"
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "2. test_client_full_journey.sh (Playwright)"
# ─────────────────────────────────────────────────────────────────────────────

JOURNEY="${REPO_ROOT}/tests/e2e/test_client_full_journey.sh"

if [[ -f "$JOURNEY" ]]; then
    _check "test_client_full_journey.sh existe" "pass"
else
    _check "test_client_full_journey.sh existe" "fail" "não encontrado: $JOURNEY"
fi

if [[ -f "$JOURNEY" ]]; then
    bash -n "$JOURNEY" 2>/dev/null && \
        _check "test_client_full_journey.sh sintaxe bash válida" "pass" || \
        _check "test_client_full_journey.sh sintaxe bash válida" "fail"

    grep -q "playwright\|Playwright" "$JOURNEY" 2>/dev/null && \
        _check "journey: usa Playwright" "pass" || \
        _check "journey: usa Playwright" "fail"

    grep -q "screenshot\|Screenshot" "$JOURNEY" 2>/dev/null && \
        _check "journey: tira screenshots" "pass" || \
        _check "journey: tira screenshots" "fail"

    grep -q "settings\|whatsapp\|telegram\|CHAN-1" "$JOURNEY" 2>/dev/null && \
        _check "journey: verifica features CHAN-1 (whatsapp/telegram)" "pass" || \
        _check "journey: verifica features CHAN-1" "fail"

    grep -q "install\|onboarding\|dashboard" "$JOURNEY" 2>/dev/null && \
        _check "journey: cobre telas principais (install/onboarding/dashboard)" "pass" || \
        _check "journey: cobre telas principais" "fail"
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "3. generate_demo_video.sh"
# ─────────────────────────────────────────────────────────────────────────────

DEMO="${REPO_ROOT}/tests/e2e/generate_demo_video.sh"

if [[ -f "$DEMO" ]]; then
    _check "generate_demo_video.sh existe" "pass"
else
    _check "generate_demo_video.sh existe" "fail" "não encontrado: $DEMO"
fi

if [[ -f "$DEMO" ]]; then
    bash -n "$DEMO" 2>/dev/null && \
        _check "generate_demo_video.sh sintaxe bash válida" "pass" || \
        _check "generate_demo_video.sh sintaxe bash válida" "fail"

    grep -q "ffmpeg" "$DEMO" 2>/dev/null && \
        _check "demo: usa ffmpeg para MP4" "pass" || \
        _check "demo: usa ffmpeg para MP4" "fail"

    grep -q "html\|HTML\|fallback" "$DEMO" 2>/dev/null && \
        _check "demo: tem fallback HTML quando ffmpeg ausente" "pass" || \
        _check "demo: tem fallback HTML quando ffmpeg ausente" "fail"

    grep -q "demo.mp4\|demo\.gif" "$DEMO" 2>/dev/null && \
        _check "demo: produz docs/demo.mp4 ou docs/demo.gif" "pass" || \
        _check "demo: produz docs/demo.mp4 ou docs/demo.gif" "fail"
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "4. docs/LAUNCH-FINAL.md"
# ─────────────────────────────────────────────────────────────────────────────

LAUNCH="${REPO_ROOT}/docs/LAUNCH-FINAL.md"

if [[ -f "$LAUNCH" ]]; then
    _check "LAUNCH-FINAL.md existe" "pass"
else
    _check "LAUNCH-FINAL.md existe" "fail" "não encontrado: $LAUNCH"
fi

if [[ -f "$LAUNCH" ]]; then
    grep -q "GITHUB_REPORT_ISSUE_TOKEN" "$LAUNCH" 2>/dev/null && \
        _check "LAUNCH-FINAL.md: menciona GITHUB_REPORT_ISSUE_TOKEN" "pass" || \
        _check "LAUNCH-FINAL.md: menciona GITHUB_REPORT_ISSUE_TOKEN" "fail"

    grep -q "update-remix-url.sh" "$LAUNCH" 2>/dev/null && \
        _check "LAUNCH-FINAL.md: menciona update-remix-url.sh" "pass" || \
        _check "LAUNCH-FINAL.md: menciona update-remix-url.sh" "fail"

    grep -q "generate_demo_video\|demo.mp4\|demo.mp4" "$LAUNCH" 2>/dev/null && \
        _check "LAUNCH-FINAL.md: menciona geração do vídeo demo" "pass" || \
        _check "LAUNCH-FINAL.md: menciona geração do vídeo demo" "fail"

    # Conta itens de checklist
    CHECKLIST_COUNT=$(grep -c '^\- \[ \]' "$LAUNCH" 2>/dev/null || echo 0)
    if [[ "$CHECKLIST_COUNT" -ge 10 ]]; then
        _check "LAUNCH-FINAL.md: checklist completo (${CHECKLIST_COUNT} itens)" "pass"
    else
        _check "LAUNCH-FINAL.md: checklist completo" "fail" "apenas $CHECKLIST_COUNT itens (esperado ≥10)"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "5. docs/SPRINT-SHIP-1-LOVABLE-PROMPT.md"
# ─────────────────────────────────────────────────────────────────────────────

LOVABLE="${REPO_ROOT}/docs/SPRINT-SHIP-1-LOVABLE-PROMPT.md"

if [[ -f "$LOVABLE" ]]; then
    _check "SPRINT-SHIP-1-LOVABLE-PROMPT.md existe" "pass"
else
    _check "SPRINT-SHIP-1-LOVABLE-PROMPT.md existe" "fail" "não encontrado: $LOVABLE"
fi

if [[ -f "$LOVABLE" ]]; then
    grep -q "ReportIssueModal\|report-issue-modal" "$LOVABLE" 2>/dev/null && \
        _check "prompt Lovable: referencia ReportIssueModal" "pass" || \
        _check "prompt Lovable: referencia ReportIssueModal" "fail"

    grep -q "HelpCircle\|botão.*?\|\"?\"" "$LOVABLE" 2>/dev/null && \
        _check "prompt Lovable: referencia botão '?'" "pass" || \
        _check "prompt Lovable: referencia botão '?'" "fail"

    grep -q "report-issue\|functions.invoke" "$LOVABLE" 2>/dev/null && \
        _check "prompt Lovable: referencia edge fn report-issue" "pass" || \
        _check "prompt Lovable: referencia edge fn report-issue" "fail"

    grep -q "report_issues_log" "$LOVABLE" 2>/dev/null && \
        _check "prompt Lovable: inclui migration report_issues_log" "pass" || \
        _check "prompt Lovable: inclui migration report_issues_log" "fail"
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "6. install/update-remix-url.sh"
# ─────────────────────────────────────────────────────────────────────────────

# Verifica no monorepo agente-cfo (não no painel-front)
UPDATE_REMIX=""
if [[ -f "${REPO_ROOT}/install/update-remix-url.sh" ]]; then
    UPDATE_REMIX="${REPO_ROOT}/install/update-remix-url.sh"
elif [[ -f "${REPO_ROOT}/painel-front/install/update-remix-url.sh" ]]; then
    UPDATE_REMIX="${REPO_ROOT}/painel-front/install/update-remix-url.sh"
fi

if [[ -n "$UPDATE_REMIX" ]]; then
    _check "update-remix-url.sh existe" "pass"
    bash -n "$UPDATE_REMIX" 2>/dev/null && \
        _check "update-remix-url.sh sintaxe bash válida" "pass" || \
        _check "update-remix-url.sh sintaxe bash válida" "fail"
    [[ -x "$UPDATE_REMIX" ]] && \
        _check "update-remix-url.sh é executável" "pass" || \
        _check "update-remix-url.sh é executável" "fail" "chmod +x $UPDATE_REMIX"
else
    _check "update-remix-url.sh existe" "fail" "não encontrado em install/"
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "7. docs/screenshots (artefatos visuais)"
# ─────────────────────────────────────────────────────────────────────────────

SCREENSHOTS="${REPO_ROOT}/docs/screenshots"
if [[ -d "$SCREENSHOTS" ]]; then
    _check "docs/screenshots/ existe" "pass"
    COUNT=$(ls "$SCREENSHOTS"/*.png 2>/dev/null | wc -l | tr -d ' ' || echo 0)
    if [[ "$COUNT" -ge 5 ]]; then
        _check "docs/screenshots/ tem screenshots ($COUNT PNGs)" "pass"
    else
        _check "docs/screenshots/ tem screenshots" "fail" "apenas $COUNT PNGs (esperado ≥5)"
    fi
else
    _check "docs/screenshots/ existe" "fail"
fi

JOURNEY_SS="${REPO_ROOT}/docs/screenshots/journey"
if [[ -d "$JOURNEY_SS" ]]; then
    _check "docs/screenshots/journey/ existe (diretório SHIP-1)" "pass"
else
    _check "docs/screenshots/journey/ existe" "fail" "crie: mkdir -p docs/screenshots/journey"
fi

# ─────────────────────────────────────────────────────────────────────────────
_section "8. Anti-regressão — pipeline + sprints anteriores intactos"
# ─────────────────────────────────────────────────────────────────────────────

# Scripts críticos
CRITICAL_SCRIPTS=(
    "${REPO_ROOT}/skills/agente-cfo/scripts/erp_gateway.py"
    "${REPO_ROOT}/skills/agente-cfo/scripts/erp_sync.py"
    "${REPO_ROOT}/skills/agente-cfo/scripts/heartbeat.sh"
    "${REPO_ROOT}/skills/agente-cfo/scripts/admin_action.sh"
)
for f in "${CRITICAL_SCRIPTS[@]}"; do
    if [[ -f "$f" ]]; then
        _check "$(basename "$f") intacto" "pass"
    else
        _check "$(basename "$f") intacto" "fail" "não encontrado: $f"
    fi
done

# CHAN-1 entregáveis intactos
CHAN1_FILES=(
    "${REPO_ROOT}/skills/evolution-api/scripts/whatsapp_pair_new.sh"
    "${REPO_ROOT}/skills/evolution-api/scripts/whatsapp_pair_status.sh"
    "${REPO_ROOT}/docs/SPRINT-CHAN-1-LOVABLE-PROMPT.md"
)
for f in "${CHAN1_FILES[@]}"; do
    [[ -f "$f" ]] && _check "CHAN-1: $(basename "$f") intacto" "pass" || \
        _check "CHAN-1: $(basename "$f") intacto" "fail"
done

# INT-2 entregáveis intactos
INT2_FILES=(
    "${REPO_ROOT}/skills/agente-cfo/scripts/oauth_refresh_daemon.py"
    "${REPO_ROOT}/skills/agente-cfo/scripts/integrations_health_monthly.sh"
    "${REPO_ROOT}/docs/SPRINT-INT-2-LOVABLE-PROMPT.md"
)
for f in "${INT2_FILES[@]}"; do
    [[ -f "$f" ]] && _check "INT-2: $(basename "$f") intacto" "pass" || \
        _check "INT-2: $(basename "$f") intacto" "fail"
done

# Edge fns críticas do painel
PANEL_FNS=(incoming-message hooks-dedup-check cfo-write-event telegram-webhook)
for fn in "${PANEL_FNS[@]}"; do
    DIR="${REPO_ROOT}/painel-front/supabase/functions/${fn}"
    [[ -d "$DIR" ]] && _check "edge fn $fn intacta" "pass" || \
        _check "edge fn $fn intacta" "fail"
done

# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"
printf 'SHIP-1 Smoke: %b%d/%d PASS%b' "$GREEN" "$PASS" "$TOTAL" "$NC"
[[ $FAIL -gt 0 ]] && printf ' | %b%d FAIL%b' "$RED" "$FAIL" "$NC"
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
