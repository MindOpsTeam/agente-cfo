#!/usr/bin/env python3
"""
ponto_equilibrio.py — Receita mínima para cobrir custos fixos (break-even).

Uso:
  python3 ponto_equilibrio.py                            # calcula do ERP
  python3 ponto_equilibrio.py --custo_fixo 30000 --margem_bruta_pct 40
  python3 ponto_equilibrio.py --format json
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"
CUSTO_FIXO = None
MARGEM_PCT = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--custo_fixo" and i+1 < len(sys.argv): CUSTO_FIXO = float(sys.argv[i+1]); i += 2
    elif a == "--margem_bruta_pct" and i+1 < len(sys.argv): MARGEM_PCT = float(sys.argv[i+1]); i += 2
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

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def main():
    today = date.today()
    mes = today.replace(day=1).isoformat()
    fim = today.isoformat()

    if CUSTO_FIXO is None or MARGEM_PCT is None:
        rec_r = run_erp(["list_receivables", "--from", mes, "--to", fim, "--limit","500"])
        pay_r = run_erp(["list_payables", "--from", mes, "--to", fim, "--limit","500"])
        receita = sum_amounts(rec_r)
        saidas = sum_amounts(pay_r)
        custo_fixo = saidas * 0.55   # ~55% dos custos são fixos (estimativa)
        margem = 0.35 if MARGEM_PCT is None else MARGEM_PCT / 100
    else:
        custo_fixo = CUSTO_FIXO
        margem = MARGEM_PCT / 100
        receita = sum_amounts(run_erp(["list_receivables", "--from", mes, "--to", fim, "--limit","500"]))

    pe = custo_fixo / margem if margem > 0 else 0
    diff = receita - pe
    status = "✅ acima do ponto de equilíbrio" if diff >= 0 else "🔴 abaixo do break-even"

    result = {
        "custo_fixo_mes": round(custo_fixo, 2),
        "margem_bruta_pct": round(margem * 100, 1),
        "ponto_equilibrio": round(pe, 2),
        "receita_atual_mes": round(receita, 2),
        "distancia_be": round(diff, 2),
        "estimado": CUSTO_FIXO is None,
    }
    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"⚖️  Ponto de Equilíbrio — {today.strftime('%m/%Y')}")
    print(f"  Custo fixo mês:      {fmt(custo_fixo)}")
    print(f"  Margem bruta:        {margem*100:.1f}%")
    print(f"  Break-even receita:  {fmt(pe)}")
    print(f"  Receita atual:       {fmt(receita)}")
    print(f"  Distância:           {fmt(diff)} → {status}")

if __name__ == "__main__":
    main()
