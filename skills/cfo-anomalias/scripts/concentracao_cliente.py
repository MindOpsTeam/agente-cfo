#!/usr/bin/env python3
"""concentracao_cliente.py — Top clientes em % do faturamento."""
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"; N = 5
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
    mes = today.replace(day=1).isoformat()
    r = run_erp(["list_receivables", "--from", mes, "--to", today.isoformat(), "--limit", "500"])
    items = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(items, list): items = []

    by_cli = defaultdict(float)
    total = 0.0
    for x in items:
        if not isinstance(x, dict): continue
        cli = x.get("customer") or x.get("cliente") or x.get("nome") or "Sem nome"
        val = float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
        by_cli[cli] += val; total += val

    top = sorted(by_cli.items(), key=lambda x: x[1], reverse=True)[:N]
    top_pct = sum(v for _, v in top) / total * 100 if total else 0
    result = {"date": today.isoformat(), "total_faturamento": total,
              "top_pct_concentracao": round(top_pct, 1),
              "clientes": [{"nome": n, "valor": v, "pct": round(v/total*100,1) if total else 0} for n,v in top]}

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    signal = "🔴" if top_pct > 60 else ("🟡" if top_pct > 40 else "🟢")
    print(f"🏆 Concentração de Clientes — {today.strftime('%m/%Y')}")
    print(f"  Top {N} = {top_pct:.0f}% do faturamento {signal}")
    if top_pct > 40:
        print(f"  ⚠ Concentração alta — risco se perder cliente principal")
    print()
    for i, (nome, val) in enumerate(top, 1):
        pct = val/total*100 if total else 0
        print(f"  {i}. {nome[:30]:<30} {fmt(val):>14} ({pct:.1f}%)")

if __name__ == "__main__":
    main()
