#!/usr/bin/env bash
# setup.sh — Instalador ponta-a-ponta do Agente CFO
# Roda em Ubuntu 22.04+ (VPS limpa). Idempotente.
#
# Uso interativo:    bash setup.sh
# Uso não-interativo (todas as vars preset no ambiente):
#   OMIE_APP_KEY=... OMIE_APP_SECRET=... CFO_WHATSAPP_TO=+55... \
#   ANTHROPIC_API_KEY=sk-ant-... LLM_BUDGET_BRL=50 \
#   PANEL_BASE_URL=https://xxx.supabase.co/functions/v1 \
#   NONINTERACTIVE=1 bash setup.sh
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────
SKILL_REPO="${SKILL_REPO:-https://github.com/MindOpsTeam/agente-cfo.git}"
# Ref do repo (branch ou tag). Default 'main'; o instalador do painel passa uma
# tag de release fixa (ex: REPO_REF=v1.2.0) pra instalação reproduzível.
REPO_REF="${REPO_REF:-main}"
SKILL_DEST="${HOME}/.openclaw/workspace/skills/agente-cfo"
ENV_FILE="${HOME}/.agente-cfo/.env"
INSTANCE_ENV="${HOME}/.agente-cfo/instance.env"
CRON_IDS_FILE="${HOME}/.agente-cfo/cron-ids.env"
LOG_DIR="${HOME}/.agente-cfo/logs"
STATE_DIR="${HOME}/.agente-cfo"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info() { echo -e "${CYAN}[CFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $*"; }
fail() {
    echo -e "${RED}[ERRO]${NC} $*" >&2
    echo -e "${RED}Setup abortado. Corrija o problema e execute novamente.${NC}" >&2
    exit 1
}

# Escapa um valor pra ser seguro DENTRO de "double quotes" tanto no `source` do
# bash quanto no EnvironmentFile= do systemd. Sem isso, um valor com espaço ou
# caractere especial (ex: CFO_CRM_NAME="rd station") faz o bash tentar executar
# o nome da variável como comando → `line N: VAR: command not found`.
_env_escape() {
    local v="${1-}"
    v="${v//$'\r'/}"      # remove CR de paste do Windows
    v="${v//$'\n'/ }"     # newline nunca quebra a linha do .env
    v="${v//\\/\\\\}"     # \  -> \\
    v="${v//\"/\\\"}"     # "  -> \"
    v="${v//\$/\\\$}"     # \$ -> literal (não expande no source)
    v="${v//\`/\\\`}"     # `  -> literal
    printf '%s' "$v"
}

# Faz source de um .env de forma defensiva. Se o arquivo estiver corrompido
# (ex: .env de uma versão antiga, sem aspas), faz backup em .broken e segue sem
# abortar — o PASSO 8 regrava no formato correto. Evita o crash em re-execução.
_safe_source_env() {
    local f="$1"
    [[ -f "$f" ]] || return 0
    if bash -ec 'set -a; source "$1"' _ "$f" >/dev/null 2>&1; then
        set -a; source "$f"; set +a
    else
        warn "$f corrompido (provável .env antigo sem aspas) — backup em ${f}.broken; será regenerado."
        cp -f "$f" "${f}.broken" 2>/dev/null || true
        rm -f "$f"
    fi
}

# Contrato painel→instalador (painel "burro"): o painel manda apenas o JSON do
# onboarding em base64 (CFO_ONBOARDING_B64). TODO o mapeamento nome-de-variável
# mora AQUI (central) — assim, mudar nomes nunca exige atualizar o painel de um
# cliente. Env explícito tem prioridade (instalação manual / re-execução).
_ONBOARDING_PARSER='import sys, json, re
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
def sh(v):
    s = str(v).replace("\\", "\\\\").replace("\"", "\\\"").replace("$", "\\$").replace("`", "\\`")
    return "\"" + s + "\""
SKILL = {"rdstation": "rd-station"}
def skill(n): return SKILL.get(n, n)
out = []
def put(k, v):
    if v not in (None, ""):
        out.append("export %s=%s" % (k, sh(v)))
if d.get("anthropic_key"): put("ANTHROPIC_API_KEY", d["anthropic_key"])
if d.get("whatsapp_phone"): put("CFO_WHATSAPP_TO", d["whatsapp_phone"])
erp = d.get("erp") or {}
if erp.get("name") and erp["name"] != "none":
    put("CFO_ERP_NAME", skill(erp["name"]))
    pref = re.sub(r"[^A-Z0-9]", "_", erp["name"].upper())
    for k, v in (erp.get("credentials") or {}).items():
        put("%s_%s" % (pref, k.upper()), v)
def nn(sec):
    s = d.get(sec) or {}; n = s.get("name")
    return skill(n) if (n and n != "none") else "nenhum"
put("CFO_CRM_NAME", nn("crm"))
put("CFO_COBRANCA_NAME", nn("billing"))
put("CFO_ECOMMERCE_NAME", nn("ecommerce"))
print("\n".join(out))'

_load_onboarding() {
    [[ -n "${CFO_ONBOARDING_B64:-}" ]] || return 0
    command -v python3 >/dev/null 2>&1 || { warn "python3 ausente — não consegui ler o onboarding."; return 0; }
    local out
    out=$(printf '%s' "$CFO_ONBOARDING_B64" | base64 -d 2>/dev/null | python3 -c "$_ONBOARDING_PARSER" 2>/dev/null) || true
    [[ -n "$out" ]] || { warn "CFO_ONBOARDING_B64 ilegível — seguindo sem presets."; return 0; }
    local line var
    while IFS= read -r line; do
        [[ "$line" == export\ * ]] || continue
        var="${line#export }"; var="${var%%=*}"
        [[ -n "${!var:-}" ]] && continue   # env explícito tem prioridade
        eval "$line"
    done <<< "$out"
    ok "Dados do onboarding carregados do painel."
}

# Instala o serviço que registra a instância no painel em segundo plano, tentando
# a cada 2 min até conseguir (auto-cura quando PANEL_TOKEN/PANEL_BASE_URL ficam ok).
# Ao registrar: persiste INSTANCE_ID no .env, reinicia os daemons e se desliga.
_install_register_retry_service() {
    local script="${STATE_DIR}/register_retry.sh"
    cat > "$script" <<'RETRY'
#!/usr/bin/env bash
set -u
STATE_DIR="$HOME/.agente-cfo"
ENV_FILE="$STATE_DIR/.env"
INSTANCE_ENV="$STATE_DIR/instance.env"
BODY_FILE="$STATE_DIR/register_body.json"
while true; do
    INSTANCE_ID=""; PANEL_BASE_URL=""; PANEL_TOKEN=""
    [[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true
    if [[ -n "${INSTANCE_ID:-}" ]]; then
        systemctl disable --now cfo-register-retry 2>/dev/null || true
        exit 0
    fi
    if [[ -n "${PANEL_BASE_URL:-}" && -n "${PANEL_TOKEN:-}" && -f "$BODY_FILE" ]]; then
        RESP=$(curl -s --max-time 30 -X POST "${PANEL_BASE_URL}/instance-register" \
            -H "Content-Type: application/json" -H "X-Panel-Token: ${PANEL_TOKEN}" \
            --data-binary "@${BODY_FILE}" 2>/dev/null)
        IID=$(printf '%s' "$RESP" | python3 -c "
import sys, json
try: print(json.loads(sys.stdin.read()).get('instance_id',''))
except: print('')
" 2>/dev/null || echo "")
        if [[ -n "$IID" ]]; then
            echo "INSTANCE_ID=\"$IID\"" > "$INSTANCE_ENV"
            grep -v '^INSTANCE_ID=' "$ENV_FILE" > "$ENV_FILE.tmp" 2>/dev/null && mv "$ENV_FILE.tmp" "$ENV_FILE"
            echo "INSTANCE_ID=\"$IID\"" >> "$ENV_FILE"
            chmod 600 "$ENV_FILE" 2>/dev/null || true
            for d in cfo-proactive cfo-automation-engine cfo-supabase-sync cfo-credentials-sync cfo-metrics-publisher cfo-alerts-checker; do
                systemctl restart "$d" 2>/dev/null || true
            done
            logger -t cfo-register-retry "Instância registrada: $IID" 2>/dev/null || true
            systemctl disable --now cfo-register-retry 2>/dev/null || true
            exit 0
        fi
    fi
    sleep 120
done
RETRY
    chmod +x "$script" 2>/dev/null || true
    cat > /etc/systemd/system/cfo-register-retry.service <<UNIT
[Unit]
Description=Agente CFO - retry de registro no painel
After=network.target
# Sem rate-limit de restart: o serviço pode reiniciar quantas vezes precisar até
# o token bater (senão o systemd o marcaria 'failed' e pararia de tentar).
StartLimitIntervalSec=0

[Service]
Type=simple
User=${USER:-root}
Environment=HOME=${HOME}
ExecStart=/usr/bin/env bash ${script}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload 2>/dev/null || true
    systemctl enable --now cfo-register-retry 2>/dev/null || { warn "Não consegui ativar cfo-register-retry."; return 1; }
    return 0
}

# Handshake VPS↔painel: valida que o PANEL_TOKEN é aceito pelo painel apontado por
# PANEL_BASE_URL — SEM efeito colateral (GET que só checa o token: 401 = não bate;
# qualquer outra resposta = token aceito). Garante que URL e token são do MESMO
# painel. Retorno: 0 = aceito; 1 = 401 (não bate); 2 = não deu pra validar.
_verify_panel_token() {
    [[ -n "${PANEL_BASE_URL:-}" && -n "${PANEL_TOKEN:-}" ]] || return 2
    local code
    code=$(curl -s -m 15 -o /dev/null -w "%{http_code}" \
        "${PANEL_BASE_URL}/chat-pending-lookup" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" 2>/dev/null || echo "000")
    case "$code" in
        401)         return 1 ;;
        000|404|405) return 2 ;;
        *)           return 0 ;;
    esac
}

ask() {
    local var_name="$1" description="$2" default_val="${3:-}"
    if [[ -n "${!var_name:-}" ]]; then
        ok "$description: já definido."
        return
    fi
    # NONINTERACTIVE (instalação dirigida pelo painel): nunca pergunta. Usa o
    # default se houver; senão falha explícito nomeando a variável que faltou.
    if [[ "${NONINTERACTIVE:-}" == "1" ]]; then
        if [[ -n "$default_val" ]]; then
            export "$var_name"="$default_val"
            ok "$description: usando padrão ($default_val)."
            return
        fi
        fail "NONINTERACTIVE: a variável obrigatória '$var_name' ($description) não foi fornecida pelo painel. Gere um novo link de instalação no onboarding."
    fi
    local prompt_str="$description"
    [[ -n "$default_val" ]] && prompt_str="$description [${default_val}]"
    local value=""
    while [[ -z "$value" ]]; do
        # Lê de /dev/tty pra funcionar mesmo via `curl | bash` (stdin é o script)
        if [[ -r /dev/tty ]]; then
            read -rp "$(echo -e "${CYAN}?${NC} ${prompt_str}: ")" value </dev/tty
        else
            fail "Setup precisa rodar interativamente. Baixe o script primeiro:
  curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/${REPO_REF}/install/setup.sh -o /tmp/cfo-setup.sh
  bash /tmp/cfo-setup.sh"
        fi
        value="${value:-$default_val}"
        [[ -z "$value" ]] && echo "  ⚠️  Valor obrigatório."
    done
    export "$var_name"="$value"
}

step() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN} PASSO $*${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Agente CFO — Instalador v1.2             ║${NC}"
echo -e "${CYAN}║   CFO virtual para PME brasileira via Omie+WA    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
info "Iniciando instalação em: $(hostname) — $(date '+%Y-%m-%d %H:%M:%S')"
mkdir -p "$LOG_DIR" "$STATE_DIR"
mkdir -p "${STATE_DIR}/memory"
chmod 700 "${STATE_DIR}/memory"

# Reutiliza config existente em re-execução (não regera tokens)
if [[ -f "$ENV_FILE" ]]; then
    info "Detectado $ENV_FILE — reutilizando config existente (re-execução)."
fi
# shellcheck source=/dev/null
_safe_source_env "$ENV_FILE"
# shellcheck source=/dev/null
_safe_source_env "$INSTANCE_ENV"

# Presets do painel (CFO_ONBOARDING_B64) → variáveis internas. Depois do source do
# .env pra que, em re-execução, o que já está no .env tenha prioridade.
_load_onboarding

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Pre-flight
# ─────────────────────────────────────────────────────────────────────────────
step "1/13 — Verificando dependências"

# ── Aviso de recursos (CPU/RAM) ──────────────────────────────────────────────
# 1 vCPU com o profile 'coding' satura a CPU (100% sustentado) e provedores ATIVAM
# throttle, travando o agente (model_call pendura, disco fica lento). Recomendado 2+ vCPU.
_NCPU=$(nproc 2>/dev/null || echo 1)
_RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}')
if [[ "${_NCPU:-1}" -lt 2 ]]; then
    warn "Esta VPS tem apenas ${_NCPU} vCPU. O agente (profile 'coding') pode saturar a CPU e o provedor pode ativar throttle, deixando o Marcos lento/travado. RECOMENDADO: 2+ vCPU."
fi
if [[ -n "${_RAM_MB:-}" && "${_RAM_MB}" -lt 3500 ]]; then
    warn "RAM baixa (${_RAM_MB} MB). Recomendado 4GB+ para o OpenClaw + skills + daemons."
fi

# ── Node check ≥22.12 + auto-install via NodeSource ──────────────────────────
# OpenClaw 2026.5+ requer Node v22.12+. Node 18/20 causa hard error na inicialização.
_install_node22() {
    info "Instalando Node 22 LTS via NodeSource..."
    command -v curl &>/dev/null || apt-get install -y curl -q
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - 2>&1 | tail -5
    apt-get install -y nodejs 2>&1 | tail -5
    local _maj _min
    _maj=$(node --version 2>/dev/null | tr -d 'v' | cut -d. -f1)
    _min=$(node --version 2>/dev/null | tr -d 'v' | cut -d. -f2)
    if [[ "${_maj:-0}" -lt 22 ]] || ( [[ "${_maj:-0}" -eq 22 ]] && [[ "${_min:-0}" -lt 12 ]] ); then
        fail "Instalação do Node falhou. Instale manualmente e execute o setup de novo."
    fi
    ok "Node.js $(node --version) instalado."
}

_ensure_node22() {
    if command -v node &>/dev/null; then
        local _maj _min
        _maj=$(node --version | tr -d 'v' | cut -d. -f1)
        _min=$(node --version | tr -d 'v' | cut -d. -f2)
        # Aceita 22.12+ ou qualquer 23+
        if [[ "$_maj" -gt 22 ]] || ( [[ "$_maj" -eq 22 ]] && [[ "$_min" -ge 12 ]] ); then
            ok "Node.js $(node --version) — OK."
            return
        fi
        warn "Node.js $(node --version) encontrado, mas OpenClaw requer v22.12+."
    else
        warn "Node.js não encontrado."
    fi

    if [[ "${CI:-}" == "true" ]] || [[ "${NONINTERACTIVE:-}" == "1" ]]; then
        _install_node22
        return
    fi

    local _ans="S"
    # /dev/tty: idem ask_choice — evita ler a resposta do corpo do script via pipe.
    [[ -r /dev/tty ]] && read -rp "$(echo -e "${CYAN}?${NC} Posso instalar Node 22 LTS via apt? (S/n): ")" _ans </dev/tty
    _ans="${_ans:-S}"
    if [[ "$_ans" =~ ^[Ss]$ ]]; then
        _install_node22
    else
        fail "Node.js v22.12+ é obrigatório (OpenClaw exige).
Instale manualmente:
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
Depois execute este script novamente."
    fi
}

_ensure_node22

MISSING=()
for bin in npm python3 curl jq git openssl; do
    command -v "$bin" &>/dev/null && ok "$bin ok" || MISSING+=("$bin")
done

[[ ${#MISSING[@]} -gt 0 ]] && fail "Dependências ausentes: ${MISSING[*]}
Instale com:
  apt-get update && apt-get install -y npm python3 curl jq git openssl"

ok "Dependências OK."

# ── Pre-flight 1b: detectar versão OpenClaw e validar flags ──────────────────
# Suporte a 2026.5.x: flags de cron renomeadas (--no-deliver/-light-context mantidos,
# mas o gateway precisa de restart após npm update para evitar protocol mismatch 1002).
_OC_VERSION_RAW=$(openclaw --version 2>/dev/null | head -1 || echo "0.0.0")
_OC_VERSION=$(echo "$_OC_VERSION_RAW" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "0.0.0")
_OC_MAJOR=$(echo "$_OC_VERSION" | cut -d. -f1)
_OC_MINOR=$(echo "$_OC_VERSION" | cut -d. -f2)
_OC_PATCH=$(echo "$_OC_VERSION" | cut -d. -f3)

# Semver >= 2026.5.0?
_oc_semver_gte() {
    local maj="$1" min="$2" pat="${3:-0}"
    [[ "$_OC_MAJOR" -gt "$maj" ]] && return 0
    [[ "$_OC_MAJOR" -eq "$maj" && "$_OC_MINOR" -gt "$min" ]] && return 0
    [[ "$_OC_MAJOR" -eq "$maj" && "$_OC_MINOR" -eq "$min" && "$_OC_PATCH" -ge "$pat" ]] && return 0
    return 1
}

if _oc_semver_gte 2026 5 0; then
    info "OpenClaw ${_OC_VERSION} detectado (>= 2026.5.0) — modo compat ativo."
    _OC_COMPAT_MODE="2026.5"
else
    _OC_COMPAT_MODE="legacy"
fi

if command -v openclaw &>/dev/null; then
    info "Verificando suporte a flags de 'openclaw cron add'..."
    _CRON_HELP=$(openclaw cron add --help 2>&1 || true)
    _CRON_FLAGS_OK=1

    for _flag in "--no-deliver" "--light-context" "--session" "--json"; do
        if echo "$_CRON_HELP" | grep -qF -- "$_flag"; then
            ok "openclaw cron add ${_flag}: suportado"
        else
            warn "OpenClaw ${_OC_VERSION} não suporta a flag '${_flag}' em 'cron add'."
            _CRON_FLAGS_OK=0
        fi
    done

    if [[ $_CRON_FLAGS_OK -eq 0 ]]; then
        fail "Uma ou mais flags obrigatórias não estão disponíveis no OpenClaw ${_OC_VERSION}.
Atualize o OpenClaw com: npm install -g openclaw@latest
Se o problema persistir, abra uma issue em: https://github.com/openclaw/openclaw
Instalação abortada para evitar cron jobs quebrados."
    fi
    ok "Flags de cron add: todas suportadas."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2: Instalar/atualizar OpenClaw
# ─────────────────────────────────────────────────────────────────────────────
step "2/13 — OpenClaw"

if command -v openclaw &>/dev/null; then
    ok "OpenClaw já instalado. Atualizando..."
fi
npm install -g openclaw@latest 2>&1 | tail -3 || fail "Falha ao instalar OpenClaw."
ok "OpenClaw: $(openclaw --version 2>/dev/null | head -1)"

# COMPAT-1: Após npm update, re-detectar versão (pode ter atualizado).
# Reusa _oc_semver_gte (definida no PASSO 1) — só reatualiza os globais de versão.
_OC_VERSION=$(openclaw --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "0.0.0")
[[ -z "$_OC_VERSION" || "$_OC_VERSION" == "0.0.0" ]] && \
    fail "OpenClaw não respondeu a 'openclaw --version' após a instalação.
Verifique o npm global:  npm install -g openclaw@latest  (e o PATH do node)."
_OC_MAJOR=$(echo "$_OC_VERSION" | cut -d. -f1)
_OC_MINOR=$(echo "$_OC_VERSION" | cut -d. -f2)
_OC_PATCH=$(echo "$_OC_VERSION" | cut -d. -f3)
if _oc_semver_gte 2026 5 0; then
    _OC_COMPAT_MODE="2026.5"
    info "Versão pós-update: OpenClaw ${_OC_VERSION} (compat 2026.5)"
else
    _OC_COMPAT_MODE="legacy"
fi


# Sprint 36 — Pre-instala pacotes npm dos MCP servers populares (evita cold-start por download)
step "2b/13 — Pre-instalando npm packages de MCP servers"
npm install -g --prefer-offline @supabase/mcp-server-supabase@latest 2>&1 | tail -3 \
    || warn "@supabase/mcp-server-supabase: falha na instalação (warmer tentará depois)"
ok "MCP npm packages pré-instalados (cold-start reduzido)"

# Otimizações para VPS
if ! grep -q 'NODE_COMPILE_CACHE' "${HOME}/.bashrc" 2>/dev/null; then
    cat >> "${HOME}/.bashrc" <<'EOF'
export NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
mkdir -p /var/tmp/openclaw-compile-cache
export OPENCLAW_NO_RESPAWN=1
EOF
fi
export NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
mkdir -p /var/tmp/openclaw-compile-cache
export OPENCLAW_NO_RESPAWN=1

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3: Credenciais Omie + WhatsApp + LLM
# ─────────────────────────────────────────────────────────────────────────────
step "3/13 — Credenciais"

# Credenciais do ERP Omie só são pedidas quando o ERP é Omie. Para outros ERPs as
# credenciais sincronizam do painel (Vault) via credentials-sync — não trava aqui.
if [[ "${CFO_ERP_NAME:-omie}" == "omie" ]]; then
    ask "OMIE_APP_KEY"      "Omie App Key"
    ask "OMIE_APP_SECRET"   "Omie App Secret"
fi
ask "CFO_WHATSAPP_TO"   "WhatsApp destino dos alertas (ex: +5511999999999)"
ask "ANTHROPIC_API_KEY" "Anthropic API Key (sk-ant-...)"
ask "LLM_BUDGET_BRL"    "Orçamento mensal LLM em BRL" "50"

[[ "$ANTHROPIC_API_KEY" == sk-ant-* ]] || \
    warn "ANTHROPIC_API_KEY não parece uma chave Anthropic. Continuando."
[[ "$CFO_WHATSAPP_TO" =~ ^\+[0-9]{10,15}$ ]] || \
    warn "CFO_WHATSAPP_TO '$CFO_WHATSAPP_TO' — verifique o formato E.164."

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3b: Escolher ERP e CRM
# ─────────────────────────────────────────────────────────────────────────────
step "3b/13 — Escolher ERP e CRM"

ask_choice() {
    local var_name="$1" description="$2" options="$3" default="$4"
    if [[ -n "${!var_name:-}" ]]; then
        ok "$description: ${!var_name}"
        return
    fi
    # NONINTERACTIVE: usa o default sem perguntar (defaults são seguros: omie/nenhum).
    if [[ "${NONINTERACTIVE:-}" == "1" ]]; then
        export "$var_name"="$default"
        ok "$description: $default (padrão)"
        return
    fi
    echo ""
    info "$description"
    info "Opcoes: $options"
    local _choice=""
    # Lê de /dev/tty: via `curl | bash` o stdin é o PRÓPRIO script — sem isso o
    # `read` consome as PRÓXIMAS LINHAS do script como se fossem a resposta, e
    # CFO_CRM_NAME acaba virando o texto de uma linha de código → o clone da skill
    # tenta clonar `ask_choice "..."` e quebra com `fatal: especifique diretórios`.
    if [[ -r /dev/tty ]]; then
        read -rp "$(echo -e "${CYAN}?${NC} Escolha (vazio = $default): ")" _choice </dev/tty
    else
        info "Sem terminal interativo — usando padrão: $default"
    fi
    _choice="${_choice//[$'\r\n\t ']/}"   # nome de skill é um token: sem espaço/CR/LF
    export "$var_name"="${_choice:-$default}"
}

ask_choice "CFO_ERP_NAME"       "Qual ERP voce usa?" "omie / bling / tiny / granatum / vhsys / nibo / contaazul" "omie"
ask_choice "CFO_CRM_NAME"       "Quer conectar um CRM?" "hubspot / rd-station / piperun / pipedrive / kommo / nenhum" "nenhum"
ask_choice "CFO_COBRANCA_NAME"  "Plataforma de cobranca?" "asaas / iugu / nenhum" "nenhum"
ask_choice "CFO_ECOMMERCE_NAME" "Plataforma de e-commerce?" "mercado-livre / nuvemshop / nenhum" "nenhum"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: PANEL_BASE_URL e PANEL_TOKEN
# ─────────────────────────────────────────────────────────────────────────────
step "4/13 — Painel (Supabase do cliente)"

ask "PANEL_BASE_URL" \
    "URL do seu projeto Supabase (ex: https://xxxx.supabase.co/functions/v1)"

# Blindagem: é comum colarem o COMANDO do instalador inteiro aqui
# (https://xxx.supabase.co/functions/v1/setup-installer?token=... | bash).
# Extraímos só o host Supabase e reconstruímos a base canônica /functions/v1.
if [[ "$PANEL_BASE_URL" =~ (https://[a-z0-9-]+\.supabase\.co) ]]; then
    PANEL_BASE_URL="${BASH_REMATCH[1]}/functions/v1"
    ok "PANEL_BASE_URL normalizada: $PANEL_BASE_URL"
else
    warn "PANEL_BASE_URL não parece uma URL Supabase válida. Continuando."
    PANEL_BASE_URL="${PANEL_BASE_URL%/}"
fi

if [[ -n "${PANEL_TOKEN:-}" ]]; then
    # Veio do painel (.install_env.sh): token e URL co-injetados pelo MESMO painel
    # (PANEL_BASE_URL = origin de quem emitiu o token), então batem por construção.
    ok "PANEL_TOKEN recebido do painel."
else
    # Instalação manual (curl direto): geramos o token; o handshake abaixo EXIGE
    # que ele seja cadastrado como secret no painel certo antes de prosseguir.
    PANEL_TOKEN=$(openssl rand -hex 32)
    ok "PANEL_TOKEN gerado."
    echo ""
    info "💡 Caminho recomendado (sem token manual): instale pelo LINK do painel."
    info "   No painel → Onboarding → 'gerar link de instalação' → rode aquele comando."
    info "   Esse fluxo injeta PANEL_TOKEN + URL juntos (sempre batem) e ativa a VPS"
    info "   no painel automaticamente. O modo manual exige cadastrar o secret na mão."
    echo ""
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4b: Handshake VPS↔painel — REQUISITO de instalação.
# O PANEL_TOKEN da VPS PRECISA ser aceito pelo painel apontado por PANEL_BASE_URL
# (a URL do front). Validamos AQUI, antes de instalar tudo, pra nunca terminar
# numa instalação que não fala com o painel (e pra pegar token no painel errado).
# ─────────────────────────────────────────────────────────────────────────────
step "4b/13 — Validando conexão com o painel"

_PANEL_HOST_URL="${PANEL_BASE_URL%/functions/v1}"
while true; do
    _verify_panel_token; _hs=$?
    if [[ $_hs -eq 0 ]]; then
        ok "Handshake OK — PANEL_TOKEN bate com o secret do painel (${_PANEL_HOST_URL})."
        break
    fi
    echo ""
    if [[ $_hs -eq 2 ]]; then
        warn "Não consegui validar o handshake (painel inacessível em ${PANEL_BASE_URL})."
    else
        warn "O PANEL_TOKEN da VPS NÃO bate com o secret deste painel."
    fi
    echo -e "  ${YELLOW}Cadastre/atualize no painel DESTE endereço:${NC} ${_PANEL_HOST_URL}"
    echo -e "  ${YELLOW}o secret${NC} PANEL_TOKEN ${YELLOW}com EXATAMENTE este valor:${NC}"
    echo ""
    echo "      ${PANEL_TOKEN}"
    echo ""
    echo "  (Supabase do painel → Edge Functions → Secrets → PANEL_TOKEN)"
    echo ""
    if [[ "${NONINTERACTIVE:-}" == "1" || ! -r /dev/tty ]]; then
        warn "Seguindo mesmo assim — cfo-register-retry conecta sozinho quando o token bater."
        break
    fi
    read -rp "Ajustou o secret? Tecle ENTER pra revalidar (Ctrl+C pra abortar)... " </dev/tty
done

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 5: Gerar HOOKS_TOKEN
# ─────────────────────────────────────────────────────────────────────────────
step "5/13 — Gerando hooks token"

if [[ -z "${HOOKS_TOKEN:-}" ]]; then
    HOOKS_TOKEN=$(openssl rand -hex 16)
    ok "HOOKS_TOKEN gerado."
else
    ok "HOOKS_TOKEN já definido."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 5b: Configurar OpenClaw (gateway.mode, provider Anthropic, secrets)
# ─────────────────────────────────────────────────────────────────────────────
step "5b/13 — Configurando OpenClaw"

openclaw config set gateway.mode local 2>&1 | grep -v "^Config overwrite" || true
openclaw config set gateway.auth.mode token 2>&1 | grep -v "^Config overwrite" || true
# Gera token de gateway se ainda não existe (usado pro dashboard via painel)
if ! python3 -c "import json,os,sys; t=json.load(open(os.path.expanduser('~/.openclaw/openclaw.json'))).get('gateway',{}).get('auth',{}).get('token'); sys.exit(0 if t else 1)" 2>/dev/null; then
    _GW_TOKEN=$(openssl rand -hex 24)
    openclaw config set gateway.auth.token "$_GW_TOKEN" 2>&1 | grep -v "^Config overwrite" || true
    ok "gateway.auth.token gerado."
fi
# Permite UI ser aberta de qualquer origin (proteção real é auth.token no fragment)
# Necessário porque Cloudflare quick tunnels mudam a URL a cada reinício
openclaw config set 'gateway.controlUi.allowedOrigins' '["*"]' 2>&1 | grep -v "^Config overwrite" || true
# Desabilita device pairing — acesso é via token único no fragment URL
openclaw config set 'gateway.controlUi.dangerouslyDisableDeviceAuth' true 2>&1 | grep -v "^Config overwrite" || true
ok "gateway.mode=local + auth.mode=token + controlUi (allowedOrigins=* + dangerouslyDisableDeviceAuth) configurado."

# ── COMPAT-1: tools.profile + exec approvals ─────────────────────────────────
# Garante que Marcos tenha exec/bash (group:runtime) disponível.
# Profile "coding" = group:fs + group:runtime + group:web + group:sessions + group:memory + cron
# Sem isso, trajectory.jsonl mostra tools:0 e Marcos não consegue chamar scripts shell.
openclaw config set tools.profile coding 2>&1 | grep -v "^Config overwrite" || \
    warn "tools.profile: falhou — Marcos pode não ter bash disponível."
ok "tools.profile=coding (exec/bash habilitado para Marcos)."

# Allowlist completa de scripts shell que Marcos chama no Caminho A/B
# Formato: glob; deve cobrir todos os .sh e .py executados via subprocess
_EXEC_SCRIPTS=(
    "${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/*.sh"
    "${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/*.py"
    "${HOME}/.openclaw/workspace/skills/evolution-api/scripts/*.sh"
    "${HOME}/.openclaw/workspace/skills/telegram/scripts/*.sh"
    "${HOME}/.openclaw/workspace/skills/*/scripts/*.sh"
    "${HOME}/.openclaw/workspace/skills/*/scripts/*.py"
)
for _pat in "${_EXEC_SCRIPTS[@]}"; do
    openclaw approvals allowlist add "$_pat" 2>/dev/null || \
        warn "approvals allowlist add '${_pat}': falhou (pode já existir)."
done
ok "Exec approvals allowlist configurada para scripts CFO."

# ── COMPAT-1: popular workspace root do agent main ───────────────────────────
# OpenClaw 2026.5+ lê workspace bootstrap files (AGENTS.md, SOUL.md, etc.)
# do root definido em agents.defaults.workspace.
# Se o setup não criar esses arquivos, AGENT.md fica vazio.
_WS_ROOT="${HOME}/.openclaw/workspace"
mkdir -p "$_WS_ROOT"

# PHD-1: Aplica template AGENTS.md PhD se template existir no repo OU cria o bootstrap básico
# Template prioridade: install/templates/AGENTS.md (do monorepo, via git pull/clone)
_AGENTS_TEMPLATE="${HOME}/.openclaw/workspace/skills/agente-cfo/../../../install/templates/AGENTS.md"
# Caminho mais provável quando skill foi clonada de $SKILL_REPO
_AGENTS_TEMPLATE_REPO="/tmp/agente-cfo-agents-template/install/templates/AGENTS.md"

_apply_agents_template() {
    local tmpl="$1"
    if [[ -f "$tmpl" ]]; then
        cp "$tmpl" "${_WS_ROOT}/AGENTS.md"
        ok "AGENTS.md PhD aplicado de template: $tmpl"
        return 0
    fi
    return 1
}

if [[ ! -f "${_WS_ROOT}/AGENTS.md" ]] || grep -q "Workspace do Agente CFO" "${_WS_ROOT}/AGENTS.md" 2>/dev/null; then
    # Tenta aplicar template PhD do repo clonado
    _APPLIED=0
    for _tmpl in \
        "${SKILL_DEST}/../install/templates/AGENTS.md" \
        "${HOME}/.openclaw/workspace/install/templates/AGENTS.md" \
        "/tmp/agente-cfo-clone/install/templates/AGENTS.md"; do
        if _apply_agents_template "$_tmpl" 2>/dev/null; then _APPLIED=1; break; fi
    done

    if [[ $_APPLIED -eq 0 ]]; then
        # Fallback 1: clone rápido apenas do template
        _TMPL_CLONE=$(mktemp -d /tmp/agente-cfo-tmpl-XXXXX)
        git clone --depth 1 --branch "$REPO_REF" --filter=blob:none --sparse "$SKILL_REPO" "$_TMPL_CLONE" 2>/dev/null && \
            (cd "$_TMPL_CLONE" && git sparse-checkout set "install/templates") && \
            [[ -f "$_TMPL_CLONE/install/templates/AGENTS.md" ]] && \
            _apply_agents_template "$_TMPL_CLONE/install/templates/AGENTS.md" && _APPLIED=1
        rm -rf "$_TMPL_CLONE" 2>/dev/null || true
    fi

    if [[ $_APPLIED -eq 0 ]]; then
        # Fallback 2: curl raw do GitHub (funciona mesmo sem git sparse-checkout disponível)
        info "Tentando AGENTS.md via curl raw do GitHub..."
        _RAW_AGENTS_URL="https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/${REPO_REF}/install/templates/AGENTS.md"
        if curl -fsSL --max-time 20 "$_RAW_AGENTS_URL" -o "${_WS_ROOT}/AGENTS.md" 2>/dev/null; then
            # Valida que o arquivo baixado é o template PhD (não uma página de erro HTML)
            if grep -qiE 'Marcos|CFO|PhD|Planejador|Conciliação' "${_WS_ROOT}/AGENTS.md" 2>/dev/null; then
                ok "AGENTS.md PhD baixado via curl raw (GitHub)."
                _APPLIED=1
            else
                rm -f "${_WS_ROOT}/AGENTS.md" 2>/dev/null || true
                warn "Arquivo baixado via curl não é o template PhD esperado."
            fi
        else
            warn "curl raw do GitHub falhou para AGENTS.md."
        fi
    fi

    if [[ $_APPLIED -eq 0 ]]; then
        # Último fallback: AGENTS.md básico (será substituído pelo template pós-instalação)
        cat > "${_WS_ROOT}/AGENTS.md" << 'AGENTS_EOF'
# AGENTS.md — Marcos, CFO Virtual

Você é Marcos, CFO sênior e estrategista financeiro.
Leia skills/agente-cfo/identity/identity.md, soul.md e prompts/conversa.md.
AGENTS_EOF
        warn "AGENTS.md básico criado (template PhD será aplicado após instalação completa)."
    fi
fi

if [[ ! -f "${_WS_ROOT}/SOUL.md" ]]; then
    # Copia do agente-cfo se existir, senão cria mínimo
    _CFO_SOUL="${_WS_ROOT}/skills/agente-cfo/identity/soul.md"
    if [[ -f "$_CFO_SOUL" ]]; then
        cp "$_CFO_SOUL" "${_WS_ROOT}/SOUL.md"
        ok "SOUL.md copiado de agente-cfo/identity/soul.md."
    else
        cat > "${_WS_ROOT}/SOUL.md" << 'SOUL_EOF'
# SOUL.md — Marcos, CFO Virtual

Você é Marcos, CFO virtual. Números primeiro, contexto depois.
Leia skills/agente-cfo/identity/soul.md para guardrails completos.
SOUL_EOF
        ok "SOUL.md (mínimo) criado — agente-cfo ainda não instalado."
    fi
fi

# Garante que IDENTITY.md aponte para identidade correta
if [[ ! -f "${_WS_ROOT}/IDENTITY.md" ]]; then
    cat > "${_WS_ROOT}/IDENTITY.md" << 'IDENTITY_EOF'
# IDENTITY.md

- **Name:** Marcos
- **Creature:** CFO Virtual ⚡
- **Vibe:** direto, numérico, sem firulas financeiras
- **Emoji:** 💼
IDENTITY_EOF
    ok "IDENTITY.md criado."
    # Aplica identidade no agent main
    openclaw agents set-identity --agent main --from-identity \
        --workspace "$_WS_ROOT" 2>/dev/null || \
        warn "agents set-identity: falhou (non-critical, aplica na próxima init)."
fi

info "Configurando provider Anthropic no OpenClaw..."
_ANTHROPIC_PATCH=$(mktemp /tmp/anthropic-cfg-XXXXXX.json5)
cat > "$_ANTHROPIC_PATCH" <<'ANTEOF'
{
  "models": {
    "providers": {
      "anthropic": {
        "baseUrl": "https://api.anthropic.com",
        "apiKey": {
          "source": "env",
          "provider": "anthropic",
          "id": "ANTHROPIC_API_KEY"
        },
        "models": [
          {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4.6",
            "api": "anthropic-messages",
            "maxTokens": 8192,
            "input": ["text", "image"]
          }
        ]
      }
    }
  },
  "secrets": {
    "providers": {
      "anthropic": {
        "source": "env",
        "allowlist": ["ANTHROPIC_API_KEY"]
      }
    }
  }
}
ANTEOF
openclaw config patch --file "$_ANTHROPIC_PATCH" 2>&1 | tail -3 || warn "config patch falhou — continuando."
rm -f "$_ANTHROPIC_PATCH"

openclaw models set anthropic/claude-sonnet-4-6 2>/dev/null || warn "models set falhou — continuando."
ok "Provider Anthropic/claude-sonnet-4-6 configurado como padrão."

# Exportar ANTHROPIC_API_KEY para o runtime do OpenClaw (bashrc + env atual)
grep -q "ANTHROPIC_API_KEY" "${HOME}/.bashrc" 2>/dev/null || \
    echo "export ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> "${HOME}/.bashrc"
export ANTHROPIC_API_KEY

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 6: Instalar wacli
# ─────────────────────────────────────────────────────────────────────────────
step "6/13 — Instalando wacli"

if command -v wacli &>/dev/null; then
    ok "wacli já instalado: $(wacli --version 2>&1 | head -1)"
else
    _ARCH=$(uname -m)
    case "$_ARCH" in
        x86_64)  _WACLI_ARCH="amd64" ;;
        aarch64) _WACLI_ARCH="arm64" ;;
        *)        fail "Arquitetura não suportada para wacli: $_ARCH" ;;
    esac
    _WACLI_VER="${WACLI_VERSION:-v0.7.0}"
    info "Baixando wacli ${_WACLI_VER} (${_WACLI_ARCH})..."
    curl -fsSL \
        "https://github.com/steipete/wacli/releases/download/${_WACLI_VER}/wacli-linux-${_WACLI_ARCH}.tar.gz" \
        -o /tmp/wacli.tar.gz || fail "Falha ao baixar wacli. Verifique conectividade."
    tar xzf /tmp/wacli.tar.gz -C /tmp
    mv /tmp/wacli /usr/local/bin/wacli
    chmod +x /usr/local/bin/wacli
    rm -f /tmp/wacli.tar.gz
    ok "wacli instalado: $(wacli --version 2>&1 | head -1)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 7: Pareamento WhatsApp
# ─────────────────────────────────────────────────────────────────────────────
step "7/13 — Pareamento WhatsApp"

_wacli_connected() {
    local _out
    _out=$(wacli doctor 2>&1 || true)
    if echo "$_out" | grep -qE 'AUTHENTICATED[[:space:]]+true|"authenticated":true'; then
        if echo "$_out" | grep -qE 'CONNECTION_STATE[[:space:]]+(connected|locked_by_other_process)|"connected":true'; then
            return 0
        fi
    fi
    return 1
}

if _wacli_connected; then
    ok "WhatsApp já pareado e conectado — pulando."
elif [[ "${CI:-}" == "true" ]] || [[ "${NONINTERACTIVE:-}" == "1" ]] || [[ "${CFO_SKIP_WHATSAPP_PAIR:-}" == "1" ]] || [[ ! -r /dev/tty ]]; then
    # Modo não-interativo: o wacli auth fica em loop infinito de QR ("Scan this QR code...")
    # esperando alguém escanear, travando o setup. Pulamos — o WhatsApp é conectado depois
    # pelo painel (Evolution API, recomendado) ou via 'wacli auth' manual.
    warn "Pareamento WhatsApp (wacli) pulado — modo não-interativo. Conecte o WhatsApp depois pelo painel (Evolution) ou rode 'wacli auth' manualmente na VPS."
else
    info "Iniciando pareamento WhatsApp..."
    echo ""
    echo "INSTRUÇÃO:"
    echo "  1. WhatsApp no celular → ⋮ → Dispositivos conectados"
    echo "  2. Conectar um dispositivo → aponte para o QR code"
    echo ""
    read -rp "Pressione ENTER para exibir o QR code (Ctrl+C para pular e usar Evolution)..."

    # timeout: nunca deixa o wacli auth pendurar o setup indefinidamente. Falha é não-fatal
    # (o canal WhatsApp pode ser conectado pelo painel via Evolution).
    timeout 180 wacli auth || \
        warn "Pareamento wacli não concluído (timeout/erro). Conecte o WhatsApp pelo painel (Evolution) ou rode 'wacli auth' depois."

    sleep 3
    _wacli_connected || \
        warn "WhatsApp ainda não confirmado. Verifique 'wacli doctor' após o setup, ou use Evolution pelo painel."
    ok "Etapa de pareamento concluída."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 7b: Detectar JID real do WhatsApp (bug 6b fix)
# Após pareamento, extraímos o JID do wacli doctor para evitar o problema
# do "9 BR extra" ao usar CFO_WHATSAPP_TO em formato E.164.
# ─────────────────────────────────────────────────────────────────────────────
info "Detectando JID WhatsApp via wacli doctor..."
WA_JID=$(wacli doctor 2>/dev/null | awk '/^LINKED_JID/ {print $NF; exit}' || echo "")
if [[ -n "$WA_JID" && "$WA_JID" == *"@"* ]]; then
    CFO_WHATSAPP_TO="$WA_JID"
    ok "WhatsApp JID detectado: $CFO_WHATSAPP_TO"
else
    warn "Não foi possível detectar JID via wacli doctor. Usando CFO_WHATSAPP_TO=$CFO_WHATSAPP_TO"
    warn "Se wacli_inbound não receber mensagens, verifique 'wacli doctor' e corrija CFO_WHATSAPP_TO no .env"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 8: Persistir .env (ANTES do gateway systemd — bug 1 fix)
# O gateway systemd usa EnvironmentFile=~/.agente-cfo/.env.
# Se o .env não existir quando o gateway tenta subir, o systemd falha com
# "Failed to load environment files: No such file or directory".
# ─────────────────────────────────────────────────────────────────────────────
step "8/13 — Persistindo configuração"

mkdir -p "$(dirname "$ENV_FILE")"

# Todos os valores vão entre "aspas" e escapados via _env_escape: seguro tanto
# pro `source` do bash quanto pro EnvironmentFile= do systemd (mesmo com espaços
# ou caracteres especiais). NUNCA gravar valor cru aqui.
cat > "$ENV_FILE" << EOF
# Agente CFO — gerado por setup.sh em $(date '+%Y-%m-%d %H:%M:%S')
OMIE_APP_KEY="$(_env_escape "${OMIE_APP_KEY-}")"
OMIE_APP_SECRET="$(_env_escape "${OMIE_APP_SECRET-}")"
CFO_WHATSAPP_TO="$(_env_escape "${CFO_WHATSAPP_TO-}")"
ANTHROPIC_API_KEY="$(_env_escape "${ANTHROPIC_API_KEY-}")"
LLM_BUDGET_BRL="$(_env_escape "${LLM_BUDGET_BRL-}")"
PANEL_BASE_URL="$(_env_escape "${PANEL_BASE_URL-}")"
PANEL_TOKEN="$(_env_escape "${PANEL_TOKEN-}")"
INGRESS_URL=""
HOOKS_TOKEN="$(_env_escape "${HOOKS_TOKEN-}")"
CFO_ERP_NAME="$(_env_escape "${CFO_ERP_NAME:-omie}")"
CFO_CRM_NAME="$(_env_escape "${CFO_CRM_NAME:-nenhum}")"
CFO_COBRANCA_NAME="$(_env_escape "${CFO_COBRANCA_NAME:-nenhum}")"
CFO_ECOMMERCE_NAME="$(_env_escape "${CFO_ECOMMERCE_NAME:-nenhum}")"
OMIE_SKILL_PATH="$(_env_escape "${HOME}/.openclaw/workspace/skills/omie")"
INSTANCE_ID=""
EOF
chmod 600 "$ENV_FILE"
ok "Config salva em $ENV_FILE (chmod 600)."

# shellcheck source=/dev/null
source "$ENV_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 9: Cloudflare Tunnel + systemd units (bug 1 fix: .env já existe)
# ─────────────────────────────────────────────────────────────────────────────
step "9/13 — Cloudflare Tunnel + systemd"

if ! command -v cloudflared &>/dev/null; then
    info "Instalando cloudflared..."
    _CF_ARCH_MAP=""
    case "$(uname -m)" in
        x86_64)  _CF_ARCH_MAP="amd64" ;;
        aarch64) _CF_ARCH_MAP="arm64" ;;
        *)        fail "Arquitetura não suportada: $(uname -m)" ;;
    esac
    curl -fsSL \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${_CF_ARCH_MAP}" \
        -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
    ok "cloudflared instalado."
else
    ok "cloudflared já instalado."
fi

_OPENCLAW_BIN="$(command -v openclaw)"
_CF_BIN="$(command -v cloudflared)"
_WACLI_BIN="$(command -v wacli)"
_USER_NAME="${USER:-root}"
_INBOUND_SCRIPT="${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/wacli_inbound.py"
_PROACTIVE_SCRIPT="${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/cfo_proactive_watcher.py"

# Unit do gateway OpenClaw
cat > /etc/systemd/system/openclaw-gateway.service << EOF
[Unit]
Description=OpenClaw Gateway (Agente CFO)
After=network.target

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=OPENCLAW_NO_RESPAWN=1
Environment=NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
EnvironmentFile=${ENV_FILE}
ExecStart=${_OPENCLAW_BIN} gateway --port 18789 --bind loopback
Restart=always
RestartSec=5
TimeoutStartSec=90

[Install]
WantedBy=multi-user.target
EOF

# Unit do Cloudflare Tunnel
cat > /etc/systemd/system/cloudflared-cfo.service << EOF
[Unit]
Description=Cloudflare Tunnel (Agente CFO)
After=network.target openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
ExecStart=${_CF_BIN} tunnel --url http://localhost:18789 --no-autoupdate
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Unit wacli-sync — mantém sessão WhatsApp ativa em background
cat > /etc/systemd/system/wacli-sync.service << EOF
[Unit]
Description=wacli WhatsApp sync (Agente CFO)
After=network.target

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
ExecStart=${_WACLI_BIN} sync --follow --idle-exit 0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Unit wacli-inbound — daemon de polling de mensagens inbound (bug 2 fix)
# Este unit estava ausente no setup.sh anterior, causando falha no doctor
# ("wacli-inbound listener: inativo") e nenhuma mensagem sendo processada.
cat > /etc/systemd/system/wacli-inbound.service << EOF
[Unit]
Description=Marcos WhatsApp Inbound Listener (Agente CFO)
After=network.target openclaw-gateway.service wacli-sync.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_INBOUND_SCRIPT}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Unit cfo-proactive — daemon de detecção de anomalias proativas (Sprint 5)
# O script cfo_proactive_watcher.py precisa existir (instalado no PASSO 11).
# O unit é criado agora mas iniciado APÓS o PASSO 11 (junto com wacli-inbound).
cat > /etc/systemd/system/cfo-proactive.service << EOF
[Unit]
Description=Marcos Proactive Watcher (Agente CFO)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_PROACTIVE_SCRIPT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Unit cfo-automation-engine — Automation Engine (Sprint 17)
_AUTOMATION_ENGINE_SCRIPT="${SKILL_DEST}/scripts/cfo_automation_engine.py"
cat > /etc/systemd/system/cfo-automation-engine.service << EOF
[Unit]
Description=Marcos Automation Engine (Agente CFO)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_AUTOMATION_ENGINE_SCRIPT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Unit cfo-supabase-sync — Supabase Projects Sync (Sprint 25)
_SUPABASE_SYNC_SCRIPT="${HOME}/.openclaw/workspace/skills/supabase/scripts/supabase_sync.py"
cat > /etc/systemd/system/cfo-supabase-sync.service << EOF
[Unit]
Description=Agente CFO - Supabase Projects Sync
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_SUPABASE_SYNC_SCRIPT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
# Unit cfo-credentials-sync — Credentials Sync (Sprint 26 — Zero SSH)
_CREDENTIALS_SYNC_SCRIPT="${SKILL_DEST}/scripts/credentials_sync.py"
cat > /etc/systemd/system/cfo-credentials-sync.service << EOF
[Unit]
Description=Agente CFO - Integration Credentials Sync (Zero SSH)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_CREDENTIALS_SYNC_SCRIPT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
# Unit cfo-mcp-warmer — MCP Server Pre-warm (Sprint 36)
_MCP_WARMER_SCRIPT="${SKILL_DEST}/scripts/mcp_warmer.py"
cat > /etc/systemd/system/cfo-mcp-warmer.service << EOF
[Unit]
Description=Agente CFO - MCP Server Pre-warm (cold-start reduction)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
Environment=MCP_WARMER_INTERVAL_MIN=10
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_MCP_WARMER_SCRIPT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
# Unit cfo-erp-sync — ERP→Painel sync bidirecional (Sprint SYNC-1)
_ERP_SYNC_SCRIPT="${SKILL_DEST}/scripts/erp_sync.py"
cat > /etc/systemd/system/cfo-erp-sync.service << EOF
[Unit]
Description=Agente CFO - ERP Sync (puxa novidades do ERP a cada 5min)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
Environment=ERP_SYNC_INTERVAL_S=300
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_ERP_SYNC_SCRIPT}
Restart=always
RestartSec=30
StartLimitIntervalSec=3600
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now cfo-erp-sync 2>/dev/null || warn "systemctl enable cfo-erp-sync falhou."
ok "cfo-erp-sync.service iniciado (pull ERP→painel a cada ${ERP_SYNC_INTERVAL_S:-300}s)."

# Unit cfo-metrics-publisher — Observability (Sprint 40)
_METRICS_PUBLISHER_SCRIPT="${SKILL_DEST}/scripts/metrics_publisher.py"
cat > /etc/systemd/system/cfo-metrics-publisher.service << EOF
[Unit]
Description=Agente CFO - Metrics Publisher (observability)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_METRICS_PUBLISHER_SCRIPT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# Unit cfo-dashboard-publisher — KPIs financeiros (push model, FIX-KPI-2)
_DASHBOARD_PUBLISHER_SCRIPT="${SKILL_DEST}/scripts/dashboard_publisher.py"
cat > /etc/systemd/system/cfo-dashboard-publisher.service << EOF
[Unit]
Description=Agente CFO - Dashboard Publisher (snapshot financeiro -> painel)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_DASHBOARD_PUBLISHER_SCRIPT}
Restart=always
RestartSec=10
Environment=DASHBOARD_PUBLISHER_INTERVAL_S=${DASHBOARD_PUBLISHER_INTERVAL_S:-120}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
# Unit cfo-alerts-checker — Alertas configuráveis (Sprint 42)
_ALERTS_CHECKER_SCRIPT="${SKILL_DEST}/scripts/alerts_checker.py"
cat > /etc/systemd/system/cfo-alerts-checker.service << EOF
[Unit]
Description=Agente CFO - Alerts Checker (alertas configuráveis)
After=network.target openclaw-gateway.service cfo-metrics-publisher.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_ALERTS_CHECKER_SCRIPT}
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
# Unit cfo-health-doctor — Auto-recovery (Sprint 44)
_HEALTH_DOCTOR_SCRIPT="${SKILL_DEST}/scripts/health_doctor.py"
cat > /etc/systemd/system/cfo-health-doctor.service << EOF
[Unit]
Description=Agente CFO - Health Doctor (auto-recovery sistêmico)
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${_USER_NAME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
# Limites conservadores: health-doctor raramente deve reiniciar
StartLimitIntervalSec=600
StartLimitBurst=3
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${_HEALTH_DOCTOR_SCRIPT}
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

# Atualiza units CFO para StartLimitBurst inteligente (Sprint 44)
# Daemons de baixo risco: máx 5 restarts em 10min antes de parar o restart storm
for _unit in cfo-proactive cfo-automation-engine cfo-credentials-sync cfo-supabase-sync \
             cfo-alerts-checker; do
    _unit_file="/etc/systemd/system/${_unit}.service"
    if [[ -f "$_unit_file" ]]; then
        # Adiciona StartLimitBurst se não existir
        if ! grep -q "StartLimitBurst" "$_unit_file"; then
            sed -i '/\[Service\]/a StartLimitIntervalSec=3600\nStartLimitBurst=5' "$_unit_file"
        fi
    fi
done

systemctl daemon-reload

# Iniciar gateway e aguardar responder
# COMPAT-1: Se o gateway já estava rodando com versão anterior, força restart
# para evitar "protocol mismatch (1002)" ao usar cron add com novo CLI.
if systemctl is-active --quiet openclaw-gateway 2>/dev/null; then
    info "Gateway já ativo — reiniciando para sincronizar versão do CLI (COMPAT-1)..."
    systemctl restart openclaw-gateway 2>/dev/null || warn "restart openclaw-gateway falhou."
    sleep 5
fi

systemctl enable --now openclaw-gateway 2>/dev/null || warn "systemctl enable openclaw-gateway falhou."

info "Aguardando OpenClaw Gateway subir na porta 18789 (até 60s)..."
_GW_OK=0
for _i in $(seq 1 30); do
    if curl -fs http://127.0.0.1:18789/__openclaw__/canvas/ >/dev/null 2>&1 || \
       ss -tlnp 2>/dev/null | grep -q ':18789'; then
        _GW_OK=1
        ok "Gateway pronto (~$((_i * 2))s)."
        break
    fi
    sleep 2
done

if [[ $_GW_OK -eq 0 ]]; then
    warn "Gateway não respondeu em 60s — tentando restart..."
    systemctl restart openclaw-gateway 2>/dev/null || true
    sleep 8
    ss -tlnp 2>/dev/null | grep -q ':18789' || \
        fail "Gateway não subiu. Diagnóstico:
  journalctl -u openclaw-gateway -n 50
  openclaw gateway --port 18789 --bind loopback  # manual pra ver erro"
fi

# Configurar hooks no gateway (agora que está up)
openclaw config set hooks.enabled true        2>/dev/null || warn "hooks.enabled: falhou"
openclaw config set hooks.token "${HOOKS_TOKEN}" 2>/dev/null || warn "hooks.token: falhou"
ok "OpenClaw hooks configurados (token: ${HOOKS_TOKEN:0:8}...)."

# Iniciar wacli-sync
systemctl enable --now wacli-sync 2>/dev/null || warn "wacli-sync: enable falhou (não crítico)."
ok "wacli-sync iniciado (mantém WhatsApp conectado)."

# Iniciar Cloudflare Tunnel e capturar URL
if [[ -n "${INGRESS_URL:-}" ]]; then
    ok "INGRESS_URL já definida: $INGRESS_URL — pulando tunnel."
else
    systemctl enable --now cloudflared-cfo 2>/dev/null || warn "cloudflared-cfo enable falhou."

    info "Aguardando Cloudflare Tunnel URL (até 60s)..."
    INGRESS_URL=""
    for _i in $(seq 1 30); do
        sleep 2
        INGRESS_URL=$(journalctl -u cloudflared-cfo -n 80 --no-pager 2>/dev/null \
            | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || echo "")
        [[ -n "$INGRESS_URL" ]] && break
    done

    # Fallback: processo inline se journalctl não tiver a URL ainda
    if [[ -z "$INGRESS_URL" ]]; then
        warn "URL não encontrada via journalctl — tentando fallback inline..."
        systemctl stop cloudflared-cfo 2>/dev/null || true
        _TUNNEL_LOG=$(mktemp /tmp/cfd-XXXXXX.log)
        cloudflared tunnel --url "http://localhost:18789" \
            --logfile "$_TUNNEL_LOG" --no-autoupdate &
        _TUNNEL_PID=$!
        for _i in $(seq 1 30); do
            sleep 2
            INGRESS_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$_TUNNEL_LOG" 2>/dev/null | head -1 || echo "")
            [[ -n "$INGRESS_URL" ]] && break
        done
        rm -f "$_TUNNEL_LOG"
        if [[ -z "$INGRESS_URL" ]]; then
            kill "${_TUNNEL_PID:-}" 2>/dev/null || true
            fail "Não foi possível capturar URL do Tunnel.
Verifique: journalctl -u cloudflared-cfo -n 50
O Tunnel exige saída TCP para *.cloudflare.com na porta 443."
        fi
        ok "Tunnel ativo (inline): $INGRESS_URL"
        systemctl start cloudflared-cfo 2>/dev/null || true
    else
        ok "Tunnel ativo (systemd): $INGRESS_URL"
    fi
fi

# Atualizar INGRESS_URL no .env agora que temos a URL real
grep -v "^INGRESS_URL=" "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
echo "INGRESS_URL=\"$(_env_escape "${INGRESS_URL-}")\"" >> "$ENV_FILE"
chmod 600 "$ENV_FILE"
if [[ -n "${INGRESS_URL:-}" ]]; then
    ok "INGRESS_URL persistida no .env."
else
    # A VPS ainda registra e aparece online no painel (canal VPS→painel não depende
    # do túnel); o que fica limitado é o painel→VPS (dashboard remoto/hooks).
    warn "Não consegui capturar a URL do túnel Cloudflare (INGRESS_URL vazia)."
    warn "A VPS vai registrar normalmente, mas o painel não conseguirá abrir o"
    warn "dashboard remoto até o túnel ter URL. Verifique: systemctl status cloudflared-cfo"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 10: Instalar skills do monorepo (omie + ERP/CRM escolhidos)
# (bug 3 fix): omie e demais skills ERP/CRM vêm do monorepo, não do ClawHub.
# O ClawHub tem v1.0.3 (interface antiga sem get_balance/list_payables/etc).
# ─────────────────────────────────────────────────────────────────────────────
step "10/13 — Skills ERP/CRM (monorepo)"

_install_skill_from_repo() {
    local skill_name="$1"
    local dest="${HOME}/.openclaw/workspace/skills/${skill_name}"

    if [[ -d "$dest" && -f "$dest/SKILL.md" ]]; then
        ok "Skill ${skill_name} já instalada."
        return
    fi

    info "Clonando skill '${skill_name}' do monorepo..."
    local clone_dir="/tmp/agente-cfo-skill-${skill_name}-clone"
    rm -rf "$clone_dir"
    # Retry: hiccup transitório de DNS/rede no meio de dezenas de clones. Aqui a
    # função RETORNA erro (não aborta) — quem chama decide se é fatal (omie/agente-cfo
    # são essenciais → || fail; as cfo-* especializadas seguem com warn).
    local _tries=0
    until git clone --depth 1 --branch "$REPO_REF" --filter=blob:none --sparse "$SKILL_REPO" "$clone_dir" 2>/dev/null; do
        _tries=$((_tries+1))
        if [[ $_tries -ge 4 ]]; then
            warn "Falha ao clonar ${skill_name} de ${SKILL_REPO} (4 tentativas)."
            rm -rf "$clone_dir"
            return 1
        fi
        warn "Clone de '${skill_name}' falhou (tentativa ${_tries}/4) — possível hiccup de DNS/rede. Retentando em 5s..."
        rm -rf "$clone_dir"; sleep 5
    done
    cd "$clone_dir"
    git sparse-checkout set "skills/${skill_name}" "skills/_lib" 2>/dev/null
    mkdir -p "${HOME}/.openclaw/workspace/skills"
    cp -r "skills/${skill_name}" "$dest" 2>/dev/null || true
    # Instalar/atualizar _lib (BaseERPClient/BaseCRMClient)
    mkdir -p "${HOME}/.openclaw/workspace/skills/_lib"
    cp -r "skills/_lib/"* "${HOME}/.openclaw/workspace/skills/_lib/" 2>/dev/null || true
    cd / && rm -rf "$clone_dir"

    # Validação: sparse-checkout pode "passar" mas deixar a skill vazia. Sem SKILL.md
    # a skill é inútil (o daemon rodaria sem script). Trata como falha de instalação.
    if [[ ! -f "$dest/SKILL.md" ]]; then
        warn "Skill ${skill_name} ficou incompleta (sem SKILL.md após o checkout)."
        rm -rf "$dest" 2>/dev/null || true
        return 1
    fi

    chmod +x "$dest/scripts/"*.sh 2>/dev/null || true
    ok "Skill ${skill_name} instalada de ${SKILL_REPO}."
    return 0
}

# Sempre instalar omie do monorepo (versão com get_balance/list_payables/etc).
# Essencial: sem omie o CFO não lê o ERP → aborta com mensagem clara.
_install_skill_from_repo "omie" || fail "Skill essencial 'omie' não pôde ser instalada (sem conexão com ${SKILL_REPO}?). Verifique a rede da VPS e rode o instalador de novo."

# Instalar requirements.txt se existir
OMIE_DEST="${HOME}/.openclaw/workspace/skills/omie"
[[ -f "$OMIE_DEST/requirements.txt" ]] && \
    pip3 install -r "$OMIE_DEST/requirements.txt" -q 2>/dev/null || true

# Skills ERP/CRM/cobrança/e-commerce escolhidas. Não-essenciais: se a skill não
# instalar, avisa e NÃO tenta o connect.sh (evita rodar sobre diretório vazio).
if [[ "${CFO_ERP_NAME:-omie}" != "omie" ]]; then
    if _install_skill_from_repo "${CFO_ERP_NAME}"; then
        bash "${HOME}/.openclaw/workspace/skills/${CFO_ERP_NAME}/scripts/connect.sh" || warn "connect.sh do ERP falhou — configure manualmente."
    else
        warn "Skill ERP '${CFO_ERP_NAME}' não instalou — pulei o connect.sh."
    fi
fi

if [[ "${CFO_CRM_NAME:-nenhum}" != "nenhum" ]]; then
    if _install_skill_from_repo "${CFO_CRM_NAME}"; then
        bash "${HOME}/.openclaw/workspace/skills/${CFO_CRM_NAME}/scripts/connect.sh" || warn "connect.sh do CRM falhou — configure manualmente."
    else
        warn "Skill CRM '${CFO_CRM_NAME}' não instalou — pulei o connect.sh."
    fi
fi

if [[ "${CFO_COBRANCA_NAME:-nenhum}" != "nenhum" ]]; then
    if _install_skill_from_repo "${CFO_COBRANCA_NAME}"; then
        bash "${HOME}/.openclaw/workspace/skills/${CFO_COBRANCA_NAME}/scripts/connect.sh" || warn "connect.sh de cobranca falhou — configure manualmente."
    else
        warn "Skill de cobrança '${CFO_COBRANCA_NAME}' não instalou — pulei o connect.sh."
    fi
fi

if [[ "${CFO_ECOMMERCE_NAME:-nenhum}" != "nenhum" ]]; then
    if _install_skill_from_repo "${CFO_ECOMMERCE_NAME}"; then
        bash "${HOME}/.openclaw/workspace/skills/${CFO_ECOMMERCE_NAME}/scripts/connect.sh" || warn "connect.sh de e-commerce falhou — configure manualmente."
    else
        warn "Skill de e-commerce '${CFO_ECOMMERCE_NAME}' não instalou — pulei o connect.sh."
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 11: Instalar skill agente-cfo
# ─────────────────────────────────────────────────────────────────────────────
step "11/13 — Skill agente-cfo"
# Essencial: é o cérebro do Marcos (scripts de ronda, relatórios, heartbeat).
_install_skill_from_repo "agente-cfo" || fail "Skill essencial 'agente-cfo' não pôde ser instalada (sem conexão com ${SKILL_REPO}?). Verifique a rede da VPS e rode o instalador de novo."
chmod +x $SKILL_DEST/scripts/*.sh 2>/dev/null || true
ok "Skill agente-cfo instalada em $SKILL_DEST"

# COMPAT-1: Agora que agente-cfo está instalada, garantir workspace root bootstrap
_WS_ROOT="${HOME}/.openclaw/workspace"
_CFO_SOUL_SRC="${SKILL_DEST}/identity/soul.md"
_soul_needs_update=0
[[ ! -f "${_WS_ROOT}/SOUL.md" ]] && _soul_needs_update=1
[[ -f "${_WS_ROOT}/SOUL.md" ]] && ! grep -q "guardrails" "${_WS_ROOT}/SOUL.md" 2>/dev/null && _soul_needs_update=1
if [[ -f "$_CFO_SOUL_SRC" && "$_soul_needs_update" -eq 1 ]]; then
    cp "$_CFO_SOUL_SRC" "${_WS_ROOT}/SOUL.md"
    ok "SOUL.md atualizado com identity de agente-cfo."
fi
# Aplica identidade Marcos no agent main (idempotente)
openclaw agents set-identity --agent main --from-identity \
    --workspace "$_WS_ROOT" 2>/dev/null || \
    warn "agents set-identity: falhou (non-critical)."
ok "Workspace bootstrap do agent main populado (COMPAT-1)."

# DIST-1: Aplicar template AGENTS.md PhD (agora que agente-cfo está instalada)
# Estratégia multi-fallback: git sparse → curl raw → mínimo inline
_WS_ROOT="${HOME}/.openclaw/workspace"
_AGENTS_PHD_APPLIED=0

_apply_agents_phd() {
    local src="$1"
    [[ -f "$src" ]] || return 1
    grep -qiE 'Marcos|CFO|PhD|Planejador|Conciliação' "$src" 2>/dev/null || return 1
    cp "$src" "${_WS_ROOT}/AGENTS.md"
    ok "AGENTS.md PhD aplicado de: $src"
    _AGENTS_PHD_APPLIED=1
}

# Tentativa 1: git sparse-checkout
_TMPL_SRC=$(mktemp -d /tmp/cfo-agents-phd-XXXXX)
if git clone --depth 1 --branch "$REPO_REF" --filter=blob:none --sparse "$SKILL_REPO" "$_TMPL_SRC" 2>/dev/null; then
    (cd "$_TMPL_SRC" && git sparse-checkout set "install/templates" 2>/dev/null)
    _apply_agents_phd "$_TMPL_SRC/install/templates/AGENTS.md" || true
fi
rm -rf "$_TMPL_SRC" 2>/dev/null || true

# Tentativa 2: curl raw GitHub (fallback sem git)
if [[ $_AGENTS_PHD_APPLIED -eq 0 ]]; then
    info "Baixando AGENTS.md PhD via curl raw (fallback)..."
    _RAW_URL="https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/${REPO_REF}/install/templates/AGENTS.md"
    _TMP_AGENTS=$(mktemp /tmp/agents-phd-XXXXX.md)
    if curl -fsSL --max-time 20 "$_RAW_URL" -o "$_TMP_AGENTS" 2>/dev/null; then
        _apply_agents_phd "$_TMP_AGENTS" || warn "AGENTS.md baixado via curl não parece válido."
    else
        warn "curl raw GitHub falhou para AGENTS.md (sem conectividade?)."
    fi
    rm -f "$_TMP_AGENTS" 2>/dev/null || true
fi

# Fallback final: não sobrescreve se já existe algum AGENTS.md
if [[ $_AGENTS_PHD_APPLIED -eq 0 ]]; then
    if [[ -f "${_WS_ROOT}/AGENTS.md" ]]; then
        warn "AGENTS.md PhD não aplicado — mantendo versão existente."
    else
        warn "AGENTS.md PhD não aplicado e nenhum existente — Marcos usará defaults de SOUL.md."
    fi
fi

# DIST-1: Instalar TODAS as 20 skills CFO especializadas (all-skills guaranteed)
step "11b/13 — Skills CFO especializadas (DIST-1: all 20)"
_CFO_SKILLS=(
    # Análise e relatórios
    cfo-analise-estrategica
    cfo-projecao
    cfo-inadimplencia
    cfo-anomalias
    cfo-tributacao-br
    cfo-cobranca-orquestrada
    cfo-relatorios-executivos
    # Conciliação cross-sistema
    cfo-conciliacao-cobranca-erp
    cfo-conciliacao-ecommerce-erp
    cfo-conciliacao-crm-erp
    cfo-conciliacao-manual-erp
    cfo-conciliacao-bancaria
    # Aprendizado e ação
    cfo-aprendizado-padrao
    cfo-acao-composta
    # Planejamento e cenários
    cfo-planejamento
    cfo-cenarios-nomeados
    cfo-what-if
    cfo-calendario-acoes
    cfo-sensitivity
    cfo-decisao-estrategica
)
_CFO_SKILL_FAIL=0
for _skill in "${_CFO_SKILLS[@]}"; do
    _install_skill_from_repo "$_skill" || { warn "Skill ${_skill}: falhou ao instalar (não-crítico)."; _CFO_SKILL_FAIL=$((_CFO_SKILL_FAIL+1)); }
done
if [[ $_CFO_SKILL_FAIL -eq 0 ]]; then
    ok "Todas as 20 skills CFO instaladas com sucesso."
else
    warn "${_CFO_SKILL_FAIL} skill(s) CFO falharam — verifique conectividade com ${SKILL_REPO}."
fi

# PHD-1: Criar diretório de memória financeira
mkdir -p "${HOME}/.agente-cfo/memory"
chmod 700 "${HOME}/.agente-cfo/memory"
ok "Diretório de memória financeira criado."

# Agora que agente-cfo está instalada, podemos iniciar o wacli-inbound (bug 2 fix)
# O script wacli_inbound.py precisa existir antes de o service subir.
systemctl enable --now wacli-inbound 2>/dev/null || warn "wacli-inbound enable falhou."
ok "wacli-inbound.service iniciado."

# Iniciar proactive watcher (cfo_proactive_watcher.py já existe)
systemctl enable --now cfo-proactive 2>/dev/null || warn "cfo-proactive enable falhou."
ok "cfo-proactive.service iniciado (detecção de anomalias a cada ${CFO_PROACTIVE_INTERVAL_MINUTES:-30} min)."

# Iniciar automation engine (Sprint 17)
systemctl enable --now cfo-automation-engine 2>/dev/null || warn "systemctl enable cfo-automation-engine falhou."
# NÃO desativa cfo-proactive aqui — mantém para rollback
info "cfo-automation-engine ativado. cfo-proactive mantido (rollback disponível)."

# Instalar skill supabase (Sprint 25) — não-essencial, não aborta se falhar.
_install_skill_from_repo "supabase" || warn "Skill 'supabase' não instalou (não-crítico)."
chmod +x "${HOME}/.openclaw/workspace/skills/supabase/connect.sh" 2>/dev/null || true
chmod +x "${HOME}/.openclaw/workspace/skills/supabase/doctor.sh" 2>/dev/null || true

# Iniciar supabase sync daemon
systemctl enable --now cfo-supabase-sync 2>/dev/null || warn "systemctl enable cfo-supabase-sync falhou."
ok "cfo-supabase-sync.service iniciado (sync de projetos Supabase a cada ${SUPABASE_SYNC_INTERVAL_MIN:-5} min)."

# Iniciar credentials sync daemon (Sprint 26 — Zero SSH)
chmod +x "${SKILL_DEST}/scripts/self_update.sh" 2>/dev/null || true
systemctl enable --now cfo-credentials-sync 2>/dev/null || warn "systemctl enable cfo-credentials-sync falhou."
ok "cfo-credentials-sync.service iniciado (sync de credenciais a cada ${CREDENTIALS_SYNC_INTERVAL_MIN:-3} min)."

# Instalar skill evolution-api e iniciar daemon (Sprint 27) — não-essencial.
_install_skill_from_repo "evolution-api" || warn "Skill 'evolution-api' não instalou (não-crítico)."

# Instalar skill telegram e iniciar daemon (Sprint 34) — não-essencial.
_install_skill_from_repo "telegram" || warn "Skill 'telegram' não instalou (não-crítico)."

# Iniciar MCP warmer (Sprint 36 — redução de cold-start)
systemctl enable --now cfo-mcp-warmer 2>/dev/null || warn "systemctl enable cfo-mcp-warmer falhou."
ok "cfo-mcp-warmer.service iniciado (pre-warm MCPs a cada ${MCP_WARMER_INTERVAL_MIN:-10} min)."

# Iniciar metrics publisher (Sprint 40 — Observability)
chmod +x "${SKILL_DEST}/scripts/metric_emit.sh" 2>/dev/null || true
systemctl enable --now cfo-metrics-publisher 2>/dev/null || warn "systemctl enable cfo-metrics-publisher falhou."
ok "cfo-metrics-publisher.service iniciado (publica métricas a cada ${METRICS_PUBLISHER_INTERVAL_S:-60}s)."

# Iniciar dashboard publisher (FIX-KPI-2 — snapshot financeiro push)
systemctl enable --now cfo-dashboard-publisher 2>/dev/null || warn "systemctl enable cfo-dashboard-publisher falhou."
ok "cfo-dashboard-publisher.service iniciado (snapshot financeiro a cada ${DASHBOARD_PUBLISHER_INTERVAL_S:-120}s)."

# Iniciar alerts checker (Sprint 42 — alertas configuráveis)
systemctl enable --now cfo-alerts-checker 2>/dev/null || warn "systemctl enable cfo-alerts-checker falhou."
ok "cfo-alerts-checker.service iniciado (verifica alertas a cada ${ALERTS_CHECKER_INTERVAL_S:-60}s)."

# Iniciar health doctor (Sprint 44 — auto-recovery)
chmod +x "${SKILL_DEST}/scripts/auto_rollback.sh" 2>/dev/null || true
systemctl enable --now cfo-health-doctor 2>/dev/null || warn "systemctl enable cfo-health-doctor falhou."
ok "cfo-health-doctor.service iniciado (saúde sistêmica a cada ${HEALTH_DOCTOR_INTERVAL_S:-60}s)."

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 12: Registrar instância no painel
# ─────────────────────────────────────────────────────────────────────────────
step "12/13 — Registrando no painel"

INSTANCE_ID="${INSTANCE_ID:-}"
if [[ -f "$INSTANCE_ENV" ]]; then
    # shellcheck source=/dev/null
    source "$INSTANCE_ENV" 2>/dev/null || true
fi

AGENTE_CFO_VER=$(git -C "$SKILL_DEST" describe --tags --always 2>/dev/null || echo "1.0.0")
OPENCLAW_VER=$(openclaw --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")

# Token do dashboard do OpenClaw (lido do openclaw.json — usado pra autenticar UI)
OPENCLAW_DASHBOARD_TOKEN=$(python3 -c "
import json, os
try:
    with open(os.path.expanduser('~/.openclaw/openclaw.json')) as f:
        print(json.load(f).get('gateway', {}).get('token', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

REGISTER_BODY=$(printf \
    '{"hostname":"%s","openclaw_version":"%s","agente_cfo_version":"%s","ingress_url":"%s","hooks_token":"%s","openclaw_dashboard_token":"%s"}' \
    "$(hostname)" "$OPENCLAW_VER" "$AGENTE_CFO_VER" "${INGRESS_URL:-}" "$HOOKS_TOKEN" "$OPENCLAW_DASHBOARD_TOKEN")

# Salva a payload pra o serviço de retry reaproveitar exatamente a mesma.
REGISTER_BODY_FILE="${STATE_DIR}/register_body.json"
printf '%s' "$REGISTER_BODY" > "$REGISTER_BODY_FILE"
chmod 600 "$REGISTER_BODY_FILE" 2>/dev/null || true

_persist_instance_id() {
    local iid="$1"
    echo "INSTANCE_ID=\"$(_env_escape "$iid")\"" > "$INSTANCE_ENV"
    grep -v "^INSTANCE_ID=" "$ENV_FILE" > "${ENV_FILE}.tmp" 2>/dev/null && mv "${ENV_FILE}.tmp" "$ENV_FILE"
    echo "INSTANCE_ID=\"$(_env_escape "$iid")\"" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"
}

# RESILIÊNCIA: o registro NÃO aborta mais a instalação. Tenta inline (3x p/ hiccup
# de rede); se não der, segue e instala um serviço (cfo-register-retry) que tenta
# sozinho a cada 2 min até o PANEL_TOKEN/PANEL_BASE_URL estarem certos — então
# registra, persiste o INSTANCE_ID, reinicia os daemons e se desliga.
INSTANCE_ID=""
REGISTER_RESP=""
for _try in 1 2 3; do
    REGISTER_RESP=$(curl -s --max-time 30 -X POST "${PANEL_BASE_URL}/instance-register" \
        -H "Content-Type: application/json" \
        -H "X-Panel-Token: ${PANEL_TOKEN}" \
        --data-binary "@${REGISTER_BODY_FILE}")
    NEW_INSTANCE_ID=$(printf '%s' "$REGISTER_RESP" | python3 -c "
import sys, json
try: print(json.loads(sys.stdin.read()).get('instance_id',''))
except: print('')
" 2>/dev/null || echo "")
    [[ -n "$NEW_INSTANCE_ID" ]] && { INSTANCE_ID="$NEW_INSTANCE_ID"; break; }
    [[ $_try -lt 3 ]] && { warn "Registro no painel falhou (tentativa ${_try}/3) — retentando em 5s..."; sleep 5; }
done

if [[ -n "$INSTANCE_ID" ]]; then
    _persist_instance_id "$INSTANCE_ID"
    ok "Instância registrada: $INSTANCE_ID"
else
    warn "Não consegui registrar no painel agora (a instalação CONTINUA)."
    warn "Resposta do painel: ${REGISTER_RESP:-<vazia>}"
    warn "Provável causa: PANEL_TOKEN não bate com o secret do painel, ou PANEL_BASE_URL."
    _install_register_retry_service && \
        ok "Serviço cfo-register-retry ativo — vai registrar sozinho quando estiver tudo certo."
fi
export INSTANCE_ID

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 13: Registrar cron jobs + doctor final
# ─────────────────────────────────────────────────────────────────────────────
step "13/13 — Cron jobs e diagnóstico"

SCRIPTS_DIR="$SKILL_DEST/scripts"
PROMPTS_DIR="$SKILL_DEST/prompts"

# Aguarda o gateway ficar pronto antes de adicionar crons (senão 'openclaw cron add'
# falha com "Gateway not yet ready to accept connections" e abortava o setup).
info "Aguardando o gateway OpenClaw ficar pronto para aceitar comandos..."
for _i in $(seq 1 24); do
    if openclaw cron list --json >/dev/null 2>&1; then
        ok "Gateway pronto."
        break
    fi
    sleep 5
done

[[ -f "$CRON_IDS_FILE" ]] && source "$CRON_IDS_FILE" 2>/dev/null || true

_add_cron_if_missing() {
    local var_name="$1" cron_cmd="$2"

    if [[ -n "${!var_name:-}" ]]; then
        if openclaw cron list --json 2>/dev/null | \
            python3 -c "
import sys, json
jobs = json.load(sys.stdin)
ids = [j.get('id') or j.get('jobId','') for j in jobs]
print('exists' if '${!var_name}' in ids else 'missing')
" 2>/dev/null | grep -q "exists"; then
            ok "$var_name já existe — pulando."
            return
        fi
    fi

    local new_id
    new_id=$(eval "$cron_cmd" 2>&1 | python3 -c "
import sys, json, re
raw = sys.stdin.read()
try:
    d = json.loads(raw)
    print(d.get('id') or d.get('jobId',''))
except:
    m = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', raw)
    print(m.group() if m else '')
" 2>/dev/null || echo "")

    if [[ -z "$new_id" ]] || ! echo "$new_id" | grep -qP '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'; then
        # NÃO-FATAL: os crons são features proativas (alertas, insights), não o núcleo do agente.
        # Um cron que falha (ex: gateway ainda inicializando) não deve abortar a instalação inteira.
        warn "Não foi possível adicionar o cron '${var_name}' (gateway pode estar inicializando). Pulando — adicione depois com 'openclaw cron add' ou re-rodando o setup."
        return
    fi

    export "$var_name"="$new_id"
    { grep -v "^${var_name}=" "$CRON_IDS_FILE" 2>/dev/null || true; echo "${var_name}=${new_id}"; } \
        > "${CRON_IDS_FILE}.tmp" && mv "${CRON_IDS_FILE}.tmp" "$CRON_IDS_FILE"
    ok "$var_name: $new_id"
}

_add_cron_if_missing "CRON_ID_MANHA" \
    "openclaw cron add --name 'CFO Alerta Manhã' --cron '0 7 * * *' --tz 'America/Sao_Paulo' --session isolated --message 'Execute: bash ${SCRIPTS_DIR}/cfo-reporter.sh ${PROMPTS_DIR}/alerta_manha.md' --no-deliver --json"

_add_cron_if_missing "CRON_ID_TARDE" \
    "openclaw cron add --name 'CFO Alerta Tarde' --cron '0 18 * * *' --tz 'America/Sao_Paulo' --session isolated --message 'Execute: bash ${SCRIPTS_DIR}/cfo-reporter.sh ${PROMPTS_DIR}/alerta_tarde.md' --no-deliver --json"

_add_cron_if_missing "CRON_ID_HEARTBEAT" \
    "openclaw cron add --name 'CFO Heartbeat' --cron '*/5 * * * *' --tz 'America/Sao_Paulo' --session isolated --message 'Execute: bash ${SCRIPTS_DIR}/heartbeat.sh' --no-deliver --light-context --json"

_add_cron_if_missing "CRON_ID_BUDGET" \
    "openclaw cron add --name 'CFO Budget Check' --cron '0 3 * * *' --tz 'America/Sao_Paulo' --session isolated --message 'Execute: bash ${SCRIPTS_DIR}/check-budget.sh' --no-deliver --json"

_add_cron_if_missing "CRON_ID_WA_WATCH" \
    "openclaw cron add --name 'CFO WhatsApp Watch' --cron '*/30 * * * *' --tz 'America/Sao_Paulo' --session isolated --message 'Execute: bash ${SCRIPTS_DIR}/whatsapp-watch.sh' --no-deliver --light-context --json"

_add_cron_if_missing "CRON_ID_MARCOS_INSIGHTS" \
    "openclaw cron add --name 'CFO Marcos Insights' --cron '*/15 * * * *' --tz 'America/Sao_Paulo' --session isolated --message 'Execute: python3 ${SCRIPTS_DIR}/marcos_insight_generator.py' --no-deliver --light-context --json"

# Sprint 45 — Backup diário automático às 03:00
_add_cron_if_missing "CRON_ID_BACKUP" \
    "openclaw cron add --name 'CFO Backup Diário' --cron '0 3 * * *' --tz 'America/Sao_Paulo' --session isolated --message 'Execute: bash ${SCRIPTS_DIR}/backup_config.sh >> ${LOG_DIR}/backup.log 2>&1 && echo Backup OK' --no-deliver --light-context --json"

# Sprint INT-2: saúde mensal de integrações (dia 1 às 09:00)
_add_cron_if_missing "CRON_ID_INTEGRATIONS_HEALTH" \
    "openclaw cron add --name 'CFO Saúde Integrações Mensal' --cron '0 9 1 * *' --tz 'America/Sao_Paulo' --session isolated --no-deliver --light-context --json \
     --message 'Execute: bash \$HOME/.openclaw/workspace/skills/agente-cfo/scripts/integrations_health_monthly.sh'"

# Cria diretório de backups e chmod no script
mkdir -p "${HOME}/.agente-cfo/backups"
chmod +x "${SCRIPTS_DIR}/backup_config.sh" "${SCRIPTS_DIR}/restore_config.sh" 2>/dev/null || true

ok "Cron jobs registrados. IDs em: $CRON_IDS_FILE"

# ── PHD-2: Crons proativos do CFO doutor ─────────────────────────────────────
# Ronda matinal, vespertina, relatório semanal e mensal.
# Usa _add_cron_if_missing com fallback warn (não aborta o setup se falhar).
step "PHD-2 — Crons proativos CFO"

_add_cron_phd2() {
    local var_name="$1" cron_cmd="$2"
    # Verifica se já existe pelo nome no cron list
    local _existing
    _existing=$(openclaw cron list --json 2>/dev/null | python3 -c "
import sys, json
try:
    jobs = json.load(sys.stdin)
    names = [j.get('name','') or j.get('jobName','') for j in jobs]
    print('exists' if any('${var_name}' in n or '${var_name}'.replace('_','-').lower() in n.lower() for n in names) else 'missing')
except:
    print('missing')
" 2>/dev/null || echo "missing")

    if [[ "$_existing" == "exists" ]]; then
        ok "Cron '${var_name}' já existe — pulando."
        return
    fi

    local new_id
    new_id=$(eval "$cron_cmd" 2>&1 | python3 -c "
import sys, json, re
raw = sys.stdin.read()
try:
    d = json.loads(raw)
    print(d.get('id') or d.get('jobId',''))
except:
    m = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', raw)
    print(m.group() if m else '')
" 2>/dev/null || echo "") || new_id=""

    if [[ -n "$new_id" ]]; then
        { grep -v "^${var_name}=" "$CRON_IDS_FILE" 2>/dev/null || true; echo "${var_name}=${new_id}"; } \
            > "${CRON_IDS_FILE}.tmp" && mv "${CRON_IDS_FILE}.tmp" "$CRON_IDS_FILE"
        ok "Cron ${var_name}: $new_id"
    else
        warn "Cron '${var_name}' não pôde ser criado — continuando. (executar manualmente depois: $cron_cmd)"
    fi
}

# Ronda matinal 07h
_add_cron_phd2 "CRON_ID_RONDA_MANHA" \
    "openclaw cron add --name 'CFO Ronda Matinal PhD' --cron '0 7 * * *' --tz 'America/Sao_Paulo' --session isolated --no-deliver --light-context --json \
     --message 'Execute o script de ronda matinal para fazer discovery financeiro proativo e enviar snapshot ao dono:\nbash \$HOME/.openclaw/workspace/skills/agente-cfo/scripts/ronda_matinal.sh'"

# Ronda vespertina 18h
_add_cron_phd2 "CRON_ID_RONDA_TARDE" \
    "openclaw cron add --name 'CFO Ronda Vespertina PhD' --cron '0 18 * * *' --tz 'America/Sao_Paulo' --session isolated --no-deliver --light-context --json \
     --message 'Execute o script de ronda vespertina para detectar anomalias do dia e alertar o dono se relevante (silencia se nada relevante):\nbash \$HOME/.openclaw/workspace/skills/agente-cfo/scripts/ronda_vespertina.sh'"

# Relatório semanal — sexta 16h
_add_cron_phd2 "CRON_ID_REL_SEMANAL" \
    "openclaw cron add --name 'CFO Relatório Semanal PhD' --cron '0 16 * * 5' --tz 'America/Sao_Paulo' --session isolated --no-deliver --json \
     --message 'Execute o relatório semanal executivo e envie resumo ao dono:\nbash \$HOME/.openclaw/workspace/skills/agente-cfo/scripts/relatorio_semanal.sh'"

# Relatório mensal — dia 1 às 08h
_add_cron_phd2 "CRON_ID_REL_MENSAL" \
    "openclaw cron add --name 'CFO Relatório Mensal PhD' --cron '0 8 1 * *' --tz 'America/Sao_Paulo' --session isolated --no-deliver --json \
     --message 'Execute o relatório mensal completo (DRE + comparativo MoM) e envie ao dono:\nbash \$HOME/.openclaw/workspace/skills/agente-cfo/scripts/relatorio_mensal.sh'"

ok "Crons proativos PHD-2 registrados."

# ── RECON-1: Cron de conciliação diária 06:30 ─────────────────────────────────
_add_cron_phd2 "CRON_ID_CONCILIACAO" \
    "openclaw cron add --name 'CFO Conciliação Diária' --cron '30 6 * * *' \
     --tz 'America/Sao_Paulo' --session isolated --no-deliver --light-context --json \
     --message 'Execute a conciliação cross-sistema (cobrança/ecommerce/crm/lançamentos manuais vs ERP). Silencia se zero divergências:\nbash \$HOME/.openclaw/workspace/skills/agente-cfo/scripts/conciliacao_diaria.sh'"
ok "Cron conciliação diária (06:30) registrado — RECON-1."

# Doctor final
info "Executando diagnóstico final..."
export LICENSE_KEY="" OMIE_APP_KEY OMIE_APP_SECRET INSTANCE_ID PANEL_BASE_URL PANEL_TOKEN
export CFO_LOG_DIR="$LOG_DIR" CFO_STATE_DIR="$STATE_DIR"
export OMIE_SKILL_PATH="${HOME}/.openclaw/workspace/skills/omie"

DOCTOR_EXIT=0
bash "${SKILL_DEST}/scripts/doctor.sh" || DOCTOR_EXIT=$?

# Smoke test de integrações MCP (Sprint 29) + master test runner (Sprint 48)
STATUS_SCRIPT="${SKILL_DEST}/scripts/integration_status.sh"
if [[ -f "$STATUS_SCRIPT" ]]; then
    step "Integration MCP status"
    chmod +x "$STATUS_SCRIPT"
    bash "$STATUS_SCRIPT" || true
fi

RUN_ALL_SCRIPT="${HOME}/.openclaw/workspace/tests/run_all.sh"
if [[ -f "$RUN_ALL_SCRIPT" ]]; then
    step "Master smoke test (Sprint 48)"
    chmod +x "$RUN_ALL_SCRIPT"
    bash "$RUN_ALL_SCRIPT" --fast --no-panel 2>&1 | tail -10 || \
        warn "Algum smoke test falhou — ver acima para detalhes"
fi

# ── Verificação de conexão e instalação (as 3 garantias) ─────────────────────
# Checa e REPORTA explicitamente: OpenClaw up, skills presentes, conexão com o
# painel (handshake) e ativação da VPS no front (registro).
step "Verificação de conexão e instalação"

_SMOKE_PASS=0; _SMOKE_FAIL=0
_smoke_check() {
    local label="$1" result="$2"
    if [[ "$result" == "OK" ]]; then
        echo -e "  ${GREEN}✅${NC} $label"
        _SMOKE_PASS=$((_SMOKE_PASS+1))
    else
        echo -e "  ${RED}❌${NC} $label — $result"
        _SMOKE_FAIL=$((_SMOKE_FAIL+1))
    fi
}

# 1. Verificar que todas as 20 skills CFO estão instaladas
_SKILLS_ROOT="${HOME}/.openclaw/workspace/skills"
_CFO_EXPECTED=(
    cfo-analise-estrategica cfo-projecao cfo-inadimplencia cfo-anomalias
    cfo-tributacao-br cfo-cobranca-orquestrada cfo-relatorios-executivos
    cfo-conciliacao-cobranca-erp cfo-conciliacao-ecommerce-erp
    cfo-conciliacao-crm-erp cfo-conciliacao-manual-erp cfo-conciliacao-bancaria
    cfo-aprendizado-padrao cfo-acao-composta
    cfo-planejamento cfo-cenarios-nomeados cfo-what-if cfo-calendario-acoes
    cfo-sensitivity cfo-decisao-estrategica
)
_CFO_MISSING=0
for _s in "${_CFO_EXPECTED[@]}"; do
    [[ -f "${_SKILLS_ROOT}/${_s}/SKILL.md" ]] || _CFO_MISSING=$((_CFO_MISSING+1))
done
if [[ $_CFO_MISSING -eq 0 ]]; then
    _smoke_check "20 skills CFO instaladas" "OK"
else
    _smoke_check "Skills CFO" "${_CFO_MISSING} skill(s) ausentes (re-execute setup.sh)"
fi

# 2. Verificar integrations_status.sh
_INTEG_SCRIPT="${SKILL_DEST}/scripts/integrations_status.sh"
if [[ -f "$_INTEG_SCRIPT" ]]; then
    _INTEG_OUT=$(bash "$_INTEG_SCRIPT" 2>&1 || true)
    echo "$_INTEG_OUT" | grep -qiE '✅|OK|connected|ativo' && \
        _smoke_check "integrations_status.sh" "OK" || \
        _smoke_check "integrations_status.sh" "sem integrações ativas (cole credenciais no painel)"
else
    _smoke_check "integrations_status.sh" "script não encontrado (non-critical)"
fi

# 3. Verificar visao_consolidada.sh
_VISAO_SCRIPT="${SKILL_DEST}/scripts/visao_consolidada.sh"
if [[ -f "$_VISAO_SCRIPT" ]]; then
    _VISAO_OUT=$(bash "$_VISAO_SCRIPT" 2>&1 | head -5 || true)
    [[ -n "$_VISAO_OUT" ]] && \
        _smoke_check "visao_consolidada.sh executou" "OK" || \
        _smoke_check "visao_consolidada.sh" "sem saída — verifique OMIE_APP_KEY"
else
    _smoke_check "visao_consolidada.sh" "script não encontrado (non-critical)"
fi

# 4. Verificar gateway ativo
if curl -fs http://127.0.0.1:18789/__openclaw__/canvas/ >/dev/null 2>&1 || \
   ss -tlnp 2>/dev/null | grep -q ':18789'; then
    _smoke_check "OpenClaw Gateway ativo (porta 18789)" "OK"
else
    _smoke_check "OpenClaw Gateway" "não encontrado na porta 18789"
fi

# 5. Verificar AGENTS.md PhD aplicado
if [[ -f "${HOME}/.openclaw/workspace/AGENTS.md" ]] && \
   grep -qiE 'Marcos|CFO|PhD|Planejador|Conciliação' "${HOME}/.openclaw/workspace/AGENTS.md" 2>/dev/null; then
    _smoke_check "AGENTS.md PhD aplicado" "OK"
else
    _smoke_check "AGENTS.md PhD" "não aplicado ou incompleto"
fi

# 6. Conexão painel↔VPS (handshake: o PANEL_TOKEN é aceito pelo painel?)
_verify_panel_token; _HS_RC=$?
if [[ $_HS_RC -eq 0 ]]; then
    _smoke_check "Conexão com o painel (token aceito)" "OK"
elif [[ $_HS_RC -eq 2 ]]; then
    _smoke_check "Conexão com o painel" "painel inacessível em ${PANEL_BASE_URL}"
else
    _smoke_check "Conexão com o painel" "PANEL_TOKEN não bate com o secret do painel (${PANEL_BASE_URL%/functions/v1})"
fi

# 7. Ativação da VPS no painel (instância registrada → aparece online no front?)
if [[ -n "${INSTANCE_ID:-}" ]]; then
    _smoke_check "VPS ativada no painel (instance_id)" "OK"
else
    _smoke_check "VPS ativada no painel" "registro pendente — cfo-register-retry conecta quando o token bater"
fi

echo ""
_SMOKE_TOTAL=$((_SMOKE_PASS + _SMOKE_FAIL))
if [[ $_SMOKE_FAIL -eq 0 ]]; then
    echo -e "${GREEN}✅ Verificação pós-instalação: TUDO OK (${_SMOKE_PASS}/${_SMOKE_TOTAL} checks)${NC}"
else
    echo -e "${YELLOW}⚠️  Verificação pós-instalação: ${_SMOKE_PASS}/${_SMOKE_TOTAL} OK — ${_SMOKE_FAIL} ponto(s) de atenção acima${NC}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Instalação Concluída!               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
if [[ -n "${INSTANCE_ID:-}" ]]; then
    echo -e "  ${GREEN}Instance ID:${NC}  $INSTANCE_ID"
else
    echo -e "  ${YELLOW}Instance ID:${NC}  registro pendente — cfo-register-retry tentando a cada 2 min"
    echo -e "  ${YELLOW}            ${NC}  (confira PANEL_TOKEN no painel; registra sozinho quando bater)"
fi
echo -e "  ${GREEN}Ingress URL:${NC}  ${INGRESS_URL:-não configurada}"
echo -e "  ${GREEN}Doctor:${NC}       $([ $DOCTOR_EXIT -eq 0 ] && echo '✅ tudo verde' || echo '⚠️  veja acima')"
echo ""
echo -e "  ${CYAN}Próximos passos:${NC}"
echo "  • Primeiro alerta chega no WhatsApp às 07:00 de amanhã"
echo "  • Se WhatsApp desconectar: bash ${SKILL_DEST}/scripts/repare.sh"
echo "  • Comando Central: KPIs e insights disponíveis via /dashboard-snapshot"
echo "  • Automações: configure em ${PANEL_BASE_URL}/automations ou via chat com Marcos"
echo "  • Para rollback: systemctl stop cfo-automation-engine && systemctl start cfo-proactive"
echo "  • Diagnóstico: bash ${SKILL_DEST}/scripts/doctor.sh"
echo "  • Logs inbound:   ${LOG_DIR}/wacli-inbound.log"
echo "  • Logs proativo:  ${LOG_DIR}/proactive.log"
echo "  • Logs: $LOG_DIR"
echo ""

[[ $DOCTOR_EXIT -ne 0 ]] && { warn "Doctor detectou falhas. Veja ❌ acima."; exit 1; }
ok "Agente CFO instalado e operacional. Boas vendas! 💼"
