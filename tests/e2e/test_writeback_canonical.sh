#!/usr/bin/env bash
# test_writeback_canonical.sh — Smoke test do pipeline write-back cross-channel.
# Verifica estrutura e contratos SEM fazer chamadas reais de rede.
# Retorna: 0 se PASS, 1 se algum check falhar.

set -uo pipefail
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

echo "=== Smoke Test: Pipeline Write-Back Cross-Channel ==="
echo ""

echo "--- P0-1: arg order em panel_post_reply.sh no promptMsg ---"
INCOMING="$REPO_DIR/painel-front/supabase/functions/incoming-message/index.ts"
if [[ -f "$INCOMING" ]] && grep -Eq 'panel_post_reply\.sh.*\$\{channel\}.*\$\{externalId\}.*"<sua resposta>".*\$\{threadId\}.*\$\{runId\}' "$INCOMING"; then
  check "promptMsg tem ordem: channel externalId <resposta> threadId runId" "OK"
else
  check "promptMsg tem ordem: channel externalId <resposta> threadId runId" "FAIL — verifique incoming-message/index.ts"
fi

echo ""
echo "--- P0-2: Evolution API send_message.sh ---"
EVO_SEND="$REPO_DIR/skills/evolution-api/scripts/send_message.sh"
[[ -f "$EVO_SEND" ]] && check "evolution-api/scripts/send_message.sh existe" "OK" || check "evolution-api/scripts/send_message.sh existe" "FAIL"
if [[ -f "$EVO_SEND" ]] && bash -n "$EVO_SEND" 2>/dev/null; then
  check "send_message.sh sintaxe bash OK" "OK"
else
  check "send_message.sh sintaxe bash OK" "FAIL"
fi

echo ""
echo "--- P0-3: Telegram send_message.sh ---"
TG_SEND="$REPO_DIR/skills/telegram/scripts/send_message.sh"
[[ -f "$TG_SEND" ]] && check "telegram/scripts/send_message.sh existe" "OK" || check "telegram/scripts/send_message.sh existe" "FAIL"
if [[ -f "$TG_SEND" ]] && bash -n "$TG_SEND" 2>/dev/null; then
  check "telegram send_message.sh sintaxe bash OK" "OK"
else
  check "telegram send_message.sh sintaxe bash OK" "FAIL"
fi

echo ""
echo "--- P0-2+3: cases whatsapp/telegram em panel_post_reply.sh ---"
POST_REPLY="$REPO_DIR/skills/agente-cfo/scripts/panel_post_reply.sh"
grep -q 'whatsapp)' "$POST_REPLY" 2>/dev/null && check "panel_post_reply.sh tem case whatsapp" "OK" || check "panel_post_reply.sh tem case whatsapp" "FAIL"
grep -q 'telegram)' "$POST_REPLY" 2>/dev/null && check "panel_post_reply.sh tem case telegram" "OK" || check "panel_post_reply.sh tem case telegram" "FAIL"
grep -q 'send_message.sh' "$POST_REPLY" 2>/dev/null && check "panel_post_reply.sh chama send_message.sh" "OK" || check "panel_post_reply.sh chama send_message.sh" "FAIL"

echo ""
echo "--- P0-4: promptMsg com contrato de write ---"
if [[ -f "$INCOMING" ]] && grep -Eq 'EXTRAÇÃO DE ENTIDADE|create_payable|conversa\.md' "$INCOMING"; then
  check "promptMsg contém contrato de write/few-shot" "OK"
else
  check "promptMsg contém contrato de write/few-shot" "FAIL"
fi

echo ""
echo "--- P0-5: pending_write state no incoming-message ---"
if [[ -f "$INCOMING" ]] && grep -Eq 'pending_write|WRITE PENDENTE' "$INCOMING"; then
  check "incoming-message detecta pending_write" "OK"
else
  check "incoming-message detecta pending_write" "FAIL"
fi

echo ""
echo "--- P1-1: cfo_write_events ---"
MIGRATION=$(ls "$REPO_DIR/painel-front/supabase/migrations/"*cfo_write_events* 2>/dev/null | head -1)
[[ -n "$MIGRATION" ]] && check "Migration cfo_write_events existe" "OK" || check "Migration cfo_write_events existe" "FAIL"

EDGE_FN="$REPO_DIR/painel-front/supabase/functions/cfo-write-event/index.ts"
[[ -f "$EDGE_FN" ]] && check "Edge fn cfo-write-event existe" "OK" || check "Edge fn cfo-write-event existe" "FAIL"

WRITE_EVENT_SH="$REPO_DIR/skills/agente-cfo/scripts/panel_write_event.sh"
[[ -f "$WRITE_EVENT_SH" ]] && check "panel_write_event.sh existe" "OK" || check "panel_write_event.sh existe" "FAIL"
if [[ -f "$WRITE_EVENT_SH" ]] && bash -n "$WRITE_EVENT_SH" 2>/dev/null; then
  check "panel_write_event.sh sintaxe bash OK" "OK"
else
  check "panel_write_event.sh sintaxe bash OK" "FAIL"
fi

WIDGET="$REPO_DIR/painel-front/src/components/cfo-write-events-widget.tsx"
[[ -f "$WIDGET" ]] && check "Widget cfo-write-events-widget.tsx existe" "OK" || check "Widget cfo-write-events-widget.tsx existe" "FAIL"
if [[ -f "$WIDGET" ]] && grep -q 'cfo_write_events' "$WIDGET"; then
  check "Widget referencia tabela cfo_write_events" "OK"
else
  check "Widget referencia tabela cfo_write_events" "FAIL"
fi

echo ""
echo "--- P1-2: dedup em conversa.md ---"
CONVERSA="$REPO_DIR/skills/agente-cfo/prompts/conversa.md"
if grep -Eq 'DUPLICATE|dedup|já foi registrado' "$CONVERSA"; then
  check "conversa.md tem instrução de dedup" "OK"
else
  check "conversa.md tem instrução de dedup" "FAIL"
fi

echo ""
echo "--- P3: auto-discover thread_id/run_id em panel_post_reply.sh ---"
POST_REPLY="$REPO_DIR/skills/agente-cfo/scripts/panel_post_reply.sh"
grep -q 'chat-pending-lookup' "$POST_REPLY" && \
  check "panel_post_reply.sh chama chat-pending-lookup" "OK" || \
  check "panel_post_reply.sh chama chat-pending-lookup" "FAIL"
grep -q 'auto-discover\|DISCOVERED_THREAD\|DISCOVERED_RUN' "$POST_REPLY" && \
  check "panel_post_reply.sh tem lógica de auto-discover" "OK" || \
  check "panel_post_reply.sh tem lógica de auto-discover" "FAIL"
grep -q 'source.*\.env\|set -a' "$POST_REPLY" && \
  check "panel_post_reply.sh carrega .env" "OK" || \
  check "panel_post_reply.sh carrega .env" "FAIL"
bash -n "$POST_REPLY" 2>/dev/null && \
  check "panel_post_reply.sh sintaxe bash OK" "OK" || \
  check "panel_post_reply.sh sintaxe bash OK" "FAIL"
grep -q 'auto-discover\|chat-pending-lookup' \
  "$REPO_DIR/skills/agente-cfo/prompts/conversa.md" && \
  check "conversa.md menciona auto-discover" "OK" || \
  check "conversa.md menciona auto-discover" "FAIL"

echo ""
echo "--- COMPAT-1: setup.sh + tools.profile ---"
SETUP_SH="$REPO_DIR/install/setup.sh"
[[ -f "$SETUP_SH" ]] && check "install/setup.sh existe" "OK" || check "install/setup.sh existe" "FAIL"
grep -q 'tools.profile.*coding\|tools\.profile coding' "$SETUP_SH" && \
  check "setup.sh seta tools.profile=coding" "OK" || \
  check "setup.sh seta tools.profile=coding" "FAIL"
grep -q 'approvals allowlist add' "$SETUP_SH" && \
  check "setup.sh configura approvals allowlist" "OK" || \
  check "setup.sh configura approvals allowlist" "FAIL"
grep -q 'systemctl restart openclaw-gateway\|restart.*openclaw-gateway' "$SETUP_SH" && \
  check "setup.sh faz gateway restart pós-update" "OK" || \
  check "setup.sh faz gateway restart pós-update" "FAIL"
grep -q 'AGENTS\.md\|workspace.*bootstrap\|COMPAT-1' "$SETUP_SH" && \
  check "setup.sh popula workspace bootstrap" "OK" || \
  check "setup.sh popula workspace bootstrap" "FAIL"
grep -q '_oc_semver_gte\|_OC_COMPAT_MODE' "$SETUP_SH" && \
  check "setup.sh detecta versão OpenClaw" "OK" || \
  check "setup.sh detecta versão OpenClaw" "FAIL"
bash -n "$SETUP_SH" 2>/dev/null && \
  check "setup.sh sintaxe bash OK" "OK" || \
  check "setup.sh sintaxe bash OK" "FAIL"

SKILL_MD="$REPO_DIR/skills/agente-cfo/SKILL.md"
grep -q '"tools"' "$SKILL_MD" && \
  check "SKILL.md declara requires.tools" "OK" || \
  check "SKILL.md declara requires.tools" "FAIL"
grep -q 'toolsProfile' "$SKILL_MD" && \
  check "SKILL.md declara toolsProfile" "OK" || \
  check "SKILL.md declara toolsProfile" "FAIL"

[[ -f "$REPO_DIR/docs/OPENCLAW-2026.5.18-COMPAT.md" ]] && \
  check "docs/OPENCLAW-2026.5.18-COMPAT.md existe" "OK" || \
  check "docs/OPENCLAW-2026.5.18-COMPAT.md existe" "FAIL"

echo ""
echo "--- FIX-FALLBACK: erp_gateway auto-fallback atômico ---"
ERP_GW="$REPO_DIR/skills/agente-cfo/scripts/erp_gateway.py"
[[ -f "$ERP_GW" ]] && check "erp_gateway.py existe" "OK" || check "erp_gateway.py existe" "FAIL"
python3 -c "import ast; ast.parse(open('$ERP_GW').read())" 2>/dev/null && \
  check "erp_gateway.py sintaxe Python OK" "OK" || check "erp_gateway.py sintaxe Python OK" "FAIL"
grep -q 'dashboard_only' "$ERP_GW" && \
  check "erp_gateway.py contém lógica fallback dashboard_only" "OK" || \
  check "erp_gateway.py contém lógica fallback dashboard_only" "FAIL"
grep -q 'WRITE_COMMANDS\|create_payable.*create_receivable\|WRITE_COMMANDS.*create' "$ERP_GW" && \
  check "erp_gateway.py define WRITE_COMMANDS" "OK" || \
  check "erp_gateway.py define WRITE_COMMANDS" "FAIL"
grep -q 'sys.exit(0).*always 0\|always 0\|não precisa.*recovery\|Marcos não precisa' "$ERP_GW" && \
  check "erp_gateway.py documenta exit 0 atômico" "OK" || \
  check "erp_gateway.py documenta exit 0 atômico" "FAIL"

# Teste funcional: ERP error → fallback dashboard_only (sem painel real)
FALLBACK_RESULT=$(python3 - "$ERP_GW" "$REPO_DIR" << 'PYEOF'
import subprocess, json, os, sys, shutil, tempfile
from pathlib import Path

erp_gw = sys.argv[1]
repo_dir = sys.argv[2]

# Cria skill stub que retorna erro ERP
stub_skill = Path.home() / ".openclaw" / "workspace" / "skills" / "_smoke_stub_err"
(stub_skill / "scripts").mkdir(parents=True, exist_ok=True)
(stub_skill / "scripts" / "_smoke_stub_err_client.py").write_text(
    'import json,sys\nprint(json.dumps({"error":"HTTP 404","faultstring":"not found"}))\nsys.exit(0)\n'
)
env = {**os.environ, "CFO_ERP_NAME": "_smoke_stub_err", "PANEL_BASE_URL": "", "PANEL_TOKEN": ""}
r = subprocess.run(
    ["python3", erp_gw, "create_payable",
     "--amount", "50", "--supplier", "Uber", "--due_date", "2026-05-20",
     "--thread_id", "t1", "--run_id", "r1", "--channel", "whatsapp:x"],
    capture_output=True, text=True, env=env,
)
shutil.rmtree(str(stub_skill), ignore_errors=True)
rc = r.returncode
try:
    d = json.loads(r.stdout)
    ok = rc == 0 and d.get("success") is True and d.get("fallback") == "dashboard_only"
    print("PASS" if ok else f"FAIL rc={rc} json={d}")
except Exception as e:
    print(f"FAIL rc={rc} parse_err={e} stdout={r.stdout[:200]}")
PYEOF
)
[[ "$FALLBACK_RESULT" == "PASS" ]] && \
  check "ERP error → fallback=dashboard_only, exit 0 (smoke)" "OK" || \
  check "ERP error → fallback=dashboard_only, exit 0 (smoke)" "FAIL — $FALLBACK_RESULT"

# Teste funcional: ERP success → fallback null
SUCCESS_RESULT=$(python3 - "$ERP_GW" << 'PYEOF'
import subprocess, json, os, sys, shutil
from pathlib import Path

erp_gw = sys.argv[1]
stub_skill = Path.home() / ".openclaw" / "workspace" / "skills" / "_smoke_stub_ok2"
(stub_skill / "scripts").mkdir(parents=True, exist_ok=True)
(stub_skill / "scripts" / "_smoke_stub_ok2_client.py").write_text(
    'import json,sys\nprint(json.dumps({"success":True,"id":"42","record_id":"42"}))\nsys.exit(0)\n'
)
env = {**os.environ, "CFO_ERP_NAME": "_smoke_stub_ok2", "PANEL_BASE_URL": "", "PANEL_TOKEN": ""}
r = subprocess.run(
    ["python3", erp_gw, "create_payable",
     "--amount", "200", "--supplier", "Aluguel", "--due_date", "2026-06-01",
     "--thread_id", "t2", "--run_id", "r2", "--channel", "whatsapp:x"],
    capture_output=True, text=True, env=env,
)
shutil.rmtree(str(stub_skill), ignore_errors=True)
rc = r.returncode
try:
    d = json.loads(r.stdout)
    ok = rc == 0 and d.get("success") is True and d.get("fallback") is None and d.get("erp_record_id") == "42"
    print("PASS" if ok else f"FAIL rc={rc} json={d}")
except Exception as e:
    print(f"FAIL rc={rc} parse={e} stdout={r.stdout[:200]}")
PYEOF
)
[[ "$SUCCESS_RESULT" == "PASS" ]] && \
  check "ERP success → fallback=null, erp_record_id OK (smoke)" "OK" || \
  check "ERP success → fallback=null, erp_record_id OK (smoke)" "FAIL — $SUCCESS_RESULT"

grep -q 'dashboard_only\|fallback\|ATÔMICO\|atômico' \
  "$REPO_DIR/skills/agente-cfo/prompts/conversa.md" && \
  check "conversa.md documenta contrato atômico" "OK" || \
  check "conversa.md documenta contrato atômico" "FAIL"

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
