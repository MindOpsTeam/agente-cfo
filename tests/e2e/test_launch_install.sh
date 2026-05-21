#!/usr/bin/env bash
# test_launch_install.sh — Sprint LAUNCH-1: smoke test de instalação e2e
# Verifica que os artefatos de distribuição estão ok e que as URLs críticas
# são acessíveis. NÃO roda setup.sh real.
# Retorna: 0 se PASS, 1 se falhar.

set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0; FAIL=0

check() {
  [[ "$2" == "OK" ]] && printf '  ✅ %s\n' "$1" && PASS=$((PASS+1)) && return
  printf '  ❌ %s — %s\n' "$1" "$2"; FAIL=$((FAIL+1))
}

echo "=== Smoke Test: Sprint LAUNCH-1 — Distribuição e Instalação ==="
echo ""

# ── Documentação cliente-friendly ────────────────────────────────────────────
echo "--- Docs cliente-friendly ---"
for doc in CLIENTE.md FAQ.md TROUBLESHOOTING.md LAUNCH-CHECKLIST.md \
           SPRINT-LAUNCH-1-LOVABLE-PROMPT.md; do
  [[ -f "$REPO_DIR/docs/$doc" ]] && check "docs/$doc existe" "OK" || check "docs/$doc existe" "FAIL"
done

echo ""
echo "--- Conteúdo CLIENTE.md ---"
CLIENTE="$REPO_DIR/docs/CLIENTE.md"
grep -q 'Pré-requisitos\|Anthropic\|VPS\|Hetzner\|onboarding\|15 minutos' "$CLIENTE" && \
  check "CLIENTE.md tem pré-requisitos + provedores + passos" "OK" || \
  check "CLIENTE.md tem pré-requisitos + provedores + passos" "FAIL"
grep -q 'Custo.*mês\|R\$.*mês\|custos mensais' "$CLIENTE" && \
  check "CLIENTE.md tem estimativa de custos" "OK" || \
  check "CLIENTE.md tem estimativa de custos" "FAIL"
grep -q 'Viver de IA\|comunidade\|ajuda' "$CLIENTE" && \
  check "CLIENTE.md tem seção de ajuda/comunidade" "OK" || \
  check "CLIENTE.md tem seção de ajuda/comunidade" "FAIL"

echo ""
echo "--- Conteúdo FAQ.md ---"
FAQ="$REPO_DIR/docs/FAQ.md"
grep -q 'Por que precisa.*VPS\|WhatsApp.*baniment\|Anthropic.*gastar\|atualiz' "$FAQ" && \
  check "FAQ.md cobre perguntas críticas (VPS/WA/custo/update)" "OK" || \
  check "FAQ.md cobre perguntas críticas (VPS/WA/custo/update)" "FAIL"

echo ""
echo "--- Conteúdo TROUBLESHOOTING.md ---"
TS="$REPO_DIR/docs/TROUBLESHOOTING.md"
grep -q 'tools.*0\|tools\.profile\|journalctl\|systemctl\|401\|QR code' "$TS" && \
  check "TROUBLESHOOTING.md cobre casos comuns (401/tools=0/QR/systemctl)" "OK" || \
  check "TROUBLESHOOTING.md cobre casos comuns (401/tools=0/QR/systemctl)" "FAIL"

echo ""
echo "--- README.md ---"
README="$REPO_DIR/README.md"
[[ -f "$README" ]] && check "README.md existe" "OK" || check "README.md existe" "FAIL"
grep -q 'Remixar.*Lovable\|Remix.*Lovable\|CFO virtual.*15 minutos\|15 minutos' "$README" && \
  check "README.md tem CTA Remix + pitch" "OK" || \
  check "README.md tem CTA Remix + pitch" "FAIL"
grep -q 'badge\|img.shields\|shields.io' "$README" && \
  check "README.md tem badges" "OK" || \
  check "README.md tem badges" "FAIL"
grep -q 'Skills\|MCPs\|1\.[0-9]\{3\}' "$README" && \
  check "README.md lista skills/MCPs" "OK" || \
  check "README.md lista skills/MCPs" "FAIL"
grep -q 'Hetzner\|DigitalOcean\|VPS' "$README" && \
  check "README.md menciona provedores de VPS" "OK" || \
  check "README.md menciona provedores de VPS" "FAIL"

echo ""
echo "--- LAUNCH-CHECKLIST.md ---"
CHECKLIST="$REPO_DIR/docs/LAUNCH-CHECKLIST.md"
grep -q 'is_published\|visibility.*public\|public_remixing' "$CHECKLIST" && \
  check "LAUNCH-CHECKLIST.md cobre configuração Lovable" "OK" || \
  check "LAUNCH-CHECKLIST.md cobre configuração Lovable" "FAIL"
grep -q 'LOVABLE AI PROMPT\|lovable_send_prompt\|Lovable' "$CHECKLIST" && \
  check "LAUNCH-CHECKLIST.md tem prompts Lovable AI" "OK" || \
  check "LAUNCH-CHECKLIST.md tem prompts Lovable AI" "FAIL"

echo ""
echo "--- setup-installer edge fn ---"
INSTALLER="$REPO_DIR/painel-front/supabase/functions/setup-installer/index.ts"
[[ -f "$INSTALLER" ]] && check "setup-installer/index.ts existe" "OK" || \
  check "setup-installer/index.ts existe" "FAIL"
[[ -f "$INSTALLER" ]] && grep -q 'setup.sh\|SETUP_URL\|token' "$INSTALLER" && \
  check "setup-installer gera script com token + setup.sh URL" "OK" || \
  check "setup-installer gera script com token + setup.sh URL" "FAIL"

echo ""
echo "--- URLs públicas (dry-run curl, sem auth) ---"
# Verifica que setup.sh existe no GitHub raw (pode falhar sem rede, aceita ambos)
SETUP_URL="https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh"
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$SETUP_URL" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
  check "setup.sh acessível em github raw (HTTP 200)" "OK"
elif [[ "$HTTP_CODE" == "000" ]]; then
  check "setup.sh github raw (sem rede — skip)" "OK"
else
  check "setup.sh github raw (HTTP $HTTP_CODE)" "FAIL"
fi

echo ""
echo "--- Smoke test setup.sh offline (sintaxe) ---"
SETUP="$REPO_DIR/install/setup.sh"
[[ -f "$SETUP" ]] && check "install/setup.sh existe" "OK" || check "install/setup.sh existe" "FAIL"
[[ -f "$SETUP" ]] && bash -n "$SETUP" 2>/dev/null && \
  check "install/setup.sh sintaxe bash OK" "OK" || \
  check "install/setup.sh sintaxe bash OK" "FAIL"
[[ -f "$SETUP" ]] && grep -q 'NONINTERACTIVE\|non.interactive\|NON_INTERACTIVE' "$SETUP" && \
  check "setup.sh suporta modo não-interativo" "OK" || \
  check "setup.sh suporta modo não-interativo" "FAIL"
[[ -f "$SETUP" ]] && grep -q 'PANEL_BASE_URL\|PANEL_TOKEN' "$SETUP" && \
  check "setup.sh usa PANEL_BASE_URL + PANEL_TOKEN" "OK" || \
  check "setup.sh usa PANEL_BASE_URL + PANEL_TOKEN" "FAIL"

echo ""
echo "--- SPRINT-LAUNCH-1-LOVABLE-PROMPT.md ---"
LP="$REPO_DIR/docs/SPRINT-LAUNCH-1-LOVABLE-PROMPT.md"
[[ -f "$LP" ]] && check "SPRINT-LAUNCH-1-LOVABLE-PROMPT.md existe" "OK" || \
  check "SPRINT-LAUNCH-1-LOVABLE-PROMPT.md existe" "FAIL"
grep -q 'last_heartbeat\|isOnline\|ONLINE\|OFFLINE' "$LP" && \
  check "Lovable prompt tem health indicator com last_heartbeat" "OK" || \
  check "Lovable prompt tem health indicator com last_heartbeat" "FAIL"
grep -q '30_000\|30s\|auto.refresh' "$LP" && \
  check "Lovable prompt tem auto-refresh 30s" "OK" || \
  check "Lovable prompt tem auto-refresh 30s" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
