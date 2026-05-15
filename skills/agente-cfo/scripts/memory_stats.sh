#!/usr/bin/env bash
# memory_stats.sh — Estatísticas da memória do Marcos.
#
# Uso: bash memory_stats.sh [--json]
#
# Sem --json: saída formatada human-readable
# Com --json: saída JSON (para Marcos usar em prompts)

set -euo pipefail

JSON_MODE=false
[[ "${1:-}" == "--json" ]] && JSON_MODE=true

WORKSPACE="${HOME}/.openclaw/workspace"
MEM_DIR="${WORKSPACE}/memory"

JSON_ARG="false"
[[ "$JSON_MODE" == "true" ]] && JSON_ARG="true"

python3 - "$WORKSPACE" "$MEM_DIR" "$JSON_ARG" << 'PYEOF'
import sys, json, os, re, glob
from pathlib import Path
from datetime import datetime
from collections import defaultdict

workspace = Path(sys.argv[1])
mem_dir = Path(sys.argv[2])
json_mode = sys.argv[3].lower() in ("true", "1", "yes")

stats = {
    "entries": 0,
    "diary_files": 0,
    "total_lines": 0,
    "oldest_diary": None,
    "newest_diary": None,
    "root_files": [],
    "tags": defaultdict(int),
    "has_memory_md": False,
    "has_soul_md": False,
    "memory_md_lines": 0,
    "workspace_size_kb": 0,
}

# Diários de memória
diaries = sorted(mem_dir.glob("*.md")) if mem_dir.exists() else []
stats["diary_files"] = len(diaries)
if diaries:
    stats["oldest_diary"] = diaries[0].stem
    stats["newest_diary"] = diaries[-1].stem

for diary in diaries:
    try:
        content = diary.read_text()
        lines = content.splitlines()
        stats["total_lines"] += len(lines)
        # Conta entradas (linhas que começam com ##, ###, -, ou >)
        entries = sum(1 for l in lines if l.strip().startswith(('##', '- ', '> ')))
        stats["entries"] += entries
        # Extrai tags (palavras após # ou em bold **palavra**)
        for word in re.findall(r'\*\*([^*]+)\*\*|#([a-z][a-z0-9_-]+)', content.lower()):
            tag = (word[0] or word[1]).strip()[:20]
            if tag and len(tag) > 2:
                stats["tags"][tag] += 1
    except Exception:
        pass

# Arquivos raiz
for fname in ["MEMORY.md", "SOUL.md", "USER.md", "IDENTITY.md", "AGENTS.md"]:
    fpath = workspace / fname
    if fpath.exists():
        stats["root_files"].append(fname)
        n = sum(1 for _ in open(fpath, errors='replace'))
        stats["total_lines"] += n
        if fname == "MEMORY.md":
            stats["has_memory_md"] = True
            stats["memory_md_lines"] = n
        if fname == "SOUL.md":
            stats["has_soul_md"] = True
        stats["entries"] += max(1, n // 5)  # estimativa: 1 entry a cada 5 linhas

# Tamanho total do workspace de memória
try:
    total_bytes = sum(
        f.stat().st_size
        for f in mem_dir.rglob("*") if f.is_file()
    )
    for fname in ["MEMORY.md", "SOUL.md", "USER.md"]:
        fp = workspace / fname
        if fp.exists():
            total_bytes += fp.stat().st_size
    stats["workspace_size_kb"] = round(total_bytes / 1024, 1)
except Exception:
    pass

# Top 10 tags
top_tags = dict(sorted(stats["tags"].items(), key=lambda x: -x[1])[:10])
stats["tags"] = top_tags

if json_mode:
    result = {k: v for k, v in stats.items()}
    print(json.dumps(result, ensure_ascii=False, indent=2))
else:
    print(f"🧠 Memória do Marcos")
    print(f"  Entries estimadas:   {stats['entries']}")
    print(f"  Diários:             {stats['diary_files']} arquivos")
    print(f"  Total de linhas:     {stats['total_lines']}")
    print(f"  Período:             {stats.get('oldest_diary','?')} → {stats.get('newest_diary','?')}")
    print(f"  Tamanho:             {stats['workspace_size_kb']} KB")
    print(f"  MEMORY.md:           {'✓' if stats['has_memory_md'] else '✗'} ({stats['memory_md_lines']} linhas)")
    print(f"  SOUL.md:             {'✓' if stats['has_soul_md'] else '✗'}")
    print(f"  Arquivos raiz:       {', '.join(stats['root_files'])}")
    if top_tags:
        print(f"  Top temas:           {', '.join(f'{k}({v})' for k,v in list(top_tags.items())[:5])}")
PYEOF
