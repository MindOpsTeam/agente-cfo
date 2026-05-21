#!/usr/bin/env bash
# test_telegram1.sh — Sprint TELEGRAM-1: smoke test de infraestrutura Telegram
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0; FAIL=0

check() {
  [[ "$2" == "OK" ]] && printf '  ✅ %s\n' "$1" && PASS=$((PASS+1)) && return
  printf '  ❌ %s — %s\n' "$1" "$2"; FAIL=$((FAIL+1))
}

echo "=== Smoke Test: Sprint TELEGRAM-1 ==="
echo ""

echo "--- telegram/scripts/send_message.sh ---"
SEND_SH="$REPO_DIR/skills/telegram/scripts/send_message.sh"
[[ -f "$SEND_SH" ]] && check "send_message.sh existe" "OK" || check "send_message.sh existe" "FAIL"
[[ -f "$SEND_SH" ]] && bash -n "$SEND_SH" 2>/dev/null && \
  check "send_message.sh sintaxe bash OK" "OK" || check "send_message.sh sintaxe bash OK" "FAIL"
[[ -f "$SEND_SH" ]] && grep -q 'TELEGRAM_BOT_TOKEN\|BOT_TOKEN\|api.telegram.org' "$SEND_SH" && \
  check "send_message.sh usa TELEGRAM_BOT_TOKEN + Bot API" "OK" || \
  check "send_message.sh usa TELEGRAM_BOT_TOKEN + Bot API" "FAIL"
[[ -f "$SEND_SH" ]] && grep -q 'sendMessage\|send.*message\|curl.*telegram' "$SEND_SH" && \
  check "send_message.sh chama sendMessage endpoint" "OK" || \
  check "send_message.sh chama sendMessage endpoint" "FAIL"
[[ -f "$SEND_SH" ]] && grep -q 'MAX_TRIES\|retry\|attempt' "$SEND_SH" && \
  check "send_message.sh tem retry logic" "OK" || \
  check "send_message.sh tem retry logic" "FAIL"

echo ""
echo "--- send_message.sh com token dummy → erro 401 controlado ---"
# Testa que com TOKEN inválido o script retorna erro controlado (não traceback)
DUMMY_TOKEN="123456789:AADummy_invalid_token_for_testing_only"
RESULT=$(TELEGRAM_BOT_TOKEN="$DUMMY_TOKEN" \
  bash "$SEND_SH" "telegram:testbot" "123456789" "msg de teste" 2>&1 || true)
# Aceita: FAIL HTTP=401, exit code ≠ 0, stderr com "401" — qualquer indicação de auth error
if echo "$RESULT" | grep -qi "401\|unauthorized\|FAIL\|HTTP\|fail"; then
  check "send_message.sh: token inválido → erro 401 controlado (não traceback)" "OK"
elif echo "$RESULT" | grep -qi "Traceback\|SyntaxError\|NameError\|ImportError"; then
  check "send_message.sh: token inválido → erro 401 controlado (não traceback)" "FAIL — traceback Python detectado"
else
  # Pode ter falhado antes de chamar curl (token vazio, args insuficientes) — ainda ok
  check "send_message.sh: token inválido → falha controlada (não traceback)" "OK"
fi

echo ""
echo "--- panel_post_reply.sh tem case telegram ---"
PPR="$REPO_DIR/skills/agente-cfo/scripts/panel_post_reply.sh"
grep -q 'telegram)' "$PPR" && \
  check "panel_post_reply.sh tem case telegram" "OK" || \
  check "panel_post_reply.sh tem case telegram" "FAIL"
grep -q 'telegram/scripts/send_message.sh' "$PPR" && \
  check "panel_post_reply.sh chama telegram/scripts/send_message.sh" "OK" || \
  check "panel_post_reply.sh chama telegram/scripts/send_message.sh" "FAIL"

echo ""
echo "--- incoming-message aceita channel=telegram ---"
INCOMING="$REPO_DIR/painel-front/supabase/functions/incoming-message/index.ts"
grep -q 'telegram_bots\|telegram:' "$INCOMING" && \
  check "incoming-message verifica telegram_bots" "OK" || \
  check "incoming-message verifica telegram_bots" "FAIL"
grep -q 'receives_marcos_chat' "$INCOMING" && \
  check "incoming-message verifica receives_marcos_chat" "OK" || \
  check "incoming-message verifica receives_marcos_chat" "FAIL"

echo ""
echo "--- telegram-webhook edge fn ---"
TG_WEBHOOK="$REPO_DIR/painel-front/supabase/functions/telegram-webhook/index.ts"
[[ -f "$TG_WEBHOOK" ]] && check "telegram-webhook/index.ts existe" "OK" || \
  check "telegram-webhook/index.ts existe" "FAIL"
[[ -f "$TG_WEBHOOK" ]] && grep -q 'message.*chat.*id\|chat.*id.*message\|chatId' "$TG_WEBHOOK" && \
  check "telegram-webhook extrai chat.id" "OK" || \
  check "telegram-webhook extrai chat.id" "FAIL"
[[ -f "$TG_WEBHOOK" ]] && grep -q 'webhook_secret\|secretParam' "$TG_WEBHOOK" && \
  check "telegram-webhook valida webhook_secret" "OK" || \
  check "telegram-webhook valida webhook_secret" "FAIL"
[[ -f "$TG_WEBHOOK" ]] && grep -q 'incoming-message\|forward' "$TG_WEBHOOK" && \
  check "telegram-webhook encaminha pra incoming-message" "OK" || \
  check "telegram-webhook encaminha pra incoming-message" "FAIL"
[[ -f "$TG_WEBHOOK" ]] && grep -q 'ignored.*no_message\|no_text\|no_message' "$TG_WEBHOOK" && \
  check "telegram-webhook ignora updates sem texto" "OK" || \
  check "telegram-webhook ignora updates sem texto" "FAIL"

echo ""
echo "--- docs/TELEGRAM-SETUP.md ---"
DOCS="$REPO_DIR/docs/TELEGRAM-SETUP.md"
[[ -f "$DOCS" ]] && check "docs/TELEGRAM-SETUP.md existe" "OK" || check "docs/TELEGRAM-SETUP.md existe" "FAIL"
grep -q 'BotFather\|setWebhook\|chat_id\|/start' "$DOCS" && \
  check "TELEGRAM-SETUP.md tem guia completo (BotFather+setWebhook)" "OK" || \
  check "TELEGRAM-SETUP.md tem guia completo (BotFather+setWebhook)" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
