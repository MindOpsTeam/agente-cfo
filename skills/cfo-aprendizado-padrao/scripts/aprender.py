#!/usr/bin/env python3
"""
aprender.py — Registra par (supplier, category) no histórico de padrões.

Uso:
  python3 aprender.py --supplier "Uber" --category "Transporte"
  python3 aprender.py --supplier "Posto BR" --category "Combustível" --amount 150
  python3 aprender.py --format json   # exibe padrões aprendidos

Persiste em ~/.agente-cfo/memory/padroes-categorias.json
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

MEMORY_FILE = Path.home() / ".agente-cfo" / "memory" / "padroes-categorias.json"
FORMAT = "text"
SUPPLIER = None
CATEGORY = None
AMOUNT = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a in ("--format",) and i + 1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--supplier" and i + 1 < len(sys.argv): SUPPLIER = sys.argv[i+1]; i += 2
    elif a == "--category" and i + 1 < len(sys.argv): CATEGORY = sys.argv[i+1]; i += 2
    elif a == "--amount" and i + 1 < len(sys.argv): AMOUNT = float(sys.argv[i+1]); i += 2
    else: i += 1


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def load() -> dict:
    if MEMORY_FILE.exists():
        try: return json.loads(MEMORY_FILE.read_text())
        except: pass
    return {}


def save(data: dict):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    patterns = load()

    # Se modo exibição
    if SUPPLIER is None and CATEGORY is None:
        if FORMAT == "json":
            print(json.dumps(patterns, ensure_ascii=False))
        else:
            print("🧠 Padrões aprendidos:")
            for sup, cats in sorted(patterns.items()):
                top = sorted(cats.items(), key=lambda x: x[1].get("count", 0), reverse=True)
                if top:
                    cat, meta = top[0]
                    print(f"  • {sup:<30} → {cat} ({meta.get('count',0)}x)")
        return

    if not SUPPLIER or not CATEGORY:
        print(json.dumps({"error": "Informe --supplier e --category"}) if FORMAT == "json"
              else "Uso: python3 aprender.py --supplier X --category Y")
        return

    sup_key = normalize(SUPPLIER)
    if sup_key not in patterns:
        patterns[sup_key] = {}

    cat_data = patterns[sup_key].get(CATEGORY, {"count": 0, "amounts": [], "last_seen": ""})
    cat_data["count"] = cat_data.get("count", 0) + 1
    if AMOUNT:
        amounts = cat_data.get("amounts", [])
        amounts.append(AMOUNT)
        cat_data["amounts"] = amounts[-20:]  # mantém últimos 20
    cat_data["last_seen"] = date.today().isoformat()
    patterns[sup_key][CATEGORY] = cat_data

    save(patterns)

    result = {"supplier": SUPPLIER, "category": CATEGORY,
              "count": cat_data["count"], "learned": True}
    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"🧠 Aprendido: '{SUPPLIER}' → '{CATEGORY}' ({cat_data['count']}x)")


if __name__ == "__main__":
    main()
