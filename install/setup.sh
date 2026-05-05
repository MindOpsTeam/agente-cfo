#!/usr/bin/env bash
# setup.sh — Instalador ponta-a-ponta do Agente CFO
# Roda em Ubuntu 22.04+ (VPS limpa). Idempotente.
#
# Uso interativo:    bash setup.sh
# Uso não-interativo (CI/envs presets):
#   LICENSE_KEY=lk_xxx OMIE_APP_KEY=... OMIE_APP_SECRET=... \
#   CFO_WHATSAPP_TO=+55... ANTHROPIC_API_KEY=sk-ant-... \
#   LLM_BUDGET_BRL=50 bash setup.sh
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────
PANEL_BASE_URL="${PANEL_BASE_URL:-https://odhcfrgydjluxunhvojp.supabase.co/functions/v1}"
SKILL_REPO="${SKILL_REPO:-https://github.com/MindOpsTeam/agente-cfo.git}"
SKILL_DEST="${HOME}/.openclaw/workspace/skills/agente-cfo"
ENV_FILE="${HOME}/.agente-cfo/.env"
INSTANCE_ENV="${HOME}/.agente-cfo/instance.env"
CRON_IDS_FILE="${HOME}/.agente-cfo/cron-ids.env"
LOG_DIR="${HOME}/.agente-cfo/logs"
STATE_DIR="${HOME}/.agente-cfo"
OPENCLAW_HOOKS_PORT="${OPENCLAW_HOOKS_PORT:-18790}"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[CFO]${NC} $*"; }
ok()      { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[AVISO]${NC} $*"; }
fail()    {
    echo -e "${RED}[ERRO]${NC} $*" >&2
    echo -e "${RED}[ERRO]${NC} Setup abortado. Corrija o problema acima e execute novamente." >&2
    exit 1
}

ask() {
    # ask VAR_NAME "Descrição" ["default_value"]
    local var_name="$1"
    local description="$2"
    local default_val="${3:-}"

    # Se variável já está definida no ambiente (modo não-interativo), pula
    if [[ -n "${!var_name:-}" ]]; then
        ok "$description já definido via ambiente."
        return
    fi

    local prompt_str="$description"
    [[ -n "$default_val" ]] && prompt_str="$description [${default_val}]"

    local value=""
    while [[ -z "$value" ]]; do
        read -rp "$(echo -e "${CYAN}?${NC} ${prompt_str}: ")" value
        value="${value:-$default_val}"
        if [[ -z "$value" ]]; then
            echo "  ⚠️  Valor obrigatório. Tente novamente."
        fi
    done

    # Exportar no ambiente atual
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
# PASSO 1: Pre-flight — verificar dependências
# ─────────────────────────────────────────────────────────────────────────────
step "1/13 — Verificando dependências"

MISSING=()
for bin in node npm python3 curl jq git; do
    if command -v "$bin" &>/dev/null; then
        ok "$bin: $(command -v "$bin")"
    else
        MISSING+=("$bin")
        warn "$bin: NÃO ENCONTRADO"
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    fail "Dependências ausentes: ${MISSING[*]}
Instale com:
  apt-get update && apt-get install -y nodejs npm python3 curl jq git
  # ou para Node.js mais recente:
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs"
fi

NODE_VER=$(node --version | tr -d 'v' | cut -d. -f1)
if [[ "$NODE_VER" -lt 18 ]]; then
    fail "Node.js >= 18 obrigatório (encontrado: $(node --version))"
fi

ok "Todas as dependências presentes."

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2: Instalar/atualizar OpenClaw
# ─────────────────────────────────────────────────────────────────────────────
step "2/13 — Instalando OpenClaw"

if command -v openclaw &>/dev/null; then
    CURRENT_VER=$(openclaw --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "desconhecida")
    ok "OpenClaw já instalado (versão $CURRENT_VER). Atualizando..."
fi

npm install -g openclaw@latest 2>&1 | tail -3 || fail "Falha ao instalar OpenClaw via npm."
ok "OpenClaw instalado: $(openclaw --version 2>/dev/null | head -1)"

# Otimizações para VPS pequena (de vps.md)
if ! grep -q 'NODE_COMPILE_CACHE' "${HOME}/.bashrc" 2>/dev/null; then
    cat >> "${HOME}/.bashrc" << 'EOF'
export NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
mkdir -p /var/tmp/openclaw-compile-cache
export OPENCLAW_NO_RESPAWN=1
EOF
    export NODE_COMPILE_CACHE=/var/tmp/openclaw-compile-cache
    mkdir -p /var/tmp/openclaw-compile-cache
    export OPENCLAW_NO_RESPAWN=1
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3: Coletar credenciais
# ─────────────────────────────────────────────────────────────────────────────
step "3/13 — Credenciais"

ask "LICENSE_KEY"        "License Key (lk_...)"
ask "OMIE_APP_KEY"       "Omie App Key"
ask "OMIE_APP_SECRET"    "Omie App Secret"
ask "CFO_WHATSAPP_TO"    "WhatsApp destino dos alertas (ex: +5511999999999)"
ask "ANTHROPIC_API_KEY"  "Anthropic API Key (sk-ant-...)"
ask "LLM_BUDGET_BRL"     "Orçamento mensal LLM em BRL" "50"

# Validações básicas
[[ "$LICENSE_KEY" == lk_* ]] || fail "LICENSE_KEY deve começar com 'lk_'"
[[ "$CFO_WHATSAPP_TO" =~ ^\+55[0-9]{10,11}$ ]] || \
    warn "CFO_WHATSAPP_TO não parece um número BR (+55...). Continuando mesmo assim."
[[ "$ANTHROPIC_API_KEY" == sk-ant-* ]] || \
    warn "ANTHROPIC_API_KEY não parece uma chave Anthropic. Continuando mesmo assim."

ok "Credenciais coletadas."

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: Gerar HOOKS_TOKEN
# ─────────────────────────────────────────────────────────────────────────────
step "4/13 — Gerando hooks token"

if [[ -z "${HOOKS_TOKEN:-}" ]]; then
    HOOKS_TOKEN=$(openssl rand -hex 16 2>/dev/null || \
        python3 -c "import secrets; print(secrets.token_hex(16))")
    ok "HOOKS_TOKEN gerado."
else
    ok "HOOKS_TOKEN já definido via ambiente."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 5: Parear WhatsApp
# ─────────────────────────────────────────────────────────────────────────────
step "5/13 — Pareamento WhatsApp"

if wacli doctor 2>&1 | grep -qi "connected\|ok\|pareado"; then
    ok "WhatsApp já pareado — pulando."
else
    info "Iniciando pareamento WhatsApp..."
    echo ""
    echo "INSTRUÇÃO:"
    echo "  1. Abra o WhatsApp no seu celular"
    echo "  2. Toque nos 3 pontinhos → 'Dispositivos conectados'"
    echo "  3. 'Conectar um dispositivo'"
    echo "  4. Aponte para o QR code abaixo"
    echo ""
    echo "Pressione ENTER para exibir o QR code..."
    read -r

    if ! wacli auth; then
        fail "Falha no pareamento WhatsApp. Execute 'wacli auth' manualmente e tente novamente."
    fi

    sleep 2
    if wacli doctor 2>&1 | grep -qi "connected\|ok"; then
        ok "WhatsApp pareado com sucesso."
    else
        fail "WhatsApp pareado mas não conectado. Verifique 'wacli doctor' e tente novamente."
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 6: Subir Cloudflare Tunnel
# ─────────────────────────────────────────────────────────────────────────────
step "6/13 — Cloudflare Tunnel"

# Instalar cloudflared se necessário
if ! command -v cloudflared &>/dev/null; then
    info "Instalando cloudflared..."
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  CF_ARCH="amd64" ;;
        aarch64) CF_ARCH="arm64" ;;
        *)        fail "Arquitetura não suportada: $ARCH" ;;
    esac
    curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" \
        -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
    ok "cloudflared instalado: $(cloudflared --version)"
else
    ok "cloudflared já instalado: $(cloudflared --version)"
fi

# Configurar OpenClaw hooks listener como serviço systemd
HOOKS_SERVICE="/etc/systemd/system/openclaw-hooks.service"
if [[ ! -f "$HOOKS_SERVICE" ]]; then
    info "Configurando openclaw hooks listener na porta ${OPENCLAW_HOOKS_PORT}..."

    # O OpenClaw expõe /hooks/agent via config hooks.enabled + bind à porta
    # Configuramos o gateway para ouvir na porta 18789 com hooks habilitados
    # e o cloudflared tunnela direto para essa porta
    OPENCLAW_HOOKS_PORT=18789  # Porta padrão do gateway OpenClaw

    cat > "$HOOKS_SERVICE" << EOF
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
    systemctl enable openclaw-hooks 2>/dev/null || true
    ok "Serviço openclaw-hooks configurado."
else
    ok "Serviço openclaw-hooks já configurado."
fi

# Subir tunnel Cloudflare e capturar URL pública
if [[ -n "${INGRESS_URL:-}" ]]; then
    ok "INGRESS_URL já definido: $INGRESS_URL — pulando tunnel."
else
    info "Subindo Cloudflare Tunnel (trycloudflare.com)..."

    TUNNEL_LOG=$(mktemp /tmp/cloudflared-XXXXXX.log)
    # Tunnel para a porta do gateway OpenClaw
    cloudflared tunnel --url "http://localhost:18789" \
        --logfile "$TUNNEL_LOG" \
        --no-autoupdate &
    TUNNEL_PID=$!

    info "Aguardando URL pública do tunnel (até 30s)..."
    INGRESS_URL=""
    for i in $(seq 1 30); do
        sleep 1
        INGRESS_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || echo "")
        [[ -n "$INGRESS_URL" ]] && break
    done

    rm -f "$TUNNEL_LOG"

    if [[ -z "$INGRESS_URL" ]]; then
        kill "$TUNNEL_PID" 2>/dev/null || true
        fail "Não foi possível capturar a URL do Cloudflare Tunnel após 30s.
Verifique conectividade e tente novamente."
    fi

    # Persistir o PID para gerenciamento
    echo "$TUNNEL_PID" > "${STATE_DIR}/cloudflared.pid"
    ok "Cloudflare Tunnel ativo: $INGRESS_URL"

    # Configurar como serviço systemd para restart automático
    CF_SERVICE="/etc/systemd/system/cloudflared-cfo.service"
    if [[ ! -f "$CF_SERVICE" ]]; then
        cat > "$CF_SERVICE" << EOF
[Unit]
Description=Cloudflare Tunnel (Agente CFO)
After=network.target openclaw-hooks.service

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
# PASSO 7: Instalar skill omie
# ─────────────────────────────────────────────────────────────────────────────
step "7/13 — Instalando skill omie"

OMIE_DEST="${HOME}/.openclaw/workspace/skills/omie"
if [[ -d "$OMIE_DEST" ]]; then
    ok "Skill omie já instalada em $OMIE_DEST"
else
    info "Instalando skill omie via openclaw skills..."
    openclaw skills install omie 2>&1 || \
        fail "Falha ao instalar skill omie. Verifique: openclaw skills install omie"
    ok "Skill omie instalada."
fi

# Verificar dependência Python da skill omie
if [[ -f "$OMIE_DEST/requirements.txt" ]]; then
    pip3 install -r "$OMIE_DEST/requirements.txt" -q 2>/dev/null || \
        warn "Falha ao instalar dependências Python da skill omie. Tente: pip3 install requests"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 8: Instalar skill agente-cfo
# ─────────────────────────────────────────────────────────────────────────────
step "8/13 — Instalando skill agente-cfo"

if [[ -d "$SKILL_DEST" && -f "$SKILL_DEST/SKILL.md" ]]; then
    ok "Skill agente-cfo já instalada em $SKILL_DEST"
    info "Atualizando para última versão..."
    cd "$SKILL_DEST" && git pull --ff-only 2>/dev/null || \
        warn "Não foi possível atualizar via git pull (ignorado)."
else
    info "Clonando skill agente-cfo de $SKILL_REPO..."
    mkdir -p "$(dirname "$SKILL_DEST")"

    # Tenta clonar apenas o subdiretório skills/agente-cfo do repo
    git clone --depth 1 --filter=blob:none --sparse "$SKILL_REPO" /tmp/agente-cfo-clone 2>/dev/null || \
        fail "Falha ao clonar $SKILL_REPO.
Certifique-se que o repositório é público ou configure SKILL_REPO com URL autenticada."

    cd /tmp/agente-cfo-clone
    git sparse-checkout set skills/agente-cfo
    cp -r skills/agente-cfo "$SKILL_DEST"
    cd / && rm -rf /tmp/agente-cfo-clone

    ok "Skill agente-cfo instalada em $SKILL_DEST"
fi

chmod +x "$SKILL_DEST/scripts/"*.sh

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 9: Persistir env (~/.agente-cfo/.env)
# ─────────────────────────────────────────────────────────────────────────────
step "9/13 — Persistindo configuração"

mkdir -p "$(dirname "$ENV_FILE")"

cat > "$ENV_FILE" << EOF
# Agente CFO — Configuração
# Gerado por setup.sh em $(date '+%Y-%m-%d %H:%M:%S')
# NÃO comite este arquivo.

LICENSE_KEY=${LICENSE_KEY}
OMIE_APP_KEY=${OMIE_APP_KEY}
OMIE_APP_SECRET=${OMIE_APP_SECRET}
CFO_WHATSAPP_TO=${CFO_WHATSAPP_TO}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
LLM_BUDGET_BRL=${LLM_BUDGET_BRL}

PANEL_BASE_URL=${PANEL_BASE_URL}
INGRESS_URL=${INGRESS_URL:-}
HOOKS_TOKEN=${HOOKS_TOKEN}

OMIE_SKILL_PATH=${HOME}/.openclaw/workspace/skills/omie
EOF

chmod 600 "$ENV_FILE"
ok "Configuração salva em $ENV_FILE (chmod 600)."

# Configurar ANTHROPIC_API_KEY para o OpenClaw usar
# OpenClaw lê do ambiente ou do config.json
if ! grep -q "ANTHROPIC_API_KEY" "${HOME}/.bashrc" 2>/dev/null; then
    echo "export ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}" >> "${HOME}/.bashrc"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 10: Registrar no painel central
# ─────────────────────────────────────────────────────────────────────────────
step "10/13 — Registrando no painel central"

# Verificar se já está registrado
if [[ -f "$INSTANCE_ENV" ]] && grep -q "INSTANCE_ID=" "$INSTANCE_ENV" 2>/dev/null; then
    # shellcheck source=/dev/null
    source "$INSTANCE_ENV"
    if [[ -n "${INSTANCE_ID:-}" && "$INSTANCE_ID" != "" ]]; then
        ok "Instância já registrada: $INSTANCE_ID — atualizando registro..."
    fi
fi

AGENTE_CFO_VERSION=$(git -C "$SKILL_DEST" describe --tags --always 2>/dev/null || echo "1.0.0")
OPENCLAW_VERSION=$(openclaw --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")

REGISTER_BODY=$(printf '{"hostname":"%s","openclaw_version":"%s","agente_cfo_version":"%s","ingress_url":"%s","hooks_token":"%s"}' \
    "$(hostname)" \
    "$OPENCLAW_VERSION" \
    "$AGENTE_CFO_VERSION" \
    "${INGRESS_URL:-}" \
    "$HOOKS_TOKEN")

REGISTER_RESPONSE=$(curl -s --max-time 30 -X POST "${PANEL_BASE_URL}/clients-register" \
    -H "Content-Type: application/json" \
    -H "X-License: ${LICENSE_KEY}" \
    -d "$REGISTER_BODY")

HTTP_STATUS=$(echo "$REGISTER_RESPONSE" | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print('ok' if 'instance_id' in d else 'error')
except:
    print('error')
" 2>/dev/null || echo "error")

if [[ "$HTTP_STATUS" != "ok" ]]; then
    fail "Falha ao registrar no painel central.
Resposta: $REGISTER_RESPONSE
Verifique: LICENSE_KEY válida, PANEL_BASE_URL acessível, INGRESS_URL definida."
fi

INSTANCE_ID=$(echo "$REGISTER_RESPONSE" | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
print(d['instance_id'])
" 2>/dev/null)

TENANT_ID=$(echo "$REGISTER_RESPONSE" | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
# tenant_id não é retornado diretamente, mas podemos inferir do LICENSE_KEY header
# o painel inclui panel_config com budget — usamos placeholder
print('')
" 2>/dev/null || echo "")

# Capturar budget do painel
LLM_BUDGET_FROM_PANEL=$(echo "$REGISTER_RESPONSE" | python3 -c "
import sys, json
d = json.loads(sys.stdin.read())
print(d.get('panel_config', {}).get('llm_budget_brl', '$LLM_BUDGET_BRL'))
" 2>/dev/null || echo "$LLM_BUDGET_BRL")

# Persistir INSTANCE_ID
cat > "$INSTANCE_ENV" << EOF
# Gerado por setup.sh em $(date '+%Y-%m-%d %H:%M:%S')
INSTANCE_ID=${INSTANCE_ID}
TENANT_ID=${TENANT_ID:-}
EOF

# Atualizar .env com INSTANCE_ID e budget do painel
grep -v "^INSTANCE_ID=" "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
grep -v "^TENANT_ID=" "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
grep -v "^LLM_BUDGET_BRL=" "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
cat >> "$ENV_FILE" << EOF
INSTANCE_ID=${INSTANCE_ID}
TENANT_ID=${TENANT_ID:-}
LLM_BUDGET_BRL=${LLM_BUDGET_FROM_PANEL}
EOF

chmod 600 "$ENV_FILE"
ok "Instância registrada: $INSTANCE_ID"

# shellcheck source=/dev/null
source "$ENV_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 11: Registrar cron jobs
# ─────────────────────────────────────────────────────────────────────────────
step "11/13 — Registrando cron jobs"

SCRIPTS_DIR="$SKILL_DEST/scripts"
PROMPTS_DIR="$SKILL_DEST/prompts"

# Carregar IDs existentes se houver
[[ -f "$CRON_IDS_FILE" ]] && source "$CRON_IDS_FILE" 2>/dev/null || true

# Helper: adiciona cron apenas se ID não existir
_add_cron_if_missing() {
    local var_name="$1"  # ex: CRON_ID_MANHA
    local cron_cmd="$2"  # comando openclaw cron add ...

    if [[ -n "${!var_name:-}" ]]; then
        # Verificar se ainda existe
        if openclaw cron list --json 2>/dev/null | python3 -c "
import sys, json
jobs = json.load(sys.stdin)
ids = [j.get('id') or j.get('jobId','') for j in jobs]
print('exists' if '${!var_name}' in ids else 'missing')
" 2>/dev/null | grep -q "exists"; then
            ok "Cron $var_name já existe (${!var_name}) — pulando."
            return
        fi
    fi

    local new_id
    new_id=$(eval "$cron_cmd" 2>&1 | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print(d.get('id') or d.get('jobId',''))
except:
    # Tentar parsear da saída texto
    for line in sys.stdin:
        if 'id' in line.lower():
            import re
            m = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', line)
            if m: print(m.group()); break
" 2>/dev/null || echo "")

    if [[ -z "$new_id" ]]; then
        warn "Não foi possível capturar ID do cron $var_name. Verifique com: openclaw cron list"
        new_id="unknown-$(date +%s)"
    fi

    export "$var_name"="$new_id"

    # Persistir IDs no arquivo
    {
        grep -v "^${var_name}=" "$CRON_IDS_FILE" 2>/dev/null || true
        echo "${var_name}=${new_id}"
    } > "${CRON_IDS_FILE}.tmp" && mv "${CRON_IDS_FILE}.tmp" "$CRON_IDS_FILE"

    ok "Cron $var_name registrado: $new_id"
}

# 1. Alerta manhã (07:00)
_add_cron_if_missing "CRON_ID_MANHA" \
    "openclaw cron add \
        --name 'CFO Alerta Manhã' \
        --cron '0 7 * * *' --tz 'America/Sao_Paulo' \
        --session isolated \
        --message 'Execute: bash ${SCRIPTS_DIR}/cfo-reporter.sh ${PROMPTS_DIR}/alerta_manha.md' \
        --no-deliver \
        --json"

# 2. Alerta tarde (18:00)
_add_cron_if_missing "CRON_ID_TARDE" \
    "openclaw cron add \
        --name 'CFO Alerta Tarde' \
        --cron '0 18 * * *' --tz 'America/Sao_Paulo' \
        --session isolated \
        --message 'Execute: bash ${SCRIPTS_DIR}/cfo-reporter.sh ${PROMPTS_DIR}/alerta_tarde.md' \
        --no-deliver \
        --json"

# 3. Heartbeat (a cada 5 min)
_add_cron_if_missing "CRON_ID_HEARTBEAT" \
    "openclaw cron add \
        --name 'CFO Heartbeat' \
        --cron '*/5 * * * *' --tz 'America/Sao_Paulo' \
        --session isolated \
        --message 'Execute: bash ${SCRIPTS_DIR}/heartbeat.sh' \
        --no-deliver \
        --light-context \
        --json"

# 4. Check budget (diário 03:00)
_add_cron_if_missing "CRON_ID_BUDGET" \
    "openclaw cron add \
        --name 'CFO Budget Check' \
        --cron '0 3 * * *' --tz 'America/Sao_Paulo' \
        --session isolated \
        --message 'Execute: bash ${SCRIPTS_DIR}/check-budget.sh' \
        --no-deliver \
        --json"

# 5. WhatsApp watch (a cada 30 min)
_add_cron_if_missing "CRON_ID_WA_WATCH" \
    "openclaw cron add \
        --name 'CFO WhatsApp Watch' \
        --cron '*/30 * * * *' --tz 'America/Sao_Paulo' \
        --session isolated \
        --message 'Execute: bash ${SCRIPTS_DIR}/whatsapp-watch.sh' \
        --no-deliver \
        --light-context \
        --json"

ok "Todos os cron jobs registrados. IDs em: $CRON_IDS_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 12: Iniciar serviços
# ─────────────────────────────────────────────────────────────────────────────
step "12/13 — Iniciando serviços"

if systemctl is-active openclaw-hooks &>/dev/null; then
    info "Reiniciando openclaw-hooks para aplicar nova config..."
    systemctl restart openclaw-hooks
else
    systemctl start openclaw-hooks || warn "Não foi possível iniciar openclaw-hooks via systemctl."
fi

if systemctl is-active cloudflared-cfo &>/dev/null; then
    ok "cloudflared-cfo já ativo."
else
    systemctl start cloudflared-cfo 2>/dev/null || \
        warn "cloudflared-cfo não iniciado via systemctl (pode já estar rodando em background)."
fi

ok "Serviços iniciados."

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 13: Doctor final
# ─────────────────────────────────────────────────────────────────────────────
step "13/13 — Diagnóstico final"

info "Executando doctor.sh..."
# Exportar vars necessárias para o doctor
export LICENSE_KEY OMIE_APP_KEY OMIE_APP_SECRET INSTANCE_ID
export PANEL_BASE_URL="${PANEL_BASE_URL}"
export CFO_LOG_DIR="$LOG_DIR"
export CFO_STATE_DIR="$STATE_DIR"
export OMIE_SKILL_PATH="${HOME}/.openclaw/workspace/skills/omie"

DOCTOR_EXIT=0
bash "${SKILL_DEST}/scripts/doctor.sh" || DOCTOR_EXIT=$?

# ─────────────────────────────────────────────────────────────────────────────
# Resumo final
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Instalação Concluída!               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}Instance ID:${NC}  $INSTANCE_ID"
echo -e "  ${GREEN}Ingress URL:${NC}  ${INGRESS_URL:-não configurada}"
echo -e "  ${GREEN}Doctor:${NC}       $([ $DOCTOR_EXIT -eq 0 ] && echo '✅ tudo verde' || echo '⚠️  alguma falha — veja acima')"
echo ""
echo -e "  ${CYAN}Próximos passos:${NC}"
echo "  1. Aguarde o alerta de manhã às 07:00 (primeiro relatório via WhatsApp)"
echo "  2. Em caso de problema com WhatsApp: bash ${SKILL_DEST}/scripts/repare.sh"
echo "  3. Para diagnóstico: bash ${SKILL_DEST}/scripts/doctor.sh"
echo "  4. Logs em: $LOG_DIR"
echo ""

if [[ $DOCTOR_EXIT -ne 0 ]]; then
    warn "Doctor retornou falhas. Verifique os itens marcados com ❌ acima antes de usar."
    exit 1
fi

ok "Agente CFO instalado e operacional. Boas vendas! 💼"
