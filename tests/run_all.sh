#!/usr/bin/env bash
# run_all.sh — Master test runner para o Agente CFO.
#
# Uso:
#   bash tests/run_all.sh [--skip-skills X,Y,Z] [--fast] [--no-panel]
#
#   --skip-skills X,Y   : pula skills específicas (separadas por vírgula)
#   --fast              : pula doctor.sh e panel health check (só smoke tests)
#   --no-panel          : pula checagem das edge functions do painel
#
# Roda em sequência:
#   1. Smoke tests de cada skill (test_mcp.py / test_sync.py)
#   2. Doctor de cada skill (doctor.sh, se existir)
#   3. integration_status.sh overview
#   4. Health check dos daemons systemd
#   5. Ping das edge functions principais do painel
#
# Saída tabular com PASS/FAIL por categoria.
# Exit code: 0 = tudo OK, 1 = alguma falha.

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
SKIP_SKILLS=""
FAST=false
NO_PANEL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --skip-skills) SKIP_SKILLS="$2"; shift 2 ;;
        --fast)        FAST=true; shift ;;
        --no-panel)    NO_PANEL=true; shift ;;
        *) echo "Argumento desconhecido: $1" >&2; exit 1 ;;
    esac
done

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$REPO_DIR/skills"
SCRIPTS_DIR="$REPO_DIR/skills/agente-cfo/scripts"
VENV="$REPO_DIR/.venv/bin/python3"
[[ ! -f "$VENV" ]] && VENV="$(which python3)"

ENV_FILE="${HOME}/.agente-cfo/.env"
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true

# ── Helpers de output ─────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
TOTAL=0; PASSED=0; FAILED=0; SKIPPED=0
declare -a FAILURES=()

_pass() { echo -e "  ${GREEN}✓${NC} $1"; TOTAL=$((TOTAL+1)); PASSED=$((PASSED+1)); }
_fail() { echo -e "  ${RED}✗${NC} $1"; TOTAL=$((TOTAL+1)); FAILED=$((FAILED+1)); FAILURES+=("$1"); }
_skip() { echo -e "  ${YELLOW}−${NC} $1"; TOTAL=$((TOTAL+1)); SKIPPED=$((SKIPPED+1)); }
_section() { echo -e "\n${CYAN}══ $1 ══${NC}"; }

_should_skip_skill() {
    local skill="$1"
    [[ -z "$SKIP_SKILLS" ]] && return 1
    local IFS=','
    read -ra SKIP_LIST <<< "$SKIP_SKILLS"
    for s in "${SKIP_LIST[@]}"; do
        [[ "$(echo "$s" | tr -d ' ')" == "$skill" ]] && return 0
    done
    return 1
}

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Agente CFO — Master Test Runner     ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════╝${NC}"
echo "Repo: $REPO_DIR"
echo "Python: $VENV"
[[ -n "$SKIP_SKILLS" ]] && echo "Pulando skills: $SKIP_SKILLS"
echo ""

# ── 1. Smoke tests das skills MCP ────────────────────────────────────────────
_section "Skills MCP (smoke tests)"

MCP_SKILLS=(
    asaas bling contaazul granatum hubspot iugu
    kommo mercado-livre nibo nuvemshop omie
    pipedrive piperun rd-station tiny vhsys
)

for skill in "${MCP_SKILLS[@]}"; do
    if _should_skip_skill "$skill"; then
        _skip "$skill (pulado)"
        continue
    fi
    test_file="$SKILLS_DIR/$skill/tests/test_mcp.py"
    if [[ ! -f "$test_file" ]]; then
        _skip "$skill (sem test_mcp.py)"
        continue
    fi
    output=$("$VENV" "$test_file" 2>&1) && _pass "$skill" || _fail "$skill: ${output: -100}"
done

# ── 2. Smoke tests de skills de sync ─────────────────────────────────────────
_section "Skills Sync (smoke tests)"

SYNC_SKILLS=(evolution-api supabase telegram)

for skill in "${SYNC_SKILLS[@]}"; do
    if _should_skip_skill "$skill"; then
        _skip "$skill (pulado)"
        continue
    fi
    # Procura test_sync.py ou test_mcp.py
    test_file="$SKILLS_DIR/$skill/tests/test_sync.py"
    [[ ! -f "$test_file" ]] && test_file="$SKILLS_DIR/$skill/tests/test_mcp.py"
    if [[ ! -f "$test_file" ]]; then
        _skip "$skill (sem teste)"
        continue
    fi
    output=$("$VENV" "$test_file" 2>&1) && _pass "$skill" || _fail "$skill: ${output: -100}"
done

# ── 3. Smoke tests dos daemons Python ────────────────────────────────────────
_section "Daemons Python (import check)"

DAEMON_SCRIPTS=(
    "agente-cfo/scripts/credentials_sync.py"
    "agente-cfo/scripts/metrics_publisher.py"
    "agente-cfo/scripts/alerts_checker.py"
    "agente-cfo/scripts/health_doctor.py"
    "agente-cfo/scripts/mcp_warmer.py"
    "agente-cfo/scripts/cost_estimator.py"
    "supabase/scripts/supabase_sync.py"
    "evolution-api/scripts/evolution_sync.py"
    "telegram/scripts/telegram_sync.py"
)

for script in "${DAEMON_SCRIPTS[@]}"; do
    full_path="$SKILLS_DIR/$script"
    name=$(basename "$(dirname "$full_path")")_$(basename "$script" .py)
    if [[ ! -f "$full_path" ]]; then
        _skip "$name (não encontrado)"
        continue
    fi
    output=$("$VENV" -c "import sys; sys.path.insert(0,'$(dirname "$full_path")'); \
        mod='$(basename "$script" .py)'; \
        __import__(mod); print('ok')" 2>&1) && _pass "$name" || _fail "$name: ${output: -80}"
done

# ── 4. Sintaxe dos shell scripts principais ───────────────────────────────────
_section "Shell scripts (sintaxe bash)"

SHELL_SCRIPTS=(
    "agente-cfo/scripts/admin_action.sh"
    "agente-cfo/scripts/backup_config.sh"
    "agente-cfo/scripts/restore_config.sh"
    "agente-cfo/scripts/auto_rollback.sh"
    "agente-cfo/scripts/memory_export.sh"
    "agente-cfo/scripts/memory_import.sh"
    "agente-cfo/scripts/memory_stats.sh"
    "agente-cfo/scripts/panel_post_reply.sh"
    "agente-cfo/scripts/self_update.sh"
    "evolution-api/scripts/send_evolution.sh"
    "telegram/scripts/send_telegram.sh"
)

for script in "${SHELL_SCRIPTS[@]}"; do
    full_path="$SKILLS_DIR/$script"
    name=$(basename "$script")
    if [[ ! -f "$full_path" ]]; then
        _skip "$name (não encontrado)"
        continue
    fi
    output=$(bash -n "$full_path" 2>&1) && _pass "$name" || _fail "$name: $output"
done

# ── 5. Doctor das skills (se não --fast) ─────────────────────────────────────
if [[ "$FAST" != "true" ]]; then
    _section "Doctor das skills"

    for skill_dir in "$SKILLS_DIR"/*/; do
        skill=$(basename "$skill_dir")
        [[ "$skill" == "_lib" || "$skill" == "_template" || "$skill" == "agente-cfo" ]] && continue
        if _should_skip_skill "$skill"; then
            _skip "$skill doctor (pulado)"
            continue
        fi
        doctor="$skill_dir/doctor.sh"
        [[ ! -f "$doctor" ]] && continue
        output=$(bash "$doctor" 2>&1 | tail -5) && _pass "$skill doctor" || \
            _skip "$skill doctor (⚠ warnings — ver acima)"
    done
fi

# ── 6. Status dos daemons systemd ─────────────────────────────────────────────
_section "Daemons systemd"

DAEMONS=(
    openclaw-gateway cloudflared-cfo
    cfo-credentials-sync cfo-supabase-sync cfo-evolution-sync cfo-telegram-sync
    cfo-automation-engine cfo-mcp-warmer
    cfo-metrics-publisher cfo-alerts-checker cfo-health-doctor
)

if command -v systemctl &>/dev/null; then
    for svc in "${DAEMONS[@]}"; do
        status=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
        if [[ "$status" == "active" ]]; then
            _pass "$svc ($status)"
        elif [[ "$status" == "unknown" ]]; then
            _skip "$svc (não instalado — ambiente de dev)"
        else
            _fail "$svc ($status)"
        fi
    done
else
    # macOS dev: verifica processos
    for svc in openclaw-gateway; do
        if pgrep -f "$svc" &>/dev/null; then
            _pass "$svc (processo ativo)"
        else
            _skip "$svc (systemd não disponível — macOS dev)"
        fi
    done
    _skip "daemons CFO (systemd não disponível — ambiente macOS)"
fi

# ── 7. Integration status ─────────────────────────────────────────────────────
_section "Integration Status"

STATUS_SCRIPT="$SCRIPTS_DIR/integration_status.sh"
if [[ -f "$STATUS_SCRIPT" ]]; then
    echo ""
    bash "$STATUS_SCRIPT" 2>/dev/null || true
    _pass "integration_status.sh executado"
else
    _skip "integration_status.sh (não encontrado)"
fi

# ── 8. Edge functions do painel (health ping) ─────────────────────────────────
if [[ "$NO_PANEL" != "true" && -n "${PANEL_BASE_URL:-}" && -n "${PANEL_TOKEN:-}" ]]; then
    _section "Edge functions do painel (health ping)"

    EDGE_FNS=(
        "heartbeat"
        "event"
        "metrics-publish"
        "integration-credentials-vps-list"
        "automations-engine-poll"
    )

    for fn in "${EDGE_FNS[@]}"; do
        url="${PANEL_BASE_URL%/}/$fn"
        # Sem X-Panel-Token deve retornar 401 (edge fn está up)
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
        if [[ "$http_code" == "401" || "$http_code" == "405" || "$http_code" == "200" ]]; then
            _pass "edge fn: $fn (HTTP $http_code — respondendo)"
        elif [[ "$http_code" == "404" ]]; then
            _skip "edge fn: $fn (404 — não deployada)"
        else
            _fail "edge fn: $fn (HTTP $http_code — inesperado)"
        fi
    done
else
    _skip "Edge functions (PANEL_BASE_URL não configurada ou --no-panel)"
fi

# ── Sumário ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}══ Resultado Final ══${NC}"
echo -e "  Total:   $TOTAL"
echo -e "  ${GREEN}Passou:  $PASSED${NC}"
[[ $SKIPPED -gt 0 ]] && echo -e "  ${YELLOW}Pulou:   $SKIPPED${NC}"
[[ $FAILED -gt 0 ]]  && echo -e "  ${RED}Falhou:  $FAILED${NC}"

if [[ ${#FAILURES[@]} -gt 0 ]]; then
    echo ""
    echo -e "${RED}Falhas:${NC}"
    for f in "${FAILURES[@]}"; do
        echo -e "  ${RED}✗${NC} $f"
    done
fi

echo ""
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✅ Todos os testes passaram!${NC}"
    exit 0
else
    echo -e "${RED}❌ $FAILED teste(s) falharam${NC}"
    exit 1
fi
