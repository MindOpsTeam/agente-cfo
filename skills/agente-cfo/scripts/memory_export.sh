#!/usr/bin/env bash
# memory_export.sh — Exporta memória e contexto do Marcos.
#
# Uso:
#   bash memory_export.sh [--output <path>] [--include-sessions] [--include-canvas]
#
#   --output <path>        : destino do tar.gz
#   --include-sessions     : inclui histórico de sessões (*.jsonl) — pode ser grande
#   --include-canvas       : inclui snapshots do canvas
#
# Conteúdo do export:
#   workspace/memory/*.md   (diários de memória)
#   workspace/MEMORY.md     (memória longa duração, se existir)
#   workspace/SOUL.md       (personalidade)
#   workspace/USER.md       (info do usuário)
#   workspace/IDENTITY.md   (identidade do agente)
#   workspace/AGENTS.md     (regras de workspace)
#   memory.sqlite           (índice vetorial, se houver)
#   metadata.json           (stats do export)
#   sessions/*.jsonl        (se --include-sessions)
#   canvas/                 (se --include-canvas)
#
# Output: ~/.agente-cfo/exports/memory-<timestamp>.tar.gz
# Retorna path do arquivo na última linha de stdout.

set -euo pipefail

OUTPUT=""
INCLUDE_SESSIONS=false
INCLUDE_CANVAS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)           OUTPUT="$2"; shift 2 ;;
        --include-sessions) INCLUDE_SESSIONS=true; shift ;;
        --include-canvas)   INCLUDE_CANVAS=true; shift ;;
        *) echo "Argumento desconhecido: $1" >&2; exit 1 ;;
    esac
done

EXPORTS_DIR="${HOME}/.agente-cfo/exports"
mkdir -p "$EXPORTS_DIR"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
[[ -z "$OUTPUT" ]] && OUTPUT="${EXPORTS_DIR}/memory-${TIMESTAMP}.tar.gz"

WORKDIR=$(mktemp -d /tmp/cfo-memory-export-XXXXXX)
trap 'rm -rf "$WORKDIR"' EXIT

WORKSPACE="${HOME}/.openclaw/workspace"
OPENCLAW="${HOME}/.openclaw"

LOG() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2; }

LOG "Exportando memória do Marcos..."

# ── 1. Arquivos de memória markdown ──────────────────────────────────────────
mkdir -p "$WORKDIR/workspace/memory"

# Diários de memória
if [[ -d "$WORKSPACE/memory" ]]; then
    cp -r "$WORKSPACE/memory/." "$WORKDIR/workspace/memory/" 2>/dev/null || true
    N_DIARY=$(ls "$WORKDIR/workspace/memory/"*.md 2>/dev/null | wc -l | tr -d ' ')
    LOG "  Diários de memória: $N_DIARY arquivos"
fi

# Arquivos raiz do workspace
for f in MEMORY.md SOUL.md USER.md IDENTITY.md AGENTS.md TOOLS.md HEARTBEAT.md; do
    src="$WORKSPACE/$f"
    [[ -f "$src" ]] && cp "$src" "$WORKDIR/workspace/$f" && LOG "  $f OK" || true
done

# ── 2. SQLite de memória (índice vetorial) ───────────────────────────────────
SQLITE_FILE="${OPENCLAW}/memory/main.sqlite"
if [[ -f "$SQLITE_FILE" ]]; then
    mkdir -p "$WORKDIR/memory"
    # Faz dump SQL (mais portável que copiar o sqlite direto)
    if command -v sqlite3 &>/dev/null; then
        sqlite3 "$SQLITE_FILE" .dump > "$WORKDIR/memory/main.sql" 2>/dev/null && \
            LOG "  memory/main.sqlite → main.sql dump OK" || \
            LOG "  memory/main.sqlite: dump falhou (arquivo vazio ou bloqueado)"
    else
        cp "$SQLITE_FILE" "$WORKDIR/memory/main.sqlite" 2>/dev/null && \
            LOG "  memory/main.sqlite (binário — sqlite3 não disponível)" || true
    fi
fi

# ── 3. Sessões (opcional) ─────────────────────────────────────────────────────
if [[ "$INCLUDE_SESSIONS" == "true" ]]; then
    SESSIONS_DIR="${OPENCLAW}/agents/main/sessions"
    if [[ -d "$SESSIONS_DIR" ]]; then
        mkdir -p "$WORKDIR/sessions"
        # Copia só os .jsonl (não os .reset.*)
        find "$SESSIONS_DIR" -name "*.jsonl" -not -name "*.reset.*" \
            -exec cp {} "$WORKDIR/sessions/" \; 2>/dev/null || true
        N_SESSIONS=$(ls "$WORKDIR/sessions/"*.jsonl 2>/dev/null | wc -l | tr -d ' ')
        LOG "  Sessões: $N_SESSIONS arquivos"
    fi
fi

# ── 4. Canvas (opcional) ──────────────────────────────────────────────────────
if [[ "$INCLUDE_CANVAS" == "true" ]]; then
    CANVAS_DIR="${OPENCLAW}/canvas"
    if [[ -d "$CANVAS_DIR" ]]; then
        mkdir -p "$WORKDIR/canvas"
        cp -r "$CANVAS_DIR/." "$WORKDIR/canvas/" 2>/dev/null || true
        LOG "  canvas: OK"
    fi
fi

# ── 5. Metadata com stats ─────────────────────────────────────────────────────
python3 -c "
import json, os, glob
from datetime import datetime, timezone
from pathlib import Path

workspace = Path.home() / '.openclaw' / 'workspace'
mem_dir = workspace / 'memory'

# Conta diários
diaries = sorted(glob.glob(str(mem_dir / '*.md')))
n_diaries = len(diaries)
oldest = diaries[0].split('/')[-1].replace('.md','') if diaries else None
newest = diaries[-1].split('/')[-1].replace('.md','') if diaries else None

# Conta linhas de memória
total_lines = 0
for f in diaries:
    try:
        total_lines += sum(1 for _ in open(f))
    except:
        pass

for root_file in ['MEMORY.md']:
    fp = workspace / root_file
    if fp.exists():
        try:
            total_lines += sum(1 for _ in open(fp))
        except:
            pass

meta = {
    'export_ts': datetime.now(timezone.utc).isoformat(),
    'diary_files': n_diaries,
    'oldest_diary': oldest,
    'newest_diary': newest,
    'total_memory_lines': total_lines,
    'include_sessions': $([[ '$INCLUDE_SESSIONS' == 'true' ]] && echo 'True' || echo 'False'),
    'include_canvas': $([[ '$INCLUDE_CANVAS' == 'true' ]] && echo 'True' || echo 'False'),
    'export_generator': 'memory_export.sh v1.0 (Sprint 46)',
}
print(json.dumps(meta, indent=2))
" > "$WORKDIR/metadata.json"
LOG "  metadata OK"

# ── 6. Empacota ───────────────────────────────────────────────────────────────
tar -czf "$OUTPUT" -C "$WORKDIR" . 2>/dev/null
SIZE=$(du -sh "$OUTPUT" | cut -f1)
LOG "✓ Memória exportada: $OUTPUT ($SIZE)"

echo "$OUTPUT"
