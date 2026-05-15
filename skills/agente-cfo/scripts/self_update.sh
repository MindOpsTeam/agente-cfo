#!/usr/bin/env bash
# self_update.sh — Auto-update do Agente CFO via git clone (Sprint 26)
#
# Executa sem input — Marcos pode chamar isso via painel.
# Atualiza todas as skills do monorepo, cria units systemd faltantes e
# reinicia os daemons.
#
# Uso:
#   bash ~/.openclaw/workspace/skills/agente-cfo/scripts/self_update.sh
#
# Via painel (edge function vps-trigger-update → push-command → Marcos):
#   Marcos executa: bash /root/.openclaw/workspace/skills/agente-cfo/scripts/self_update.sh

set -euo pipefail

REPO_URL="https://github.com/MindOpsTeam/agente-cfo.git"
CLONE_DIR="/tmp/agente-cfo-clone-$$"
WORKSPACE_SKILLS="${HOME}/.openclaw/workspace/skills"
ENV_FILE="${HOME}/.agente-cfo/.env"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
ok()  { echo "✓ $*"; }
warn(){ echo "⚠ $*" >&2; }

log "=== Agente CFO Self-Update (Sprint 26) ==="
log "Repo: ${REPO_URL}"

# ── 1. Clone shallow ──────────────────────────────────────────────────────────
log "Clonando repositório..."
rm -rf "${CLONE_DIR}"
git clone --depth 1 --quiet "${REPO_URL}" "${CLONE_DIR}"
ok "Clone concluído em ${CLONE_DIR}"

# ── 2. Atualiza _lib ──────────────────────────────────────────────────────────
log "Atualizando _lib..."
mkdir -p "${WORKSPACE_SKILLS}/_lib"
cp -rf "${CLONE_DIR}/skills/_lib/." "${WORKSPACE_SKILLS}/_lib/"
ok "_lib atualizado"

# ── 3. Atualiza cada skill ────────────────────────────────────────────────────
log "Atualizando skills..."
updated_skills=()
for skill_dir in "${CLONE_DIR}/skills"/*/; do
    skill_name=$(basename "${skill_dir}")
    [[ "${skill_name}" == "_lib"      ]] && continue
    [[ "${skill_name}" == "_template" ]] && continue

    dest="${WORKSPACE_SKILLS}/${skill_name}"
    mkdir -p "${dest}"
    cp -rf "${skill_dir}." "${dest}/"

    # chmod em scripts shell
    chmod +x "${dest}/scripts/"*.sh "${dest}/"*.sh 2>/dev/null || true

    updated_skills+=("${skill_name}")
done
ok "Skills atualizadas: ${updated_skills[*]:-nenhuma}"

# ── 4. Systemd units faltantes ────────────────────────────────────────────────
log "Verificando systemd units..."

declare -A UNIT_SCRIPTS=(
    ["cfo-supabase-sync"]="${WORKSPACE_SKILLS}/supabase/scripts/supabase_sync.py"
    ["cfo-credentials-sync"]="${WORKSPACE_SKILLS}/agente-cfo/scripts/credentials_sync.py"
    ["cfo-evolution-sync"]="${WORKSPACE_SKILLS}/evolution-api/scripts/evolution_sync.py"
    ["cfo-telegram-sync"]="${WORKSPACE_SKILLS}/telegram/scripts/telegram_sync.py"
    ["cfo-mcp-warmer"]="${WORKSPACE_SKILLS}/agente-cfo/scripts/mcp_warmer.py"
)

for unit_name in "${!UNIT_SCRIPTS[@]}"; do
    unit_file="/etc/systemd/system/${unit_name}.service"
    script_path="${UNIT_SCRIPTS[$unit_name]}"

    if [[ -f "${unit_file}" ]]; then
        log "${unit_name}.service já existe — pulando criação"
        continue
    fi

    log "Criando ${unit_name}.service..."
    cat > "${unit_file}" <<UNIT
[Unit]
Description=Agente CFO - ${unit_name}
After=network.target openclaw-gateway.service
Wants=openclaw-gateway.service

[Service]
Type=simple
User=${USER:-root}
WorkingDirectory=${HOME}
Environment=HOME=${HOME}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${script_path}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

    systemctl daemon-reload 2>/dev/null || true
    systemctl enable --now "${unit_name}" 2>/dev/null || warn "${unit_name} enable falhou"
    ok "${unit_name}.service criado e ativado"
done

# ── 5. Restart daemons ────────────────────────────────────────────────────────
log "Reiniciando daemons..."
DAEMONS=(cfo-proactive cfo-automation-engine cfo-credentials-sync cfo-supabase-sync cfo-evolution-sync cfo-telegram-sync cfo-mcp-warmer)
for daemon in "${DAEMONS[@]}"; do
    systemctl restart "${daemon}" 2>/dev/null && log "  restart ${daemon}" || warn "  ${daemon} não pôde ser reiniciado"
done

# ── 6. Cleanup ────────────────────────────────────────────────────────────────
rm -rf "${CLONE_DIR}"

# ── 7. Sumário ────────────────────────────────────────────────────────────────
echo ""
ok "Self-update completo! Skills atualizadas: ${#updated_skills[@]}"
echo ""
echo "Status dos daemons:"
for daemon in cfo-proactive cfo-automation-engine cfo-credentials-sync cfo-supabase-sync; do
    status=$(systemctl is-active "${daemon}" 2>/dev/null || echo "inativo")
    echo "  ${daemon}: ${status}"
done
echo ""
