#!/usr/bin/env bash
# memory_import.sh — Importa memória do Marcos de um export.
#
# Uso:
#   bash memory_import.sh <export.tar.gz> [--merge|--replace] [--dry-run]
#
#   --merge   (default): adiciona entries novas, NÃO sobrescreve existentes
#   --replace           : substitui toda a memória local pela importada (⚠️ DESTRUCTIVO)
#   --dry-run           : lista mudanças sem aplicar
#
# Idempotente: pode rodar múltiplas vezes com --merge sem dano.
#
# Exit 0 = OK, 1 = ERRO.

set -euo pipefail

EXPORT_FILE="${1:-}"
MODE="merge"
DRY_RUN=false

shift 2>/dev/null || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --merge)   MODE="merge"; shift ;;
        --replace) MODE="replace"; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Argumento desconhecido: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$EXPORT_FILE" ]]; then
    echo "Uso: $0 <export.tar.gz> [--merge|--replace] [--dry-run]" >&2
    exit 1
fi

if [[ ! -f "$EXPORT_FILE" ]]; then
    echo "ERRO: arquivo não encontrado: $EXPORT_FILE" >&2
    exit 1
fi

if ! echo "$EXPORT_FILE" | grep -qi "memory"; then
    echo "AVISO: arquivo não parece ser um export de memória CFO (não contém 'memory' no nome)." >&2
    echo "Continuando mesmo assim..." >&2
fi

LOG() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
DRY() { [[ "$DRY_RUN" == "true" ]]; }

LOG "=== Memory Import ($MODE) $(DRY && echo '[DRY-RUN]') ==="
LOG "Export: $EXPORT_FILE"

# ── Extrai export ─────────────────────────────────────────────────────────────
WORKDIR=$(mktemp -d /tmp/cfo-memory-import-XXXXXX)
trap 'rm -rf "$WORKDIR"' EXIT

tar -xzf "$EXPORT_FILE" -C "$WORKDIR" 2>/dev/null || {
    LOG "ERRO: falha ao extrair export"
    exit 1
}

WORKSPACE="${HOME}/.openclaw/workspace"

# Mostra metadata
if [[ -f "$WORKDIR/metadata.json" ]]; then
    python3 -c "
import json
meta = json.load(open('$WORKDIR/metadata.json'))
print(f'  Exportado em:   {meta.get(\"export_ts\",\"?\")}')
print(f'  Diários:        {meta.get(\"diary_files\",0)} arquivos')
print(f'  Memória linhas: {meta.get(\"total_memory_lines\",0)}')
print(f'  Período:        {meta.get(\"oldest_diary\",\"?\")} → {meta.get(\"newest_diary\",\"?\")}')
"
fi

CHANGES=0

# ── 1. Diários de memória ─────────────────────────────────────────────────────
IMPORT_MEM="$WORKDIR/workspace/memory"
LOCAL_MEM="$WORKSPACE/memory"

if [[ -d "$IMPORT_MEM" ]]; then
    mkdir -p "$LOCAL_MEM"
    for src_file in "$IMPORT_MEM"/*.md; do
        [[ -f "$src_file" ]] || continue
        fname=$(basename "$src_file")
        dest_file="$LOCAL_MEM/$fname"

        if [[ "$MODE" == "merge" ]]; then
            if [[ -f "$dest_file" ]]; then
                # Verifica se conteúdo é diferente
                if ! diff -q "$src_file" "$dest_file" &>/dev/null; then
                    LOG "  MERGE $fname (conteúdo diferente — mantendo local, appendando entradas novas)"
                    if ! DRY; then
                        # Appenda linhas do import que não estão no local
                        python3 -c "
local_lines = set(open('$dest_file').readlines())
new_lines = [l for l in open('$src_file').readlines() if l not in local_lines]
if new_lines:
    with open('$dest_file', 'a') as f:
        f.write('\n# --- importado de $EXPORT_FILE ---\n')
        f.writelines(new_lines)
    print(f'  Appendou {len(new_lines)} linhas novas')
else:
    print('  (nenhuma linha nova)')
"
                    fi
                    CHANGES=$((CHANGES + 1))
                fi
            else
                LOG "  NOVO $fname"
                if ! DRY; then
                    cp "$src_file" "$dest_file"
                fi
                CHANGES=$((CHANGES + 1))
            fi
        else
            # Replace: sobrescreve tudo
            if ! DRY; then
                cp "$src_file" "$dest_file"
            fi
            LOG "  REPLACE $fname"
            CHANGES=$((CHANGES + 1))
        fi
    done
fi

# ── 2. Arquivos raiz do workspace ────────────────────────────────────────────
for fname in MEMORY.md SOUL.md USER.md IDENTITY.md AGENTS.md TOOLS.md; do
    src_file="$WORKDIR/workspace/$fname"
    dest_file="$WORKSPACE/$fname"

    [[ -f "$src_file" ]] || continue

    if [[ "$MODE" == "merge" ]]; then
        if [[ -f "$dest_file" ]]; then
            if ! diff -q "$src_file" "$dest_file" &>/dev/null; then
                LOG "  MERGE $fname (mantendo local — arquivo raiz não é sobrescrito em --merge)"
                # Em merge, arquivos raiz NÃO são sobrescritos (são únicos por instância)
            fi
        else
            LOG "  NOVO $fname"
            if ! DRY; then
                cp "$src_file" "$dest_file"
            fi
            CHANGES=$((CHANGES + 1))
        fi
    else
        # Replace: backup do atual + sobrescreve
        if [[ -f "$dest_file" ]] && ! DRY; then
            cp "$dest_file" "${dest_file}.bak.import" 2>/dev/null || true
        fi
        if ! DRY; then
            cp "$src_file" "$dest_file"
        fi
        LOG "  REPLACE $fname"
        CHANGES=$((CHANGES + 1))
    fi
done

# ── 3. SQLite — aviso sobre índice vetorial ──────────────────────────────────
if [[ -f "$WORKDIR/memory/main.sql" || -f "$WORKDIR/memory/main.sqlite" ]]; then
    LOG "  ℹ SQLite encontrado no export — reindexação automática necessária"
    if [[ "$MODE" == "replace" ]] && ! DRY; then
        LOG "  Reconstruindo índice de memória via openclaw memory reindex..."
        openclaw memory reindex 2>/dev/null && LOG "  ✓ reindex OK" || \
            LOG "  ⚠ reindex falhou — memória será reindexada no próximo uso"
    fi
fi

# ── 4. Sessões (se existirem no export) ──────────────────────────────────────
if [[ -d "$WORKDIR/sessions" ]]; then
    N_SESSIONS=$(ls "$WORKDIR/sessions/"*.jsonl 2>/dev/null | wc -l | tr -d ' ')
    LOG "  $N_SESSIONS sessão(ões) no export"
    if [[ "$MODE" == "replace" ]]; then
        LOCAL_SESSIONS="${HOME}/.openclaw/agents/main/sessions"
        for sfile in "$WORKDIR/sessions/"*.jsonl; do
            [[ -f "$sfile" ]] || continue
            fname=$(basename "$sfile")
            if [[ ! -f "$LOCAL_SESSIONS/$fname" ]]; then
                if ! DRY; then
                    cp "$sfile" "$LOCAL_SESSIONS/$fname" 2>/dev/null || true
                fi
                LOG "  IMPORT sessão $fname"
                CHANGES=$((CHANGES + 1))
            fi
        done
    fi
fi

# ── Sumário ───────────────────────────────────────────────────────────────────
echo ""
if DRY; then
    LOG "=== [DRY-RUN] $CHANGES mudança(s) seriam aplicadas ==="
else
    LOG "=== Import concluído ($MODE): $CHANGES mudança(s) aplicadas ==="
fi
