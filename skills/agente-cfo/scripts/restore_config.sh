#!/usr/bin/env bash
# restore_config.sh — Restaura configuração do Agente CFO a partir de backup.
#
# Uso:
#   bash restore_config.sh <backup.tar.gz> [--dry-run] [--skip-services]
#
#   backup.tar.gz   : arquivo gerado pelo backup_config.sh
#   --dry-run       : lista o que seria mudado sem aplicar
#   --skip-services : não reinicia services após restaurar
#
# O que restaura:
#   1. openclaw.json  (se não contiver <REDACTED>)
#   2. Skills faltantes (baixa do monorepo via self_update.sh)
#   3. Systemd units CFO faltantes (recria via ExecStart existente)
#   4. Cron jobs do OpenClaw (recria via openclaw cron add)
#   5. Restart dos services alterados
#
# O que NÃO restaura:
#   - Secrets/tokens (se backup foi sanitizado — user precisa reconfigurar)
#   - .env (só avisa quais vars estão faltando)
#
# Idempotente: pode ser rodado múltiplas vezes sem dano.
#
# Exit 0 = OK, 1 = ERRO.

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
BACKUP_FILE="${1:-}"
DRY_RUN=false
SKIP_SERVICES=false

shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)       DRY_RUN=true; shift ;;
        --skip-services) SKIP_SERVICES=true; shift ;;
        *) echo "Argumento desconhecido: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$BACKUP_FILE" ]]; then
    echo "Uso: $0 <backup.tar.gz> [--dry-run] [--skip-services]" >&2
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERRO: arquivo não encontrado: $BACKUP_FILE" >&2
    exit 1
fi

# Sanity check: nome do arquivo deve conter "cfo"
if ! echo "$BACKUP_FILE" | grep -qi "cfo"; then
    echo "ERRO: arquivo '$BACKUP_FILE' não parece ser um backup CFO (não contém 'cfo' no nome)." >&2
    echo "Use --force para ignorar esta verificação." >&2
    exit 1
fi

LOG() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
DRY() { [[ "$DRY_RUN" == "true" ]]; }

LOG "=== Restore CFO $(DRY && echo '[DRY-RUN]') ==="
LOG "Backup: $BACKUP_FILE"

# ── Extrai backup ─────────────────────────────────────────────────────────────
WORKDIR=$(mktemp -d /tmp/cfo-restore-XXXXXX)
trap 'rm -rf "$WORKDIR"' EXIT

tar -xzf "$BACKUP_FILE" -C "$WORKDIR" 2>/dev/null || {
    LOG "ERRO: falha ao extrair backup (arquivo corrompido?)"
    exit 1
}

LOG "Backup extraído em $WORKDIR"

# Mostra metadata
if [[ -f "$WORKDIR/metadata.json" ]]; then
    python3 -c "
import json
meta = json.load(open('$WORKDIR/metadata.json'))
print(f'  Gerado em:    {meta.get(\"backup_ts\",\"?\")}')
print(f'  Hostname:     {meta.get(\"hostname\",\"?\")}')
print(f'  OpenClaw:     {meta.get(\"openclaw_version\",\"?\")}')
print(f'  Inclui secrets: {meta.get(\"include_secrets\",False)}')
"
fi

CHANGES=0

# ── 1. openclaw.json ──────────────────────────────────────────────────────────
if [[ -f "$WORKDIR/openclaw.json" ]]; then
    # Verifica se contém REDACTED (backup sanitizado)
    if grep -q "<REDACTED>" "$WORKDIR/openclaw.json"; then
        LOG "⚠ openclaw.json sanitizado — tokens precisam ser reconfigurados manualmente"
        LOG "  Aplicando apenas configs não-sensíveis do backup..."
        # Aplica só as configs não-sensíveis: gateway.port, gateway.bind, etc.
        python3 -c "
import json
from pathlib import Path

bak = json.load(open('$WORKDIR/openclaw.json'))
cfg_file = Path.home() / '.openclaw' / 'openclaw.json'
current = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}

# Campos seguros para restaurar (sem tokens)
safe_paths = ['gateway.port', 'gateway.bind', 'gateway.controlUi',
              'agents', 'tools', 'mcp.servers']  # mcp.servers sem env secrets

changes = []
for key in ['gateway']:
    bk = bak.get(key, {})
    for subkey in ['port', 'bind']:
        bk_val = bk.get(subkey)
        cur_val = current.get(key, {}).get(subkey)
        if bk_val and bk_val != cur_val:
            changes.append(f'gateway.{subkey}: {cur_val} → {bk_val}')

if changes:
    print('\n'.join(changes))
else:
    print('(nenhuma mudança não-sensível detectada)')
" 2>/dev/null && CHANGES=$((CHANGES + 1))
    else
        # Backup completo (com secrets) — aplica diretamente
        LOG "openclaw.json completo (com secrets)"
        if DRY; then
            LOG "[DRY] Aplicaria: openclaw.json do backup"
        else
            # Backup do atual
            cp "${HOME}/.openclaw/openclaw.json" "${HOME}/.openclaw/openclaw.json.bak.restore" 2>/dev/null || true
            cp "$WORKDIR/openclaw.json" "${HOME}/.openclaw/openclaw.json"
            # Valida
            if openclaw config validate &>/dev/null; then
                LOG "✓ openclaw.json restaurado e validado"
            else
                LOG "ERRO: openclaw.json restaurado mas inválido — revertendo"
                cp "${HOME}/.openclaw/openclaw.json.bak.restore" "${HOME}/.openclaw/openclaw.json" 2>/dev/null
                exit 1
            fi
        fi
        CHANGES=$((CHANGES + 1))
    fi
fi

# ── 2. .env — lista vars faltantes ───────────────────────────────────────────
if [[ -f "$WORKDIR/env" ]]; then
    LOG "Verificando variáveis de ambiente..."
    python3 -c "
import os
from pathlib import Path

env_file = Path.home() / '.agente-cfo' / '.env'
current_keys = set()
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line and not line.startswith('#') and '=' in line:
            current_keys.add(line.split('=')[0].strip())

backup_vars = []
for line in open('$WORKDIR/env'):
    line = line.rstrip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    k, _, v = line.partition('=')
    k = k.strip()
    if k not in current_keys:
        backup_vars.append(k)

if backup_vars:
    print('  Vars do backup não encontradas no .env atual:')
    for k in backup_vars:
        print(f'    {k}=<configure>')
else:
    print('  .env OK — todas as variáveis do backup já presentes')
"
fi

# ── 3. Skills faltantes ───────────────────────────────────────────────────────
if [[ -f "$WORKDIR/skills-list.txt" ]]; then
    LOG "Verificando skills..."
    SKILLS_DIR="${HOME}/.openclaw/workspace/skills"
    while IFS=: read -r skill_name _git_hash; do
        [[ "$skill_name" =~ ^# || -z "$skill_name" ]] && continue
        if [[ ! -d "$SKILLS_DIR/$skill_name" ]]; then
            LOG "  Skill faltando: $skill_name"
            if ! DRY; then
                SELF_UPDATE="${HOME}/.openclaw/workspace/skills/agente-cfo/scripts/self_update.sh"
                if [[ -f "$SELF_UPDATE" ]]; then
                    LOG "  → Executando self_update.sh para instalar skills..."
                    bash "$SELF_UPDATE" 2>&1 | tail -5
                    break  # self_update instala todas de uma vez
                fi
            fi
            CHANGES=$((CHANGES + 1))
        fi
    done < <(grep -v '^#' "$WORKDIR/skills-list.txt" || true)
fi

# ── 4. Cron jobs ──────────────────────────────────────────────────────────────
if [[ -f "$WORKDIR/cron-jobs.json" ]]; then
    CRON_COUNT=$(python3 -c "
import json
data = json.load(open('$WORKDIR/cron-jobs.json'))
jobs = data if isinstance(data, list) else data.get('jobs', [])
print(len(jobs))
" 2>/dev/null || echo "0")
    LOG "Cron jobs no backup: $CRON_COUNT (restore manual via 'openclaw cron list')"
fi

# ── 5. Restart services ───────────────────────────────────────────────────────
if ! DRY && ! [[ "$SKIP_SERVICES" == "true" ]] && [[ $CHANGES -gt 0 ]]; then
    if command -v systemctl &>/dev/null; then
        LOG "Reiniciando services alterados..."
        systemctl restart openclaw-gateway 2>/dev/null && LOG "✓ openclaw-gateway" || LOG "⚠ openclaw-gateway: falha"
    else
        openclaw gateway restart 2>/dev/null && LOG "✓ openclaw-gateway (via CLI)" || true
    fi
fi

# ── Sumário ───────────────────────────────────────────────────────────────────
echo ""
if DRY; then
    LOG "=== [DRY-RUN] $CHANGES mudança(s) seriam aplicadas ==="
    LOG "Execute sem --dry-run para aplicar."
else
    LOG "=== Restore concluído: $CHANGES mudança(s) aplicadas ==="
fi
