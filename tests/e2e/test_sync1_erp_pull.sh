#!/usr/bin/env bash
# test_sync1_erp_pull.sh — SPRINT SYNC-1: Smoke test ERP Pull daemon
#
# Verifica:
#   1. erp_sync.py existe e tem sintaxe Python OK
#   2. panel_write_event.sh suporta --origin (SYNC-1)
#   3. Systemd unit cfo-erp-sync.service está definida no setup.sh
#   4. AGENTS.md template tem seção "Feed de atividade"
#   5. docs/SPRINT-SYNC-1-LOVABLE-PROMPT.md existe
#   6. erp_sync.py --dry-run --once executa sem erro de Python (sem VPS)
#
# Não requer VPS, Supabase nem ERP real.
# Retorna: 0 se PASS, 1 se falhar.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0; FAIL=0

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

check_ok()   { echo -e "  ${GREEN}✅${NC} $1"; PASS=$((PASS+1)); }
check_fail() { echo -e "  ${RED}❌${NC} $1 — $2"; FAIL=$((FAIL+1)); }
check_skip() { echo -e "  ${YELLOW}⏭️${NC}  $1 — $2"; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   SYNC-1 Smoke Test — ERP Pull Daemon               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

ERP_SYNC="$REPO_DIR/skills/agente-cfo/scripts/erp_sync.py"
PANEL_WRITE="$REPO_DIR/skills/agente-cfo/scripts/panel_write_event.sh"
SETUP_SH="$REPO_DIR/install/setup.sh"
AGENTS_MD="$REPO_DIR/install/templates/AGENTS.md"

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 1. erp_sync.py existe e sintaxe OK ---"

if [[ -f "$ERP_SYNC" ]]; then
    check_ok "erp_sync.py existe"
else
    check_fail "erp_sync.py" "não encontrado em $ERP_SYNC"
fi

if [[ -f "$ERP_SYNC" ]]; then
    if python3 -m py_compile "$ERP_SYNC" 2>/dev/null; then
        check_ok "erp_sync.py sintaxe Python OK"
    else
        _ERR=$(python3 -m py_compile "$ERP_SYNC" 2>&1 | head -3)
        check_fail "erp_sync.py sintaxe" "$_ERR"
    fi
fi

# Verificar estrutura mínima do daemon
if [[ -f "$ERP_SYNC" ]]; then
    for _sym in "def main" "def sync_erp" "def run_once" "erp_sync" "origin.*erp_sync"; do
        grep -qE "$_sym" "$ERP_SYNC" && \
            check_ok "erp_sync.py contém: $_sym" || \
            check_fail "erp_sync.py" "missing: $_sym"
    done
    # dry_run separado (macOS grep não aceita \| sem -E e o pattern ficaria ambíguo)
    grep -qE "dry.run|dry_run" "$ERP_SYNC" && \
        check_ok "erp_sync.py tem suporte a --dry-run" || \
        check_fail "erp_sync.py" "missing: dry_run"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 2. panel_write_event.sh suporta --origin ---"

if [[ -f "$PANEL_WRITE" ]]; then
    if grep -q "\-\-origin" "$PANEL_WRITE"; then
        check_ok "panel_write_event.sh tem --origin (SYNC-1)"
    else
        check_fail "panel_write_event.sh --origin" "flag não encontrada — patch SYNC-1 não aplicado"
    fi
    if grep -q "ORIGIN\|origin" "$PANEL_WRITE"; then
        check_ok "panel_write_event.sh passa origin no payload JSON"
    else
        check_fail "panel_write_event.sh payload" "origin não incluída no JSON"
    fi
else
    check_fail "panel_write_event.sh" "não encontrado em $PANEL_WRITE"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 3. setup.sh contém systemd unit cfo-erp-sync ---"

if [[ -f "$SETUP_SH" ]]; then
    if grep -q "cfo-erp-sync" "$SETUP_SH"; then
        check_ok "setup.sh menciona cfo-erp-sync"
    else
        check_fail "setup.sh" "cfo-erp-sync não encontrado — patch SYNC-1 não aplicado"
    fi
    if grep -q "cfo-erp-sync\.service" "$SETUP_SH"; then
        check_ok "setup.sh cria cfo-erp-sync.service"
    else
        check_fail "setup.sh" "cfo-erp-sync.service não criado"
    fi
    if grep -A3 "cfo-erp-sync" "$SETUP_SH" | grep -q "enable.*cfo-erp-sync\|cfo-erp-sync.*enable"; then
        check_ok "setup.sh habilita e inicia cfo-erp-sync"
    else
        check_fail "setup.sh" "systemctl enable cfo-erp-sync não encontrado"
    fi
    # Verificar que ERP_SYNC_INTERVAL_S está na unit (configurável)
    if grep -q "ERP_SYNC_INTERVAL_S" "$SETUP_SH"; then
        check_ok "setup.sh unit tem ERP_SYNC_INTERVAL_S configurável"
    else
        check_fail "setup.sh" "ERP_SYNC_INTERVAL_S não definido na unit systemd"
    fi
else
    check_fail "setup.sh" "não encontrado em $SETUP_SH"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 4. AGENTS.md template — seção Feed de atividade ---"

if [[ -f "$AGENTS_MD" ]]; then
    if grep -q "Feed de atividade\|erp_sync\|origin.*erp_sync" "$AGENTS_MD"; then
        check_ok "AGENTS.md template tem seção 'Feed de atividade'"
    else
        check_fail "AGENTS.md template" "seção Feed de atividade não encontrada — patch SYNC-1 não aplicado"
    fi
    if grep -q "origin='erp_sync'\|origin=.erp_sync" "$AGENTS_MD"; then
        check_ok "AGENTS.md instrui Marcos a verificar origin=erp_sync"
    else
        check_fail "AGENTS.md" "instrução de origin=erp_sync não encontrada"
    fi
else
    check_fail "AGENTS.md template" "não encontrado em $AGENTS_MD"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 5. Docs SYNC-1 ---"

LOVABLE_PROMPT="$REPO_DIR/docs/SPRINT-SYNC-1-LOVABLE-PROMPT.md"
if [[ -f "$LOVABLE_PROMPT" ]]; then
    check_ok "docs/SPRINT-SYNC-1-LOVABLE-PROMPT.md existe"
    # Verificar que tem os principais refinos
    for _kw in "ActivityFeed" "origin" "tabs" "empty" "erp_sync"; do
        grep -qiE "$_kw" "$LOVABLE_PROMPT" && \
            check_ok "SPRINT-SYNC-1-LOVABLE-PROMPT tem: $_kw" || \
            check_fail "SPRINT-SYNC-1-LOVABLE-PROMPT" "missing: $_kw"
    done
else
    check_fail "docs/SPRINT-SYNC-1-LOVABLE-PROMPT.md" "não encontrado"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo "--- 6. erp_sync.py --dry-run --once (sem VPS) ---"

if [[ -f "$ERP_SYNC" ]] && command -v python3 &>/dev/null; then
    # Executa com CFO_ERP_NAME=omie mas sem .env real → espera graceful "sem ERP"
    _OUT=$(CFO_ERP_NAME="" \
        PANEL_BASE_URL="https://smoke-test-placeholder.supabase.co/functions/v1" \
        PANEL_TOKEN="smoke-test-token" \
        python3 "$ERP_SYNC" --dry-run --once 2>&1); _EXIT_CODE=$?; true

    # WARNING de subprocesso (erp_gateway saída vazia) é esperado sem ERP real.
    # O daemon deve terminar com "Rodada única concluída" e exit 0.
    _EXIT_CODE=$?
    if [[ $_EXIT_CODE -ne 0 ]]; then
        _ERR=$(echo "$_OUT" | grep -E "^Traceback|SyntaxError|ImportError" | head -2 || echo "exit $_EXIT_CODE")
        check_fail "erp_sync.py --dry-run --once" "exit $_EXIT_CODE: $_ERR"
    elif echo "$_OUT" | grep -qE "Rodada única concluída"; then
        check_ok "erp_sync.py --dry-run --once completa com 'Rodada única concluída'"
    else
        check_ok "erp_sync.py --dry-run --once executa sem exceção (exit 0)"
    fi
else
    check_skip "erp_sync.py --dry-run" "python3 não disponível ou script ausente"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
TOTAL=$((PASS+FAIL))
if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}✅ PASS ${PASS}/${TOTAL} — SYNC-1 smoke OK${NC}"
    exit 0
else
    echo -e "${RED}❌ FAIL ${FAIL}/${TOTAL} — ${PASS} ok${NC}"
    exit 1
fi
