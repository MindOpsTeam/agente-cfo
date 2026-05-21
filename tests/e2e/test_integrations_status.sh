#!/usr/bin/env bash
# test_integrations_status.sh — Smoke test de integrações plug-and-play
# Verifica estrutura dos artefatos da Sprint INTEGRATIONS-1.
# Retorna: 0 se PASS, 1 se falhar.

set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0
FAIL=0

check() {
  local desc="$1" result="$2"
  if [[ "$result" == "OK" ]]; then
    printf '  ✅ %s\n' "$desc"
    PASS=$((PASS+1))
  else
    printf '  ❌ %s — %s\n' "$desc" "$result"
    FAIL=$((FAIL+1))
  fi
}

echo "=== Smoke Test: Integrações Plug-and-Play (Sprint INTEGRATIONS-1) ==="
echo ""

# ── integrations_status.sh ──────────────────────────────────────────────────
echo "--- integrations_status.sh ---"
INTEG_STATUS="$REPO_DIR/skills/agente-cfo/scripts/integrations_status.sh"
[[ -f "$INTEG_STATUS" ]] && check "integrations_status.sh existe" "OK" || \
  check "integrations_status.sh existe" "FAIL"
[[ -f "$INTEG_STATUS" ]] && bash -n "$INTEG_STATUS" 2>/dev/null && \
  check "integrations_status.sh sintaxe bash OK" "OK" || \
  check "integrations_status.sh sintaxe bash OK" "FAIL"
[[ -f "$INTEG_STATUS" ]] && grep -q 'has_secret\|SECRETS_DIR\|openclaw.*mcp' "$INTEG_STATUS" && \
  check "integrations_status.sh consulta secrets + MCPs" "OK" || \
  check "integrations_status.sh consulta secrets + MCPs" "FAIL"
[[ -f "$INTEG_STATUS" ]] && grep -q 'dashboard_only\|--format\|FORMAT' "$INTEG_STATUS" && \
  check "integrations_status.sh suporta --format" "OK" || \
  check "integrations_status.sh suporta --format" "FAIL"
[[ -f "$INTEG_STATUS" ]] && grep -q 'TELEGRAM_BOT_TOKEN\|TG_STATUS' "$INTEG_STATUS" && \
  check "integrations_status.sh verifica canal Telegram" "OK" || \
  check "integrations_status.sh verifica canal Telegram" "FAIL"

echo ""
echo "--- conversa.md — intent de status das integrações ---"
CONVERSA="$REPO_DIR/skills/agente-cfo/prompts/conversa.md"
grep -q 'integrations_status.sh\|integrações estão ativas\|status das integr' "$CONVERSA" && \
  check "conversa.md tem intent integrations_status" "OK" || \
  check "conversa.md tem intent integrations_status" "FAIL"

echo ""
echo "--- Rota Telegram no painel ---"
TG_ROUTE="$REPO_DIR/painel-front/src/routes/_authenticated/settings_.telegram.tsx"
[[ -f "$TG_ROUTE" ]] && check "settings_.telegram.tsx existe" "OK" || \
  check "settings_.telegram.tsx existe" "FAIL"
[[ -f "$TG_ROUTE" ]] && grep -q 'telegram_bots\|bot_username\|bot_token' "$TG_ROUTE" && \
  check "settings_.telegram.tsx usa telegram_bots" "OK" || \
  check "settings_.telegram.tsx usa telegram_bots" "FAIL"
[[ -f "$TG_ROUTE" ]] && grep -q 'BotFather\|getMe\|webhook' "$TG_ROUTE" && \
  check "settings_.telegram.tsx tem guia BotFather" "OK" || \
  check "settings_.telegram.tsx tem guia BotFather" "FAIL"
[[ -f "$TG_ROUTE" ]] && grep -q 'receives_marcos_chat\|webhook_secret' "$TG_ROUTE" && \
  check "settings_.telegram.tsx configura receives_marcos_chat" "OK" || \
  check "settings_.telegram.tsx configura receives_marcos_chat" "FAIL"

echo ""
echo "--- Sidebar com canal Telegram ---"
SIDEBAR="$REPO_DIR/painel-front/src/components/app-sidebar.tsx"
grep -q 'Telegram\|telegram\|MessageCircle' "$SIDEBAR" && \
  check "app-sidebar.tsx tem link Telegram" "OK" || \
  check "app-sidebar.tsx tem link Telegram" "FAIL"
grep -q 'channelItems\|Canais\|channels' "$SIDEBAR" && \
  check "app-sidebar.tsx tem seção Canais" "OK" || \
  check "app-sidebar.tsx tem seção Canais" "FAIL"

echo ""
echo "--- integrations-spec.ts — todas as 17 skills ---"
SPEC="$REPO_DIR/painel-front/src/lib/integrations-spec.ts"
[[ -f "$SPEC" ]] && check "integrations-spec.ts existe" "OK" || \
  check "integrations-spec.ts existe" "FAIL"
for skill in omie bling tiny granatum vhsys nibo contaazul hubspot rd-station piperun \
             pipedrive kommo asaas iugu mercado-livre nuvemshop supabase; do
  [[ -f "$SPEC" ]] && grep -q "\"$skill\"" "$SPEC" && \
    check "integrations-spec: $skill" "OK" || \
    check "integrations-spec: $skill" "FAIL"
done

echo ""
echo "--- Documentação ---"
[[ -f "$REPO_DIR/docs/INTEGRACOES-PLUG-AND-PLAY.md" ]] && \
  check "docs/INTEGRACOES-PLUG-AND-PLAY.md existe" "OK" || \
  check "docs/INTEGRACOES-PLUG-AND-PLAY.md existe" "FAIL"
grep -q 'Fluxo E2E\|API Key\|OAuth' "$REPO_DIR/docs/INTEGRACOES-PLUG-AND-PLAY.md" 2>/dev/null && \
  check "docs/INTEGRACOES-PLUG-AND-PLAY.md tem fluxo E2E" "OK" || \
  check "docs/INTEGRACOES-PLUG-AND-PLAY.md tem fluxo E2E" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
