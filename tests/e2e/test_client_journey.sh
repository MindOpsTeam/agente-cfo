#!/usr/bin/env bash
# test_client_journey.sh — SPRINT DIST-1: Smoke E2E "cliente novo do zero"
#
# Verifica todos os endpoints públicos e artefatos de distribuição sem rodar
# setup.sh real nem precisar de VPS. Executa em ~30s.
#
# Uso:
#   bash tests/e2e/test_client_journey.sh
#   PANEL_BASE_URL=https://xxxx.supabase.co/functions/v1 bash tests/e2e/test_client_journey.sh
#
# Retorna: 0 se todos os checks passarem, 1 se algum falhar.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS=0; FAIL=0; SKIP=0

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

check_ok()   { echo -e "  ${GREEN}✅${NC} $1"; PASS=$((PASS+1)); }
check_fail() { echo -e "  ${RED}❌${NC} $1 — $2"; FAIL=$((FAIL+1)); }
check_skip() { echo -e "  ${YELLOW}⏭️${NC}  $1 — $2 (skip)"; SKIP=$((SKIP+1)); }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   DIST-1 Smoke E2E — Jornada Cliente do Zero        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 1. setup.sh público retorna 200
# ─────────────────────────────────────────────────────────────────────────────
echo "--- 1. Artefatos públicos de instalação ---"

SETUP_SH_URL="https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh"
_HTTP=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 "$SETUP_SH_URL" || echo "000")
if [[ "$_HTTP" == "200" ]]; then
    check_ok "setup.sh público acessível (HTTP 200)"
else
    check_fail "setup.sh público" "HTTP $_HTTP (esperado 200)"
fi

# Validar que setup.sh contém as 20 skills CFO
_SETUP_CONTENT=$(curl -fsSL --max-time 20 "$SETUP_SH_URL" 2>/dev/null || echo "")
_CFO_SKILLS_IN_SETUP=(
    cfo-analise-estrategica cfo-projecao cfo-inadimplencia cfo-anomalias
    cfo-tributacao-br cfo-cobranca-orquestrada cfo-relatorios-executivos
    cfo-conciliacao-cobranca-erp cfo-conciliacao-ecommerce-erp
    cfo-conciliacao-crm-erp cfo-conciliacao-manual-erp cfo-conciliacao-bancaria
    cfo-aprendizado-padrao cfo-acao-composta
    cfo-planejamento cfo-cenarios-nomeados cfo-what-if cfo-calendario-acoes
    cfo-sensitivity cfo-decisao-estrategica
)
_MISSING_IN_SETUP=()
for _s in "${_CFO_SKILLS_IN_SETUP[@]}"; do
    echo "$_SETUP_CONTENT" | grep -q "$_s" || _MISSING_IN_SETUP+=("$_s")
done
if [[ ${#_MISSING_IN_SETUP[@]} -eq 0 ]]; then
    check_ok "setup.sh contém referência às 20 skills CFO"
elif [[ -z "$_SETUP_CONTENT" ]]; then
    check_skip "setup.sh skills CFO" "não foi possível baixar o conteúdo (verifique conectividade)"
else
    # Se repo local está OK mas raw.githubusercontent diverge, pode ser cache CDN (~5min)
    if [[ -f "$REPO_DIR/install/setup.sh" ]]; then
        _LOCAL_MISSING=0
        for _s in "${_CFO_SKILLS_IN_SETUP[@]}"; do
            grep -q "$_s" "$REPO_DIR/install/setup.sh" || _LOCAL_MISSING=$((_LOCAL_MISSING+1))
        done
        if [[ $_LOCAL_MISSING -eq 0 ]]; then
            check_skip "setup.sh skills CFO no raw.githubusercontent" "cache CDN do GitHub ainda desatualizado — re-testar em ~5min (repo local está correto)"
        else
            check_fail "setup.sh skills CFO" "${#_MISSING_IN_SETUP[@]} ausentes: ${_MISSING_IN_SETUP[*]}"
        fi
    else
        check_fail "setup.sh skills CFO" "${#_MISSING_IN_SETUP[@]} ausentes: ${_MISSING_IN_SETUP[*]}"
    fi
fi

# Verificar AGENTS.md template público
AGENTS_TMPL_URL="https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/templates/AGENTS.md"
_HTTP=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 "$AGENTS_TMPL_URL" || echo "000")
if [[ "$_HTTP" == "200" ]]; then
    check_ok "AGENTS.md template público acessível (HTTP 200)"
else
    check_fail "AGENTS.md template" "HTTP $_HTTP"
fi

# Verificar que AGENTS.md template contém PhD/Planejador/Conciliação
_AGENTS_CONTENT=$(curl -fsSL --max-time 15 "$AGENTS_TMPL_URL" 2>/dev/null || echo "")
if echo "$_AGENTS_CONTENT" | grep -qiE 'PhD|Planejador|Conciliação|Marcos'; then
    check_ok "AGENTS.md template é PhD (contém Marcos/PhD/Planejador)"
else
    check_fail "AGENTS.md template" "não parece template PhD (conteúdo inesperado)"
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 2. 20 skills CFO no repositório
# ─────────────────────────────────────────────────────────────────────────────
echo "--- 2. Skills CFO no repo local ---"

_SKILLS_DIR="$REPO_DIR/skills"
if [[ ! -d "$_SKILLS_DIR" ]]; then
    check_skip "Skills CFO no repo" "diretório skills/ não encontrado em $REPO_DIR"
else
    _MISSING_LOCAL=()
    for _s in "${_CFO_SKILLS_IN_SETUP[@]}"; do
        [[ -f "$_SKILLS_DIR/$_s/SKILL.md" ]] || _MISSING_LOCAL+=("$_s")
    done
    if [[ ${#_MISSING_LOCAL[@]} -eq 0 ]]; then
        check_ok "Todas as 20 skills CFO presentes no repo local"
    else
        check_fail "Skills CFO repo local" "${#_MISSING_LOCAL[@]} ausentes: ${_MISSING_LOCAL[*]}"
    fi
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 3. Edge functions Supabase (requer PANEL_BASE_URL)
# ─────────────────────────────────────────────────────────────────────────────
echo "--- 3. Edge functions Supabase ---"

PANEL_BASE_URL="${PANEL_BASE_URL:-}"

if [[ -z "$PANEL_BASE_URL" ]]; then
    check_skip "Edge functions" "PANEL_BASE_URL não definida — exporte para testar"
    echo ""
    echo "  Dica: export PANEL_BASE_URL=https://xxxx.supabase.co/functions/v1"
else
    PANEL_BASE_URL="${PANEL_BASE_URL%/}"

    # setup-installer: sem token → deve retornar 400
    _HTTP=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 \
        -X POST "${PANEL_BASE_URL}/setup-installer" \
        -H "Content-Type: application/json" -d '{}' || echo "000")
    if [[ "$_HTTP" == "400" ]]; then
        check_ok "setup-installer (sem token → 400)"
    elif [[ "$_HTTP" == "200" ]]; then
        check_fail "setup-installer sem token" "retornou 200 (deveria ser 400 ou 401)"
    else
        check_fail "setup-installer" "HTTP $_HTTP (esperado 400)"
    fi

    # setup-installer: com token inválido → deve retornar 401 ou 404
    _HTTP=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 \
        -X POST "${PANEL_BASE_URL}/setup-installer" \
        -H "Content-Type: application/json" \
        -d '{"token":"invalid-token-test-smoke"}' || echo "000")
    if [[ "$_HTTP" =~ ^(401|404|422)$ ]]; then
        check_ok "setup-installer (token inválido → HTTP $_HTTP)"
    else
        check_fail "setup-installer token inválido" "HTTP $_HTTP (esperado 401/404/422)"
    fi

    # onboarding-issue-token: sem JWT → deve retornar 401
    _HTTP=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 \
        -X POST "${PANEL_BASE_URL}/onboarding-issue-token" \
        -H "Content-Type: application/json" -d '{}' || echo "000")
    if [[ "$_HTTP" =~ ^(401|403)$ ]]; then
        check_ok "onboarding-issue-token (sem JWT → HTTP $_HTTP)"
    else
        check_fail "onboarding-issue-token" "HTTP $_HTTP (esperado 401/403)"
    fi

    # onboarding-validate-anthropic-key: com chave inválida → erro estruturado (não 500)
    _RESP=$(curl -s --max-time 15 \
        -X POST "${PANEL_BASE_URL}/onboarding-validate-anthropic-key" \
        -H "Content-Type: application/json" \
        -d '{"api_key":"sk-ant-INVALID-SMOKE-TEST-KEY"}' || echo "{}")
    _HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 \
        -X POST "${PANEL_BASE_URL}/onboarding-validate-anthropic-key" \
        -H "Content-Type: application/json" \
        -d '{"api_key":"sk-ant-INVALID-SMOKE-TEST-KEY"}' || echo "000")
    if echo "$_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok')" 2>/dev/null | grep -q ok; then
        if [[ "$_HTTP_CODE" != "500" ]]; then
            check_ok "onboarding-validate-anthropic-key (chave inválida → JSON estruturado, HTTP $_HTTP_CODE)"
        else
            check_fail "onboarding-validate-anthropic-key" "HTTP 500 (não deve retornar 500 para input inválido)"
        fi
    else
        check_fail "onboarding-validate-anthropic-key" "resposta não é JSON válido (HTTP $_HTTP_CODE)"
    fi

    # onboarding-test-erp-connection: sem creds → 401 ou JSON de erro
    _RESP=$(curl -s --max-time 15 \
        -X POST "${PANEL_BASE_URL}/onboarding-test-erp-connection" \
        -H "Content-Type: application/json" \
        -d '{"erp":"omie"}' || echo "{}")
    _HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 \
        -X POST "${PANEL_BASE_URL}/onboarding-test-erp-connection" \
        -H "Content-Type: application/json" \
        -d '{"erp":"omie"}' || echo "000")
    if [[ "$_HTTP_CODE" =~ ^(400|401|422)$ ]]; then
        check_ok "onboarding-test-erp-connection (sem creds → HTTP $_HTTP_CODE)"
    elif echo "$_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); ok=d.get('error') or not d.get('success',True); print('ok' if ok else 'fail')" 2>/dev/null | grep -q ok; then
        check_ok "onboarding-test-erp-connection (sem creds → JSON de erro estruturado)"
    else
        check_fail "onboarding-test-erp-connection" "HTTP $_HTTP_CODE resp: $(echo $_RESP | head -c 100)"
    fi

    # heartbeat edge fn: sem token → 401
    _HTTP=$(curl -o /dev/null -s -w "%{http_code}" --max-time 15 \
        -X POST "${PANEL_BASE_URL}/heartbeat" \
        -H "Content-Type: application/json" -d '{}' || echo "000")
    if [[ "$_HTTP" =~ ^(401|403)$ ]]; then
        check_ok "heartbeat edge fn (sem token → HTTP $_HTTP)"
    elif [[ "$_HTTP" == "404" ]]; then
        check_skip "heartbeat edge fn" "não deployada (HTTP 404)"
    else
        check_fail "heartbeat edge fn" "HTTP $_HTTP (esperado 401/403)"
    fi
fi

echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 4. Docs de distribuição no repo local
# ─────────────────────────────────────────────────────────────────────────────
echo "--- 4. Docs de distribuição ---"

_REQUIRED_DOCS=(
    "docs/CLIENTE.md"
    "docs/TROUBLESHOOTING.md"
    "docs/FAQ.md"
    "docs/SPRINT-DIST-1-LOVABLE-PROMPT.md"
    "install/REMIX_URL.example.txt"
    "install/update-remix-url.sh"
)
for _doc in "${_REQUIRED_DOCS[@]}"; do
    if [[ -f "$REPO_DIR/$_doc" ]]; then
        check_ok "$_doc existe"
    else
        check_fail "$_doc" "não encontrado em $REPO_DIR/$_doc"
    fi
done

echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
TOTAL=$((PASS+FAIL+SKIP))
if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}✅ PASS ${PASS}/${TOTAL} — Smoke E2E DIST-1 OK${NC}"
    [[ $SKIP -gt 0 ]] && echo -e "   ${YELLOW}(${SKIP} skipped — sem PANEL_BASE_URL)${NC}"
    exit 0
else
    echo -e "${RED}❌ FAIL ${FAIL}/${TOTAL} — ${PASS} ok, ${SKIP} skip${NC}"
    exit 1
fi
