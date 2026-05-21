#!/usr/bin/env python3
"""burn.py — Burn rate mensal médio dos últimos N meses."""
import json
import subprocess
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"
MESES = 3
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--meses" and i+1 < len(sys.argv): MESES = int(sys.argv[i+1]); i += 2
    else: i += 1

def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}

def sum_amounts(r):
    lst = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(lst, list): return 0.0
    return sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0) for x in lst if isinstance(x, dict))

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".","," ).replace("X",".")

def main():
    today = date.today()
    burns = []
    for offset in range(1, MESES + 1):
        m = today.month - offset
        y = today.year
        while m <= 0: m += 12; y -= 1
        _, ld = monthrange(y, m)
        s = f"{y}-{m:02d}-01"
        e = f"{y}-{m:02d}-{ld:02d}"
        total = sum_amounts(run_erp(["list_payables", "--from", s, "--to", e, "--limit", "500"]))
        burns.append({"mes": f"{y}-{m:02d}", "total": total})

    burn_medio = sum(b["total"] for b in burns) / max(len(burns), 1)
    result = {"meses_analisados": MESES, "burn_medio_mensal": round(burn_medio, 2), "historico": burns}
    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🔥 Burn Rate — médio {MESES} meses: {fmt(burn_medio)}/mês")
    for b in burns:
        print(f"  {b['mes']}: {fmt(b['total'])}")

if __name__ == "__main__":
    main()
