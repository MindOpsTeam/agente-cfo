#!/usr/bin/env bash
# integrations_status.sh — Lista integrações ativas para Marcos responder ao dono.
#
# Uso (Marcos chama assim):
#   bash integrations_status.sh
#   bash integrations_status.sh --format json     # para processamento
#   bash integrations_status.sh --format text     # para enviar via WA/TG (default)
#
# Fontes consultadas (sem dependência de rede):
#   1. ~/.openclaw/secrets/*.env    — credentials sincronizadas pelo credentials-sync
#   2. openclaw config get mcp      — MCPs registrados no openclaw.json
#   3. ~/.agente-cfo/.env           — vars do ERP principal (CFO_ERP_NAME)
#   4. Painel (opcional): GET /integration-credentials-list com PANEL_TOKEN
#
# Saída text (WhatsApp-friendly):
#   Integrações ativas:
#   • ERP: Omie ✅ (mode:prod)
#   • Cobrança: Asaas ✅
#   • CRM: HubSpot ✅
#   • BD: Supabase sdfsdfd 🟢
#   • Canal: WhatsApp cfo-test-01 ✅, Telegram — não configurado
#   Desconectadas: bling, tiny, granatum…

set -euo pipefail

FORMAT="${1:-text}"
[[ "${1:-}" == "--format" ]] && FORMAT="${2:-text}"

ENV_FILE="${HOME}/.agente-cfo/.env"
SECRETS_DIR="${HOME}/.openclaw/secrets"

# ── Carrega .env ──────────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
has_secret() {
    local skill="$1"
    local env_file="${SECRETS_DIR}/${skill}.env"
    if [[ -f "$env_file" ]]; then
        # Verifica se tem ao menos uma var não-vazia
        grep -q '=.\+' "$env_file" 2>/dev/null && return 0
    fi
    # Fallback: verifica variáveis no ambiente
    case "$skill" in
        omie)     [[ -n "${OMIE_APP_KEY:-}" ]] && return 0 ;;
        asaas)    [[ -n "${ASAAS_API_KEY:-}" ]] && return 0 ;;
        hubspot)  [[ -n "${HUBSPOT_ACCESS_TOKEN:-}" ]] && return 0 ;;
        bling)    [[ -n "${BLING_ACCESS_TOKEN:-}" ]] && return 0 ;;
        contaazul)[[ -n "${CONTAAZUL_ACCESS_TOKEN:-}" ]] && return 0 ;;
        tiny)     [[ -n "${TINY_API_TOKEN:-}" ]] && return 0 ;;
        granatum) [[ -n "${GRANATUM_TOKEN:-}" ]] && return 0 ;;
        vhsys)    [[ -n "${VHSYS_ACCESS_TOKEN:-}" ]] && return 0 ;;
        nibo)     [[ -n "${NIBO_API_KEY:-}" ]] && return 0 ;;
        iugu)     [[ -n "${IUGU_API_TOKEN:-}" ]] && return 0 ;;
        rd-station)[[ -n "${RD_CLIENT_ID:-}" ]] && return 0 ;;
        piperun)  [[ -n "${PIPERUN_TOKEN:-}" ]] && return 0 ;;
        pipedrive)[[ -n "${PIPEDRIVE_API_TOKEN:-}" ]] && return 0 ;;
        kommo)    [[ -n "${KOMMO_ACCESS_TOKEN:-}" ]] && return 0 ;;
        mercado-livre)[[ -n "${MELI_ACCESS_TOKEN:-}" ]] && return 0 ;;
        nuvemshop)[[ -n "${NUVEMSHOP_ACCESS_TOKEN:-}" ]] && return 0 ;;
    esac
    return 1
}

is_mcp_registered() {
    local skill="$1"
    openclaw mcp show "$skill" --json 2>/dev/null | grep -q '"command"\|"url"' && return 0
    return 1
}

# ── Definições de integrações ─────────────────────────────────────────────────
declare -A SKILL_LABEL=(
    [omie]="Omie (ERP)"
    [bling]="Bling (ERP+NF-e)"
    [tiny]="Tiny ERP"
    [granatum]="Granatum"
    [vhsys]="VHSYS"
    [nibo]="Nibo"
    [contaazul]="ContaAzul"
    [hubspot]="HubSpot (CRM)"
    [rd-station]="RD Station"
    [piperun]="PipeRun"
    [pipedrive]="Pipedrive"
    [kommo]="Kommo"
    [asaas]="Asaas (Cobrança)"
    [iugu]="Iugu"
    [mercado-livre]="Mercado Livre"
    [nuvemshop]="Nuvemshop"
)

declare -A SKILL_CAT=(
    [omie]="ERP"       [bling]="ERP"       [tiny]="ERP"
    [granatum]="ERP"   [vhsys]="ERP"       [nibo]="ERP"      [contaazul]="ERP"
    [hubspot]="CRM"    [rd-station]="CRM"  [piperun]="CRM"
    [pipedrive]="CRM"  [kommo]="CRM"
    [asaas]="Cobrança" [iugu]="Cobrança"
    [mercado-livre]="E-commerce" [nuvemshop]="E-commerce"
)

ALL_SKILLS=(omie bling tiny granatum vhsys nibo contaazul
            hubspot rd-station piperun pipedrive kommo
            asaas iugu
            mercado-livre nuvemshop)

# ── Levanta status de cada skill ──────────────────────────────────────────────
declare -a ACTIVE_LIST=()
declare -a INACTIVE_LIST=()

for skill in "${ALL_SKILLS[@]}"; do
    if has_secret "$skill"; then
        # Verifica se MCP está registrado também
        if is_mcp_registered "$skill" 2>/dev/null; then
            ACTIVE_LIST+=("${skill}:mcp")
        else
            ACTIVE_LIST+=("${skill}:cred_only")
        fi
    else
        INACTIVE_LIST+=("$skill")
    fi
done

# ── Supabase multi-projeto ────────────────────────────────────────────────────
SUPABASE_PROJECTS=()
while IFS= read -r line; do
    [[ -n "$line" ]] && SUPABASE_PROJECTS+=("$line")
done < <(openclaw config get mcp.servers 2>/dev/null | \
    python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
    for k in d:
        if k.startswith('supabase_'):
            print(k)
except:
    pass
" 2>/dev/null || true)

# ── Canais ────────────────────────────────────────────────────────────────────
WA_STATUS="não conectado"
TG_STATUS="não configurado"

# WhatsApp: verifica wacli
if command -v wacli &>/dev/null; then
    WA_JID=$(wacli doctor 2>/dev/null | grep "LINKED_JID" | awk '{print $2}' || echo "")
    if [[ -n "$WA_JID" ]]; then
        WA_STATUS="✅ conectado ($WA_JID)"
    else
        WA_STATUS="⚠️ desconectado (rode: bash ${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/repare.sh)"
    fi
fi

# Telegram: verifica se telegram_sync tem token
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    BOT_USER=$(curl -fsS --max-time 5 \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" 2>/dev/null | \
        python3 -c "import json,sys; d=json.load(sys.stdin); print('@' + d['result']['username'])" \
        2>/dev/null || echo "bot configurado")
    TG_STATUS="✅ $BOT_USER"
fi

# ── ERP principal ─────────────────────────────────────────────────────────────
ERP_PRINCIPAL="${CFO_ERP_NAME:-omie}"

# ── Monta output ──────────────────────────────────────────────────────────────
if [[ "$FORMAT" == "json" ]]; then
    python3 - << PYEOF
import json
active = $(python3 -c "import json; print(json.dumps([s for s in '${ACTIVE_LIST[*]:-}'.split(' ') if s]))" 2>/dev/null || echo '[]')
inactive = $(python3 -c "import json; print(json.dumps([s for s in '${INACTIVE_LIST[*]:-}'.split(' ') if s]))" 2>/dev/null || echo '[]')
supabase_projects = $(python3 -c "import json; print(json.dumps([s for s in '${SUPABASE_PROJECTS[*]:-}'.split(' ') if s]))" 2>/dev/null || echo '[]')
print(json.dumps({
    "erp_principal": "${ERP_PRINCIPAL}",
    "active": active,
    "inactive": inactive,
    "supabase_projects": supabase_projects,
    "whatsapp": "${WA_STATUS}",
    "telegram": "${TG_STATUS}",
}, ensure_ascii=False, indent=2))
PYEOF
else
    # ── Formato texto (WhatsApp-friendly, max ~600 chars) ─────────────────────
    ACTIVE_NAMES=()
    for entry in "${ACTIVE_LIST[@]:-}"; do
        skill="${entry%%:*}"
        label="${SKILL_LABEL[$skill]:-$skill}"
        ACTIVE_NAMES+=("$label")
    done

    if [[ ${#SUPABASE_PROJECTS[@]} -gt 0 ]]; then
        for sp in "${SUPABASE_PROJECTS[@]}"; do
            slug="${sp#supabase_}"
            ACTIVE_NAMES+=("Supabase ($slug)")
        done
    fi

    INACTIVE_NAMES=()
    for skill in "${INACTIVE_LIST[@]:-}"; do
        INACTIVE_NAMES+=("${SKILL_LABEL[$skill]:-$skill}")
    done

    echo "Integrações ativas (${#ACTIVE_NAMES[@]}):"
    if [[ ${#ACTIVE_NAMES[@]} -gt 0 ]]; then
        for name in "${ACTIVE_NAMES[@]}"; do
            echo "• $name ✅"
        done
    else
        echo "• Nenhuma (configure em /integrations no painel)"
    fi

    echo ""
    echo "Canais:"
    echo "• WhatsApp: $WA_STATUS"
    echo "• Telegram: $TG_STATUS"

    if [[ ${#INACTIVE_NAMES[@]} -gt 0 ]]; then
        echo ""
        # Trunca lista de inativas pra caber no WA
        INACT_STR=$(IFS=", "; echo "${INACTIVE_NAMES[*]:-}" | cut -c1-200)
        echo "Não conectadas: $INACT_STR"
        echo "(Configure em: [painel]/integrations)"
    fi
fi
