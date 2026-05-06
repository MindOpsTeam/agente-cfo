#!/usr/bin/env bash
# setup.sh — Instalador ponta-a-ponta do Agente CFO
# Roda em Ubuntu 22.04+ (VPS limpa). Idempotente.
#
# Uso interativo:    bash setup.sh
# Uso não-interativo (todas as vars preset no ambiente):
#   OMIE_APP_KEY=... OMIE_APP_SECRET=... CFO_WHATSAPP_TO=+55... \
#   ANTHROPIC_API_KEY=sk-ant-... LLM_BUDGET_BRL=50 \
#   PANEL_BASE_URL=https://xxx.supabase.co/functions/v1 \
#   bash setup.sh
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
echo -e "${CYAN}║         Agente CFO — Instalador v1.0             ║${NC}"
echo -e "${CYAN}║   CFO virtual para PME brasileira via Omie+WA    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
info "Iniciando instalação em: $(hostname) — $(date '+%Y-%m-%d %H:%M:%S')"
mkdir -p "$LOG_DIR" "$STATE_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Pre-flight
# ─────────────────────────────────────────────────────────────────────────────
step "1/12 — Verificando dependências"

MISSING=()
for bin in node npm python3 curl jq git openssl; do
    command -v "$bin" &>/dev/null && ok "$bin ok" || MISSING+=("$bin")
done

[[ ${#MISSING[@]} -gt 0 ]] && fail "Dependências ausentes: ${MISSING[*]}
Instale com:
  apt-get update && apt-get install -y nodejs npm python3 curl jq git openssl"

NODE_VER=$(node --version | tr -d 'v' | cut -d. -f1)
[[ "$NODE_VER" -lt 18 ]] && fail "Node.js >= 18 obrigatório (encontrado: $(node --version))"
ok "Dependências OK."

# ── Pre-flight 1b: validar flags do openclaw cron add ────────────────────────
# As flags abaixo são usadas no PASSO 12. Se não existirem nessa versão do
# OpenClaw, os cron jobs seriam registrados errado e o setup terminaria verde
# com IDs falsos. Melhor falhar aqui, antes de fazer qualquer mudança.
if command -v openclaw &>/dev/null; then
    info "Verificando suporte a flags de 'openclaw cron add'..."
    _CRON_HELP=$(openclaw cron add --help 2>&1 || true)
    _OC_VERSION=$(openclaw --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "desconhecida")
    _CRON_FLAGS_OK=1

    for _flag in "--no-deliver" "--light-context" "--session" "--json"; do
        if echo "$_CRON_HELP" | grep -qF "$_flag"; then
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
step "2/12 — OpenClaw"

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
step "3/12 — Credenciais"

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
# PASSO 4: PANEL_BASE_URL e PANEL_TOKEN
# ─────────────────────────────────────────────────────────────────────────────
step "4/12 — Painel (Supabase do cliente)"

ask "PANEL_BASE_URL" \
    "URL do seu projeto Supabase (ex: https://xxxx.supabase.co/functions/v1)"

# Validar formato básico
[[ "$PANEL_BASE_URL" =~ ^https://[a-z0-9]+\.supabase\.co/functions/v1 ]] || \
    warn "PANEL_BASE_URL não parece uma URL Supabase válida. Continuando."
# Normalizar: remover barra final
PANEL_BASE_URL="${PANEL_BASE_URL%/}"

# Gerar PANEL_TOKEN se não definido
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
step "5/12 — Gerando hooks token"

if [[ -z "${HOOKS_TOKEN:-}" ]]; then
    HOOKS_TOKEN=$(openssl rand -hex 16)
    ok "HOOKS_TOKEN gerado."
else
    ok "HOOKS_TOKEN já definido."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 6: Parear WhatsApp
# ─────────────────────────────────────────────────────────────────────────────
step "6/12 — Pareamento WhatsApp"

if wacli doctor 2>&1 | grep -qi "connected\|ok\|pareado"; then
    ok "WhatsApp já pareado — pulando."
else
    info "Iniciando pareamento WhatsApp..."
    echo ""
    echo "INSTRUÇÃO:"
    echo "  1. WhatsApp no celular → ⋮ → Dispositivos conectados"
    echo "  2. Conectar um dispositivo → aponte para o QR code"
    echo ""
    read -rp "Pressione ENTER para exibir o QR code..."

    wacli auth || fail "Falha no pareamento. Execute 'wacli auth' manualmente e tente de novo."

    sleep 2
    wacli doctor 2>&1 | grep -qi "connected\|ok" || \
        fail "WhatsApp pareado mas não conectado. Verifique 'wacli doctor'."
    ok "WhatsApp pareado."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 7: Cloudflare Tunnel
# ─────────────────────────────────────────────────────────────────────────────
step "7/12 — Cloudflare Tunnel"

if ! command -v cloudflared &>/dev/null; then
    info "Instalando cloudflared..."
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  CF_ARCH="amd64" ;;
        aarch64) CF_ARCH="arm64" ;;
        *)        fail "Arquitetura não suportada: $ARCH" ;;
    esac
    curl -fsSL \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" \
        -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
    ok "cloudflared instalado."
else
    ok "cloudflared já instalado."
fi

# Configurar gateway OpenClaw como serviço
OPENCLAW_SVC="/etc/systemd/system/openclaw-gateway.service"
if [[ ! -f "$OPENCLAW_SVC" ]]; then
    cat > "$OPENCLAW_SVC" << EOF
[Unit]
Description=OpenClaw Gateway (Agente CFO)
After=network.target

[Service]
Type=simple
User=${USER}
Environment=HOME=${HOME}
Environment=OPENCLAW_NO_RESPAWN=1
Environment=NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
EnvironmentFile=${ENV_FILE}
ExecStart=$(command -v openclaw) gateway start
Restart=always
RestartSec=5
TimeoutStartSec=90

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable openclaw-gateway 2>/dev/null || true
    ok "Serviço openclaw-gateway configurado."
else
    ok "Serviço openclaw-gateway já existe."
fi

# Subir tunnel e capturar URL (apenas se INGRESS_URL não estiver definida)
if [[ -n "${INGRESS_URL:-}" ]]; then
    ok "INGRESS_URL já definida: $INGRESS_URL — pulando."
else
    info "Subindo Cloudflare Tunnel..."
    TUNNEL_LOG=$(mktemp /tmp/cfd-XXXXXX.log)

    cloudflared tunnel --url "http://localhost:18789" \
        --logfile "$TUNNEL_LOG" --no-autoupdate &
    TUNNEL_PID=$!

    INGRESS_URL=""
    for i in $(seq 1 30); do
        sleep 1
        INGRESS_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || echo "")
        [[ -n "$INGRESS_URL" ]] && break
    done
    rm -f "$TUNNEL_LOG"

    [[ -z "$INGRESS_URL" ]] && { kill "$TUNNEL_PID" 2>/dev/null || true;
        fail "Não foi possível capturar a URL do Tunnel. Verifique conectividade."; }

    echo "$TUNNEL_PID" > "${STATE_DIR}/cloudflared.pid"
    ok "Tunnel ativo: $INGRESS_URL"

    # Configurar como serviço
    CF_SVC="/etc/systemd/system/cloudflared-cfo.service"
    if [[ ! -f "$CF_SVC" ]]; then
        cat > "$CF_SVC" << EOF
[Unit]
Description=Cloudflare Tunnel (Agente CFO)
After=network.target openclaw-gateway.service

[Service]
Type=simple
User=${USER}
ExecStart=$(command -v cloudflared) tunnel --url http://localhost:18789 --no-autoupdate
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable cloudflared-cfo 2>/dev/null || true
        ok "Serviço cloudflared-cfo configurado."
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 8: Instalar skill omie
# ─────────────────────────────────────────────────────────────────────────────
step "8/12 — Skill omie"

OMIE_DEST="${HOME}/.openclaw/workspace/skills/omie"
if [[ -d "$OMIE_DEST" ]]; then
    ok "Skill omie já instalada."
else
    openclaw skills install omie 2>&1 || \
        fail "Falha ao instalar skill omie."
    ok "Skill omie instalada."
fi

[[ -f "$OMIE_DEST/requirements.txt" ]] && \
    pip3 install -r "$OMIE_DEST/requirements.txt" -q 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 9: Instalar skill agente-cfo
# ─────────────────────────────────────────────────────────────────────────────
step "9/12 — Skill agente-cfo"

if [[ -d "$SKILL_DEST" && -f "$SKILL_DEST/SKILL.md" ]]; then
    ok "Skill agente-cfo já instalada. Atualizando..."
    git -C "$SKILL_DEST" pull --ff-only 2>/dev/null || warn "git pull falhou (ignorado)."
else
    info "Clonando skill de $SKILL_REPO..."
    mkdir -p "$(dirname "$SKILL_DEST")"
    git clone --depth 1 --filter=blob:none --sparse "$SKILL_REPO" /tmp/agente-cfo-clone 2>/dev/null || \
        fail "Falha ao clonar $SKILL_REPO — verifique se o repositório é público."
    cd /tmp/agente-cfo-clone
    git sparse-checkout set skills/agente-cfo
    cp -r skills/agente-cfo "$SKILL_DEST"
    cd / && rm -rf /tmp/agente-cfo-clone
    ok "Skill agente-cfo instalada em $SKILL_DEST"
fi

chmod +x "$SKILL_DEST/scripts/"*.sh

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 10: Persistir env
# ─────────────────────────────────────────────────────────────────────────────
step "10/12 — Persistindo configuração"

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
INGRESS_URL=${INGRESS_URL:-}
HOOKS_TOKEN=${HOOKS_TOKEN}
OMIE_SKILL_PATH=${HOME}/.openclaw/workspace/skills/omie
INSTANCE_ID=
EOF
chmod 600 "$ENV_FILE"
ok "Config salva em $ENV_FILE (chmod 600)."

# Exportar ANTHROPIC_API_KEY para o OpenClaw
grep -q "ANTHROPIC_API_KEY" "${HOME}/.bashrc" 2>/dev/null || \
    echo "export ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> "${HOME}/.bashrc"

# shellcheck source=/dev/null
source "$ENV_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 11: Registrar instância no painel
# ─────────────────────────────────────────────────────────────────────────────
step "11/12 — Registrando no painel"

# Verificar se já está registrado (idempotência)
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
# PASSO 12: Registrar cron jobs + doctor final
# ─────────────────────────────────────────────────────────────────────────────
step "12/12 — Cron jobs e diagnóstico"

SCRIPTS_DIR="$SKILL_DEST/scripts"
PROMPTS_DIR="$SKILL_DEST/prompts"

# Carregar IDs existentes
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

    # UUID válido é obrigatório — setup nunca termina verde com ID falso.
    if [[ -z "$new_id" ]] || ! echo "$new_id" | grep -qP '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'; then
        fail "Não foi possível capturar um UUID válido para o cron '${var_name}'.
Saída do comando:
$(eval "$cron_cmd" 2>&1 | head -20)

Verifique:
  • OpenClaw está rodando? (openclaw gateway status)
  • Flags suportadas? (openclaw cron add --help)
  • Execute manualmente e veja o output: ${cron_cmd}"
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

ok "Cron jobs registrados. IDs em: $CRON_IDS_FILE"

# Iniciar serviços
systemctl start openclaw-gateway 2>/dev/null || warn "openclaw-gateway: não iniciou via systemctl."
systemctl start cloudflared-cfo  2>/dev/null || warn "cloudflared-cfo: não iniciou via systemctl."

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
echo "  • Diagnóstico: bash ${SKILL_DEST}/scripts/doctor.sh"
echo "  • Logs: $LOG_DIR"
echo ""

[[ $DOCTOR_EXIT -ne 0 ]] && { warn "Doctor detectou falhas. Veja ❌ acima."; exit 1; }
ok "Agente CFO instalado e operacional. Boas vendas! 💼"
