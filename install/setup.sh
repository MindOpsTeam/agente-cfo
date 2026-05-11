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

ask() {
    local var_name="$1" description="$2" default_val="${3:-}"
    if [[ -n "${!var_name:-}" ]]; then
        ok "$description: já definido."
        return
    fi
    local prompt_str="$description"
    [[ -n "$default_val" ]] && prompt_str="$description [${default_val}]"
    local value=""
    while [[ -z "$value" ]]; do
        read -rp "$(echo -e "${CYAN}?${NC} ${prompt_str}: ")" value
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

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Pre-flight
# ─────────────────────────────────────────────────────────────────────────────
step "1/13 — Verificando dependências"

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

    local _ans
    read -rp "$(echo -e "${CYAN}?${NC} Posso instalar Node 22 LTS via apt? (S/n): ")" _ans
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

# ── Pre-flight 1b: validar flags do openclaw cron add ────────────────────────
if command -v openclaw &>/dev/null; then
    info "Verificando suporte a flags de 'openclaw cron add'..."
    _CRON_HELP=$(openclaw cron add --help 2>&1 || true)
    _OC_VERSION=$(openclaw --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "desconhecida")
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

ask "OMIE_APP_KEY"      "Omie App Key"
ask "OMIE_APP_SECRET"   "Omie App Secret"
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
    echo ""
    info "$description"
    info "Opcoes: $options"
    read -rp "$(echo -e "${CYAN}?${NC} Escolha (vazio = $default): ")" _choice
    export "$var_name"="${_choice:-$default}"
}

ask_choice "CFO_ERP_NAME"       "Qual ERP voce usa?" "omie / bling / tiny / granatum / vhsys / nibo / contaazul" "omie"
ask_choice "CFO_CRM_NAME"       "Quer conectar um CRM?" "hubspot / rd-station / piperun / pipedrive / nenhum" "nenhum"
ask_choice "CFO_COBRANCA_NAME"  "Plataforma de cobranca?" "asaas / iugu / nenhum" "nenhum"
ask_choice "CFO_ECOMMERCE_NAME" "Plataforma de e-commerce?" "mercado-livre / nuvemshop / nenhum" "nenhum"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: PANEL_BASE_URL e PANEL_TOKEN
# ─────────────────────────────────────────────────────────────────────────────
step "4/13 — Painel (Supabase do cliente)"

ask "PANEL_BASE_URL" \
    "URL do seu projeto Supabase (ex: https://xxxx.supabase.co/functions/v1)"

[[ "$PANEL_BASE_URL" =~ ^https://[a-z0-9]+\.supabase\.co/functions/v1 ]] || \
    warn "PANEL_BASE_URL não parece uma URL Supabase válida. Continuando."
PANEL_BASE_URL="${PANEL_BASE_URL%/}"

if [[ -z "${PANEL_TOKEN:-}" ]]; then
    PANEL_TOKEN=$(openssl rand -hex 32)
    ok "PANEL_TOKEN gerado."
else
    ok "PANEL_TOKEN já definido via ambiente."
fi

echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║  ⚠️  AÇÃO NECESSÁRIA — Configure o PANEL_TOKEN no Supabase  ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  1. Abra: ${PANEL_BASE_URL/functions\/v1/} → Settings → Edge Functions"
echo "  2. Clique em 'Add new secret'"
echo "  3. Name:  PANEL_TOKEN"
echo "  4. Value: ${PANEL_TOKEN}"
echo ""
echo -e "${YELLOW}  ⚠️  Sem esse secret, a VPS não consegue se comunicar com o painel.${NC}"
echo ""
read -rp "Pressione ENTER após configurar o secret no Supabase..."

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
ok "gateway.mode=local configurado."

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
else
    info "Iniciando pareamento WhatsApp..."
    echo ""
    echo "INSTRUÇÃO:"
    echo "  1. WhatsApp no celular → ⋮ → Dispositivos conectados"
    echo "  2. Conectar um dispositivo → aponte para o QR code"
    echo ""
    read -rp "Pressione ENTER para exibir o QR code..."

    wacli auth || fail "Falha no pareamento. Execute 'wacli auth' manualmente e tente de novo."

    sleep 3
    _wacli_connected || \
        warn "WhatsApp pareado mas conexão ainda não confirmada. Verifique 'wacli doctor' após o setup."
    ok "WhatsApp pareado."
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

cat > "$ENV_FILE" << EOF
# Agente CFO — gerado por setup.sh em $(date '+%Y-%m-%d %H:%M:%S')
OMIE_APP_KEY=${OMIE_APP_KEY}
OMIE_APP_SECRET=${OMIE_APP_SECRET}
CFO_WHATSAPP_TO=${CFO_WHATSAPP_TO}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
LLM_BUDGET_BRL=${LLM_BUDGET_BRL}
PANEL_BASE_URL=${PANEL_BASE_URL}
PANEL_TOKEN=${PANEL_TOKEN}
INGRESS_URL=
HOOKS_TOKEN=${HOOKS_TOKEN}
CFO_ERP_NAME=${CFO_ERP_NAME:-omie}
CFO_CRM_NAME=${CFO_CRM_NAME:-nenhum}
CFO_COBRANCA_NAME=${CFO_COBRANCA_NAME:-nenhum}
CFO_ECOMMERCE_NAME=${CFO_ECOMMERCE_NAME:-nenhum}
OMIE_SKILL_PATH=${HOME}/.openclaw/workspace/skills/omie
INSTANCE_ID=
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

systemctl daemon-reload
info "Systemd units criados: openclaw-gateway, cloudflared-cfo, wacli-sync, wacli-inbound, cfo-proactive, cfo-automation-engine."

# Iniciar gateway e aguardar responder
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
echo "INGRESS_URL=${INGRESS_URL}" >> "$ENV_FILE"
chmod 600 "$ENV_FILE"
ok "INGRESS_URL persistida no .env."

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
    git clone --depth 1 --filter=blob:none --sparse "$SKILL_REPO" "$clone_dir" 2>/dev/null || \
        fail "Falha ao clonar $SKILL_REPO para skill ${skill_name}."
    cd "$clone_dir"
    git sparse-checkout set "skills/${skill_name}" "skills/_lib"
    mkdir -p "${HOME}/.openclaw/workspace/skills"
    cp -r "skills/${skill_name}" "$dest"
    # Instalar/atualizar _lib (BaseERPClient/BaseCRMClient)
    mkdir -p "${HOME}/.openclaw/workspace/skills/_lib"
    cp -r "skills/_lib/"* "${HOME}/.openclaw/workspace/skills/_lib/"
    cd / && rm -rf "$clone_dir"

    chmod +x "$dest/scripts/"*.sh 2>/dev/null || true
    ok "Skill ${skill_name} instalada de ${SKILL_REPO}."
}

# Sempre instalar omie do monorepo (versão com get_balance/list_payables/etc)
_install_skill_from_repo "omie"

# Instalar requirements.txt se existir
OMIE_DEST="${HOME}/.openclaw/workspace/skills/omie"
[[ -f "$OMIE_DEST/requirements.txt" ]] && \
    pip3 install -r "$OMIE_DEST/requirements.txt" -q 2>/dev/null || true

# Instalar skill ERP escolhida (se diferente de omie)
if [[ "${CFO_ERP_NAME:-omie}" != "omie" ]]; then
    _install_skill_from_repo "${CFO_ERP_NAME}"
    ERP_SKILL_DEST="${HOME}/.openclaw/workspace/skills/${CFO_ERP_NAME}"
    bash "$ERP_SKILL_DEST/scripts/connect.sh" || warn "connect.sh do ERP falhou — configure manualmente."
fi

# Instalar skill CRM escolhida
if [[ "${CFO_CRM_NAME:-nenhum}" != "nenhum" ]]; then
    _install_skill_from_repo "${CFO_CRM_NAME}"
    CRM_SKILL_DEST="${HOME}/.openclaw/workspace/skills/${CFO_CRM_NAME}"
    bash "$CRM_SKILL_DEST/scripts/connect.sh" || warn "connect.sh do CRM falhou — configure manualmente."
fi

# Instalar skill de cobrança escolhida
if [[ "${CFO_COBRANCA_NAME:-nenhum}" != "nenhum" ]]; then
    _install_skill_from_repo "${CFO_COBRANCA_NAME}"
    COBRANCA_SKILL_DEST="${HOME}/.openclaw/workspace/skills/${CFO_COBRANCA_NAME}"
    bash "$COBRANCA_SKILL_DEST/scripts/connect.sh" || warn "connect.sh de cobranca falhou — configure manualmente."
fi

# Instalar skill de e-commerce escolhida
if [[ "${CFO_ECOMMERCE_NAME:-nenhum}" != "nenhum" ]]; then
    _install_skill_from_repo "${CFO_ECOMMERCE_NAME}"
    ECOMMERCE_SKILL_DEST="${HOME}/.openclaw/workspace/skills/${CFO_ECOMMERCE_NAME}"
    bash "$ECOMMERCE_SKILL_DEST/scripts/connect.sh" || warn "connect.sh de e-commerce falhou — configure manualmente."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 11: Instalar skill agente-cfo
# ─────────────────────────────────────────────────────────────────────────────
step "11/13 — Skill agente-cfo"
_install_skill_from_repo "agente-cfo"
chmod +x $SKILL_DEST/scripts/*.sh 2>/dev/null || true
ok "Skill agente-cfo instalada em $SKILL_DEST"

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

REGISTER_BODY=$(printf \
    '{"hostname":"%s","openclaw_version":"%s","agente_cfo_version":"%s","ingress_url":"%s","hooks_token":"%s"}' \
    "$(hostname)" "$OPENCLAW_VER" "$AGENTE_CFO_VER" "${INGRESS_URL:-}" "$HOOKS_TOKEN")

REGISTER_RESP=$(curl -s --max-time 30 -X POST "${PANEL_BASE_URL}/instance-register" \
    -H "Content-Type: application/json" \
    -H "X-Panel-Token: ${PANEL_TOKEN}" \
    -d "$REGISTER_BODY")

NEW_INSTANCE_ID=$(echo "$REGISTER_RESP" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('instance_id',''))
except:
    print('')
" 2>/dev/null || echo "")

if [[ -z "$NEW_INSTANCE_ID" ]]; then
    fail "Falha ao registrar no painel.
Resposta: $REGISTER_RESP
Verifique:
  • PANEL_TOKEN configurado como secret no Supabase?
  • PANEL_BASE_URL correto?
  • Edge function instance-register deployed?"
fi

INSTANCE_ID="$NEW_INSTANCE_ID"
echo "INSTANCE_ID=${INSTANCE_ID}" > "$INSTANCE_ENV"

# Atualizar .env com INSTANCE_ID
grep -v "^INSTANCE_ID=" "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
echo "INSTANCE_ID=${INSTANCE_ID}" >> "$ENV_FILE"
chmod 600 "$ENV_FILE"

ok "Instância registrada: $INSTANCE_ID"
export INSTANCE_ID

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 13: Registrar cron jobs + doctor final
# ─────────────────────────────────────────────────────────────────────────────
step "13/13 — Cron jobs e diagnóstico"

SCRIPTS_DIR="$SKILL_DEST/scripts"
PROMPTS_DIR="$SKILL_DEST/prompts"

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
        fail "Não foi possível capturar UUID válido para '${var_name}'.
Saída:
$(eval "$cron_cmd" 2>&1 | head -20)

Verifique:
  • openclaw gateway status
  • openclaw cron add --help"
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

ok "Cron jobs registrados. IDs em: $CRON_IDS_FILE"

# Doctor final
info "Executando diagnóstico final..."
export LICENSE_KEY="" OMIE_APP_KEY OMIE_APP_SECRET INSTANCE_ID PANEL_BASE_URL PANEL_TOKEN
export CFO_LOG_DIR="$LOG_DIR" CFO_STATE_DIR="$STATE_DIR"
export OMIE_SKILL_PATH="${HOME}/.openclaw/workspace/skills/omie"

DOCTOR_EXIT=0
bash "${SKILL_DEST}/scripts/doctor.sh" || DOCTOR_EXIT=$?

# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Instalação Concluída!               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}Instance ID:${NC}  $INSTANCE_ID"
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
