#!/usr/bin/env bash
# auto_rollback.sh — Reverte openclaw.json para o último backup válido.
#
# Uso: bash auto_rollback.sh [--dry-run]
#
# Procura backups ~/.openclaw/openclaw.json.bak* por ordem de modificação
# (mais recente primeiro), valida cada um com `openclaw config validate`,
# e aplica o primeiro válido copiando sobre o openclaw.json atual.
#
# Retorna:
#   0 = rollback aplicado com sucesso
#   1 = nenhum backup válido encontrado
#   2 = openclaw.json atual já é válido (nada a fazer)

set -euo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

OPENCLAW_DIR="${HOME}/.openclaw"
CONFIG="$OPENCLAW_DIR/openclaw.json"
LOG_FILE="${HOME}/.agente-cfo/logs/health-doctor.log"

_log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [auto_rollback] $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "$*"; }

# 1. Verifica se config atual é válida
if openclaw config validate &>/dev/null; then
    _log "openclaw.json atual é VÁLIDO — rollback não necessário"
    exit 2
fi

_log "openclaw.json inválido — buscando backup válido..."

# 2. Lista backups por data de modificação (mais recente primeiro)
# shellcheck disable=SC2207
BACKUPS=($(ls -t "$OPENCLAW_DIR"/openclaw.json.bak* 2>/dev/null || true))

if [[ ${#BACKUPS[@]} -eq 0 ]]; then
    _log "ERRO: nenhum backup encontrado em $OPENCLAW_DIR"
    exit 1
fi

# 3. Testa cada backup e aplica o primeiro válido
for bak in "${BACKUPS[@]}"; do
    # Valida: tenta parsear JSON e rodar config validate com o backup como config
    if python3 -c "import json; json.load(open('$bak'))" &>/dev/null; then
        # Testa se openClaw aceita o backup como config válida (estrutura OK)
        if OPENCLAW_CONFIG_PATH="$bak" openclaw config validate &>/dev/null 2>&1; then
            _log "Backup válido encontrado: $bak"
            if [[ "$DRY_RUN" == "true" ]]; then
                _log "[DRY-RUN] Aplicaria: cp $bak $CONFIG"
                exit 0
            fi
            # Salva o inválido atual como .broken
            cp "$CONFIG" "${CONFIG}.broken" 2>/dev/null || true
            cp "$bak" "$CONFIG"
            _log "✓ Rollback aplicado: $bak → $CONFIG (anterior salvo em ${CONFIG}.broken)"
            exit 0
        else
            _log "Backup $bak: JSON OK mas config inválida — pulando"
        fi
    else
        _log "Backup $bak: JSON inválido — pulando"
    fi
done

_log "ERRO: nenhum backup válido encontrado (${#BACKUPS[@]} backups testados)"
exit 1
