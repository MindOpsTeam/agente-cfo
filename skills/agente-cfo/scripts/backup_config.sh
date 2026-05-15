#!/usr/bin/env bash
# backup_config.sh — Exporta configuração completa do Agente CFO.
#
# Uso:
#   bash backup_config.sh [--output <path>] [--include-secrets]
#
#   --output <path>     : destino do tar.gz (default: ~/.agente-cfo/backups/cfo-backup-<ts>.tar.gz)
#   --include-secrets   : inclui tokens/keys em plaintext (⚠️ CUIDADO — trate o arquivo com segurança)
#
# Conteúdo do backup:
#   openclaw.json        (sanitizado por padrão: tokens → <REDACTED>)
#   .env                 (sanitizado por padrão: valores → <REDACTED>)
#   skills-list.txt      (nomes das skills instaladas)
#   systemd-units.txt    (units cfo-* e openclaw-*)
#   cron-jobs.json       (cron jobs via openclaw cron list)
#   mcp-servers.json     (MCP servers registrados)
#   metadata.json        (hostname, OS, versão, timestamp)
#
# Retorna path do arquivo criado em stdout na última linha.
# Exit 0 = OK, 1 = ERRO.

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
OUTPUT=""
INCLUDE_SECRETS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)      OUTPUT="$2"; shift 2 ;;
        --include-secrets) INCLUDE_SECRETS=true; shift ;;
        *) echo "Argumento desconhecido: $1" >&2; exit 1 ;;
    esac
done

# ── Defaults ──────────────────────────────────────────────────────────────────
BACKUP_DIR="${HOME}/.agente-cfo/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

if [[ -z "$OUTPUT" ]]; then
    OUTPUT="${BACKUP_DIR}/cfo-backup-${TIMESTAMP}.tar.gz"
fi

WORKDIR=$(mktemp -d /tmp/cfo-backup-XXXXXX)
trap 'rm -rf "$WORKDIR"' EXIT

LOG() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2; }

if [[ "$INCLUDE_SECRETS" == "true" ]]; then
    echo "" >&2
    echo "⚠️  AVISO: backup inclui tokens e secrets em plaintext." >&2
    echo "   Trate o arquivo como segredo — não compartilhe sem encriptar." >&2
    echo "" >&2
fi

LOG "Criando backup em $OUTPUT..."

# ── 1. openclaw.json ──────────────────────────────────────────────────────────
CONFIG="${HOME}/.openclaw/openclaw.json"
if [[ -f "$CONFIG" ]]; then
    if [[ "$INCLUDE_SECRETS" == "true" ]]; then
        cp "$CONFIG" "$WORKDIR/openclaw.json"
    else
        # Sanitiza: substitui tokens/passwords por <REDACTED>
        python3 -c "
import json, sys, re

def sanitize(obj, path=''):
    sensitive_keys = {'token','password','secret','key','apikey','api_key',
                      'access_token','refresh_token','service_role_key',
                      'client_secret','webhook_secret'}
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            key_lower = k.lower().replace('-','_')
            is_sensitive = any(s in key_lower for s in sensitive_keys)
            if is_sensitive and isinstance(v, str) and v and not v.startswith('<'):
                result[k] = '<REDACTED>'
            else:
                result[k] = sanitize(v, f'{path}.{k}')
        return result
    if isinstance(obj, list):
        return [sanitize(i, path) for i in obj]
    return obj

data = json.load(open('$CONFIG'))
sanitized = sanitize(data)
print(json.dumps(sanitized, indent=2, ensure_ascii=False))
" > "$WORKDIR/openclaw.json"
    fi
    LOG "openclaw.json OK"
fi

# ── 2. .env ───────────────────────────────────────────────────────────────────
ENV_FILE="${HOME}/.agente-cfo/.env"
if [[ -f "$ENV_FILE" ]]; then
    if [[ "$INCLUDE_SECRETS" == "true" ]]; then
        cp "$ENV_FILE" "$WORKDIR/env"
    else
        # Sanitiza: mantém chaves, redacta valores
        python3 -c "
import sys
result = []
for line in open('$ENV_FILE'):
    line = line.rstrip()
    if not line or line.startswith('#') or '=' not in line:
        result.append(line)
        continue
    k, _, v = line.partition('=')
    k = k.strip()
    # Mantém valores que são claramente não-secretos (URLs base, booleans)
    non_secret = {'PANEL_BASE_URL','SUPABASE_URL','USD_BRL_RATE','INSTANCE_ID',
                  'MCP_WARMER_INTERVAL_MIN','CREDENTIALS_SYNC_INTERVAL_MIN',
                  'EVOLUTION_SYNC_INTERVAL_S','TELEGRAM_SYNC_INTERVAL_S',
                  'HEALTH_DOCTOR_INTERVAL_S','ALERTS_CHECKER_INTERVAL_S',
                  'METRICS_PUBLISHER_INTERVAL_S'}
    if k in non_secret:
        result.append(f'{k}={v}')
    else:
        result.append(f'{k}=<REDACTED>')
print('\n'.join(result))
" > "$WORKDIR/env"
    fi
    LOG ".env OK ($(wc -l < "$ENV_FILE") linhas)"
fi

# ── 3. Skills instaladas ──────────────────────────────────────────────────────
SKILLS_DIR="${HOME}/.openclaw/workspace/skills"
{
    echo "# Skills instaladas — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    if [[ -d "$SKILLS_DIR" ]]; then
        for skill_dir in "$SKILLS_DIR"/*/; do
            skill_name=$(basename "$skill_dir")
            [[ "$skill_name" == "_lib" || "$skill_name" == "_template" ]] && continue
            # Tenta obter versão via git log
            git_hash=$(git -C "$skill_dir" log --oneline -1 2>/dev/null | cut -d' ' -f1 || echo "unknown")
            echo "${skill_name}:${git_hash}"
        done
    fi
} > "$WORKDIR/skills-list.txt"
LOG "skills-list OK"

# ── 4. Systemd units ──────────────────────────────────────────────────────────
{
    echo "# Systemd units — $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    if command -v systemctl &>/dev/null; then
        systemctl list-units --type=service --state=loaded \
            --no-legend --no-pager 2>/dev/null | \
            grep -E '(cfo-|openclaw-|cloudflared-cfo)' | \
            awk '{print $1, $3, $4}' || true
    else
        echo "# systemctl não disponível (macOS dev)"
        ls /etc/systemd/system/cfo-*.service 2>/dev/null | xargs -I{} basename {} || true
    fi
} > "$WORKDIR/systemd-units.txt"
LOG "systemd-units OK"

# ── 5. Cron jobs ──────────────────────────────────────────────────────────────
{
    openclaw cron list --json 2>/dev/null || echo '[]'
} > "$WORKDIR/cron-jobs.json"
LOG "cron-jobs OK"

# ── 6. MCP servers ────────────────────────────────────────────────────────────
{
    python3 -c "
import json
from pathlib import Path
cfg_file = Path.home() / '.openclaw' / 'openclaw.json'
if cfg_file.exists():
    data = json.loads(cfg_file.read_text())
    servers = data.get('mcp', {}).get('servers', {})
    # Redacta env em MCP servers (contêm service_role_keys)
    sanitized = {}
    for name, entry in servers.items():
        s = {k: v for k, v in entry.items() if k != 'env'}
        if 'env' in entry:
            s['env'] = {k: '<REDACTED>' for k in entry['env']}
        sanitized[name] = s
    print(json.dumps(sanitized, indent=2))
else:
    print('{}')
"
} > "$WORKDIR/mcp-servers.json"
LOG "mcp-servers OK"

# ── 7. Metadata ───────────────────────────────────────────────────────────────
{
    python3 -c "
import json, os, subprocess, platform
from datetime import datetime, timezone

def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except:
        return 'unknown'

meta = {
    'backup_ts': datetime.now(timezone.utc).isoformat(),
    'hostname': os.uname().nodename,
    'os': platform.platform(),
    'python': platform.python_version(),
    'openclaw_version': run(['openclaw', '--version']).split('\n')[0],
    'include_secrets': $([[ "$INCLUDE_SECRETS" == "true" ]] && echo 'True' || echo 'False'),
    'backup_generator': 'backup_config.sh v1.0 (Sprint 45)',
}
print(json.dumps(meta, indent=2))
"
} > "$WORKDIR/metadata.json"
LOG "metadata OK"

# ── 8. Empacota tudo ──────────────────────────────────────────────────────────
tar -czf "$OUTPUT" -C "$WORKDIR" . 2>/dev/null
SIZE=$(du -sh "$OUTPUT" | cut -f1)
LOG "✓ Backup criado: $OUTPUT ($SIZE)"

# Mantém apenas 7 backups automáticos (os mais recentes)
if [[ "$OUTPUT" =~ "$BACKUP_DIR" ]]; then
    ls -t "$BACKUP_DIR"/cfo-backup-*.tar.gz 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
fi

# Imprime path na última linha (para scripts que capturam stdout)
echo "$OUTPUT"
