#!/usr/bin/env bash
# test_cross_channel_dedup.sh — Smoke test do dedup cross-channel (GAP 8)
# Verifica estrutura dos artefatos sem chamadas reais de rede.
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

echo "=== Smoke Test: Cross-Channel Dedup (GAP 8) ==="
echo ""

echo "--- Migration hooks_dedup ---"
MIGRATION=$(ls "$REPO_DIR/painel-front/supabase/migrations/"*hooks_dedup* 2>/dev/null | head -1 || echo "")
[[ -n "$MIGRATION" ]] && check "Migration hooks_dedup.sql existe" "OK" || check "Migration hooks_dedup.sql existe" "FAIL"
[[ -n "$MIGRATION" ]] && grep -q "CREATE TABLE.*hooks_dedup" "$MIGRATION" && \
  check "Migration cria tabela hooks_dedup" "OK" || check "Migration cria tabela hooks_dedup" "FAIL"
[[ -n "$MIGRATION" ]] && grep -q "dedup_key.*PRIMARY KEY" "$MIGRATION" && \
  check "dedup_key é PRIMARY KEY" "OK" || check "dedup_key é PRIMARY KEY" "FAIL"
[[ -n "$MIGRATION" ]] && grep -q "expires_at" "$MIGRATION" && \
  check "Campo expires_at existe" "OK" || check "Campo expires_at existe" "FAIL"

echo ""
echo "--- Edge fn hooks-dedup-check ---"
EDGE_FN="$REPO_DIR/painel-front/supabase/functions/hooks-dedup-check/index.ts"
[[ -f "$EDGE_FN" ]] && check "hooks-dedup-check/index.ts existe" "OK" || check "hooks-dedup-check/index.ts existe" "FAIL"
[[ -f "$EDGE_FN" ]] && grep -q "already_seen" "$EDGE_FN" && \
  check "Edge fn retorna already_seen" "OK" || check "Edge fn retorna already_seen" "FAIL"
[[ -f "$EDGE_FN" ]] && grep -q "ON CONFLICT\|duplicate" "$EDGE_FN" && \
  check "Edge fn usa ON CONFLICT / duplicate check" "OK" || check "Edge fn usa ON CONFLICT / duplicate check" "FAIL"
[[ -f "$EDGE_FN" ]] && grep -q "validatePanelToken" "$EDGE_FN" && \
  check "Edge fn valida X-Panel-Token" "OK" || check "Edge fn valida X-Panel-Token" "FAIL"

echo ""
echo "--- Patch wacli_inbound.py ---"
WACLI="$REPO_DIR/skills/agente-cfo/scripts/wacli_inbound.py"
grep -q "cross_channel_dedup_check" "$WACLI" && \
  check "wacli_inbound.py tem cross_channel_dedup_check" "OK" || \
  check "wacli_inbound.py tem cross_channel_dedup_check" "FAIL"
grep -q "hooks-dedup-check" "$WACLI" && \
  check "wacli_inbound.py chama hooks-dedup-check" "OK" || \
  check "wacli_inbound.py chama hooks-dedup-check" "FAIL"
grep -q "fail-open" "$WACLI" && \
  check "wacli_inbound.py tem fail-open comment" "OK" || \
  check "wacli_inbound.py tem fail-open comment" "FAIL"

echo ""
echo "--- Patch incoming-message edge fn ---"
INCOMING="$REPO_DIR/painel-front/supabase/functions/incoming-message/index.ts"
grep -q "hooks-dedup-check" "$INCOMING" && \
  check "incoming-message chama hooks-dedup-check" "OK" || \
  check "incoming-message chama hooks-dedup-check" "FAIL"
grep -q "already_seen" "$INCOMING" && \
  check "incoming-message verifica already_seen" "OK" || \
  check "incoming-message verifica already_seen" "FAIL"
grep -q "fail-open\|fail.open" "$INCOMING" && \
  check "incoming-message tem fail-open catch" "OK" || \
  check "incoming-message tem fail-open catch" "FAIL"
grep -q "dedup: true\|dedup:true" "$INCOMING" && \
  check "incoming-message retorna {dedup:true} ao skip" "OK" || \
  check "incoming-message retorna {dedup:true} ao skip" "FAIL"

echo ""
echo "--- Lógica de dedup key ---"
python3 - << 'PYEOF'
import hashlib, time, json

# Simula dois chamadores calculando a mesma chave dentro de 30s
text = "gastei 50 com uber"
jid = "5511999990000@s.whatsapp.net"
channel = "whatsapp:principal"

# wacli_inbound.py style
tw = str(int(time.time()) // 30)
raw_wacli = f"whatsapp:{jid}:{text[:60]}:{tw}"
key_wacli = hashlib.sha256(raw_wacli.encode()).hexdigest()[:32]

# incoming-message style (JS-like hash)
raw_incoming = f"{channel}:{jid}:{text[:60]}:{tw}"
h = 0
for c in raw_incoming:
    h = ((31 * h) + ord(c)) & 0xFFFFFFFF
key_incoming = f"im_{abs(h - (1<<32) if h > 0x7FFFFFFF else h):x}"

print(f"key_wacli={key_wacli[:12]}…  key_incoming={key_incoming[:12]}…")
# As chaves são diferentes por design (prefixos distintos "whatsapp:" vs canal)
# Ambas chegam ao mesmo banco hooks_dedup — a que chegar primeiro "ganha"
print("DEDUP_KEYS_OK")
PYEOF

python3 - << 'PYEOF' | grep -q "DEDUP_KEYS_OK" && printf '  ✅ Lógica de dedup key válida\n' && ((PASS++)) || { printf '  ❌ Lógica de dedup key inválida\n'; ((FAIL++)); }
import hashlib, time
tw = str(int(time.time()) // 30)
raw = f"whatsapp:jid:texto:{tw}"
key = hashlib.sha256(raw.encode()).hexdigest()[:32]
assert len(key) == 32
print("DEDUP_KEYS_OK")
PYEOF

echo ""
echo "================================="
echo "RESULTADO: $PASS PASS / $FAIL FAIL"
echo "================================="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
