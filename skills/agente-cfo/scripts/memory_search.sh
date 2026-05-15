#!/usr/bin/env bash
# memory_search.sh — Busca memórias aprendidas por keyword ou tag.
#
# Uso:
#   bash memory_search.sh <keyword> [--tag <tag>] [--limit <n>] [--json]
#
#   keyword    : termo de busca (case-insensitive, busca em content e evidence)
#   --tag      : filtra por tag (preferência|terminologia|workflow|fato)
#   --limit    : máximo de resultados (default 5)
#   --json     : saída JSON (default: human-readable)
#
# Exemplos:
#   bash memory_search.sh "asaas"
#   bash memory_search.sh "relatório" --tag preferência --limit 3
#   bash memory_search.sh "" --tag fato --json   # todos os fatos

set -euo pipefail

KEYWORD=""
TAG_FILTER=""
LIMIT=5
JSON_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)    TAG_FILTER="$2"; shift 2 ;;
        --limit)  LIMIT="$2"; shift 2 ;;
        --json)   JSON_MODE=true; shift ;;
        -*)       echo "Argumento desconhecido: $1" >&2; exit 1 ;;
        *)        KEYWORD="$1"; shift ;;
    esac
done

MEM_DIR="${HOME}/.openclaw/memory/learned"
INDEX_FILE="${MEM_DIR}/_index.json"

python3 - "$MEM_DIR" "$INDEX_FILE" "$KEYWORD" "$TAG_FILTER" "$LIMIT" "$JSON_MODE" << 'PYEOF'
import sys, json, os
from pathlib import Path

mem_dir = Path(sys.argv[1])
index_file = Path(sys.argv[2])
keyword = sys.argv[3].lower()
tag_filter = sys.argv[4]
limit = int(sys.argv[5])
json_mode = sys.argv[6].lower() == "true"

if not index_file.exists():
    if json_mode:
        print("[]")
    else:
        print("Nenhuma memória encontrada ainda.")
        print("As memórias são criadas automaticamente após cada conversa com Marcos.")
    sys.exit(0)

try:
    index = json.loads(index_file.read_text())
except Exception:
    index = {"entries": []}

results = []
for entry_id in index.get("entries", []):
    if len(results) >= limit:
        break
    entry_file = mem_dir / f"{entry_id}.json"
    if not entry_file.exists():
        continue
    try:
        entry = json.loads(entry_file.read_text())
    except Exception:
        continue

    # Filtro por tag
    if tag_filter and entry.get("tag") != tag_filter:
        continue

    # Filtro por keyword
    if keyword:
        searchable = (
            entry.get("content", "") + " " +
            entry.get("evidence", "") + " " +
            entry.get("tag", "")
        ).lower()
        if keyword not in searchable:
            continue

    results.append(entry)

if json_mode:
    print(json.dumps(results, ensure_ascii=False, indent=2))
else:
    if not results:
        kw_str = f"'{keyword}'" if keyword else "todos"
        tag_str = f" (tag: {tag_filter})" if tag_filter else ""
        print(f"Nenhuma memória encontrada para {kw_str}{tag_str}.")
        sys.exit(0)

    print(f"🧠 {len(results)} memória(s) encontrada(s):\n")
    for i, m in enumerate(results, 1):
        tag_icon = {"preferência": "❤️", "terminologia": "💬", "workflow": "⚙️", "fato": "📌"}.get(m.get("tag", ""), "•")
        print(f"{i}. {tag_icon} [{m.get('tag','')}] {m.get('content','')}")
        if m.get("evidence"):
            print(f"   Evidência: \"{m['evidence']}\"")
        ts = m.get("created_at", "")[:10]
        uses = m.get("usage_count", 0)
        print(f"   Criado: {ts} | Usos: {uses}")
        print()
PYEOF
