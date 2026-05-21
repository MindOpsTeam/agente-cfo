#!/usr/bin/env python3
"""anomalia_categoria.py — Detecta categorias com variação MoM acima do threshold."""
import json
import subprocess
import sys
from calendar import monthrange
from collections import defaultdict
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"
THRESHOLD = 20.0  # %
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--threshold" and i+1 < len(sys.argv): THRESHOLD = float(sys.argv[i+1]); i += 2
    else: i += 1

def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}

def by_cat(r):
    d = defaultdict(float)
    lst = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(lst, list): return d
    for x in lst:
        if not isinstance(x, dict): continue
        cat = (x.get("category") or x.get("categoria") or "Sem categoria").strip()
        d[cat] += float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
    return d

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def main():
    today = date.today()
    # Mês atual
    s2 = today.replace(day=1).isoformat(); e2 = today.isoformat()
    # Mês anterior
    d1 = today.replace(day=1).__class__(today.year, today.month, 1)
    from datetime import timedelta
    d1 -= timedelta(days=1)
    _, ld = monthrange(d1.year, d1.month)
    s1 = f"{d1.year}-{d1.month:02d}-01"; e1 = f"{d1.year}-{d1.month:02d}-{ld}"

    cat1 = by_cat(run_erp(["list_payables","--from",s1,"--to",e1,"--limit","500"]))
    cat2 = by_cat(run_erp(["list_payables","--from",s2,"--to",e2,"--limit","500"]))

    anomalias = []
    all_cats = set(cat1) | set(cat2)
    for cat in all_cats:
        v1 = cat1.get(cat, 0); v2 = cat2.get(cat, 0)
        if v1 == 0: continue
        delta = ((v2 - v1) / v1) * 100
        if abs(delta) >= THRESHOLD:
            anomalias.append({"categoria": cat, "v1": v1, "v2": v2, "delta_pct": round(delta, 1)})

    anomalias.sort(key=lambda x: abs(x["delta_pct"]), reverse=True)
    if FORMAT == "json":
        print(json.dumps({"date": today.isoformat(), "anomalias": anomalias}, ensure_ascii=False)); return

    print(f"🔍 Variação por Categoria ({d1.strftime('%m/%Y')} → {today.strftime('%m/%Y')})")
    if not anomalias:
        print(f"  ✅ Nenhuma categoria variou mais de {THRESHOLD:.0f}%"); return
    for a in anomalias:
        arrow = "▲" if a["delta_pct"] > 0 else "▼"
        signal = "🔴" if abs(a["delta_pct"]) > 50 else "🟡"
        print(f"  {signal} {a['categoria']:<25} {fmt(a['v1'])} → {fmt(a['v2'])}  {arrow}{abs(a['delta_pct']):.0f}%")

if __name__ == "__main__":
    main()
