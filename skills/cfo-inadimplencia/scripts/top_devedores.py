#!/usr/bin/env python3
"""top_devedores.py — Top N devedores por valor total vencido."""
import json
import subprocess
import sys
from datetime import date
from collections import defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"
N = 10
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--n" and i+1 < len(sys.argv): N = int(sys.argv[i+1]); i += 2
    else: i += 1

def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def main():
    today = date.today()
    r = run_erp(["list_overdue"])
    items = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(items, list): items = []

    by_customer = defaultdict(lambda: {"total": 0, "count": 0, "max_dias": 0})
    total_geral = 0
    for item in items:
        if not isinstance(item, dict): continue
        nome = item.get("customer") or item.get("cliente") or item.get("supplier") or item.get("nome") or "Sem nome"
        val = float(item.get("amount_brl") or item.get("amount") or item.get("valor") or 0)
        due = item.get("due_date") or item.get("vencimento") or ""
        try: dias = (today - date.fromisoformat(str(due)[:10])).days
        except: dias = 0
        by_customer[nome]["total"] += val
        by_customer[nome]["count"] += 1
        by_customer[nome]["max_dias"] = max(by_customer[nome]["max_dias"], dias)
        total_geral += val

    top = sorted(by_customer.items(), key=lambda x: x[1]["total"], reverse=True)[:N]
    result = {
        "date": today.isoformat(),
        "total_overdue": total_geral,
        "top": [{"nome": n, "total": d["total"], "faturas": d["count"],
                 "max_dias": d["max_dias"],
                 "pct_total": round(d["total"]/total_geral*100, 1) if total_geral else 0}
                for n, d in top]
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🏆 Top {N} Devedores — {today.strftime('%d/%m/%Y')}")
    print(f"   Total vencido: {fmt(total_geral)}")
    print()
    for i, (nome, d) in enumerate(top, 1):
        pct = (d["total"] / total_geral * 100) if total_geral else 0
        risk = "🔴" if d["max_dias"] > 60 else ("🟡" if d["max_dias"] > 30 else "🟠")
        print(f"  {i:2}. {nome[:30]:<30} {fmt(d['total']):>14} ({pct:.0f}%) {d['max_dias']}d {risk}")

if __name__ == "__main__":
    main()
