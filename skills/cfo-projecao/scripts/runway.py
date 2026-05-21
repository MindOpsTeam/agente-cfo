#!/usr/bin/env python3
"""
runway.py — Quantos meses de operação com o caixa atual, dado o burn médio.

Uso:
  python3 runway.py                     # calcula automaticamente
  python3 runway.py --caixa 50000 --burn 18000
  python3 runway.py --format json
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
CAIXA_MANUAL = None
BURN_MANUAL = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--caixa" and i + 1 < len(sys.argv): CAIXA_MANUAL = float(sys.argv[i+1]); i += 2
    elif a == "--burn" and i + 1 < len(sys.argv): BURN_MANUAL = float(sys.argv[i+1]); i += 2
    else: i += 1


def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def sum_amounts(r):
    lst = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(lst, list): return 0.0
    return sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
               for x in lst if isinstance(x, dict))


def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    today = date.today()

    if CAIXA_MANUAL is not None:
        caixa = CAIXA_MANUAL
    else:
        bal = run_erp(["get_balance"])
        caixa = float(bal.get("balance") or bal.get("saldo") or bal.get("saldo_total") or 0)

    if BURN_MANUAL is not None:
        burn = BURN_MANUAL
    else:
        mes = today.replace(day=1).isoformat()
        pay_r = run_erp(["list_payables", "--from", mes, "--to", today.isoformat(), "--limit", "500"])
        total_mes = sum_amounts(pay_r)
        days = max(today.day, 1)
        burn = (total_mes / days) * 30  # normaliza para 30 dias

    runway = caixa / burn if burn > 0 else 99.0

    result = {
        "date": today.isoformat(),
        "caixa": caixa,
        "burn_mensal": round(burn, 2),
        "runway_meses": round(runway, 1),
        "runway_dias": round(runway * 30, 0),
        "alerta": runway < 2,
        "atencao": 2 <= runway < 4,
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
        return

    signal = "🔴 CRÍTICO" if runway < 2 else ("🟡 ATENÇÃO" if runway < 4 else "🟢 OK")
    print(f"⏱ Runway — {today.strftime('%d/%m/%Y')}")
    print(f"  Caixa atual:    {fmt(caixa)}")
    print(f"  Burn mensal:    {fmt(burn)}")
    print(f"  Runway:         {runway:.1f} meses ({int(runway * 30)} dias) {signal}")
    if runway < 3:
        print(f"  ⚠ Com esse ritmo, o caixa esgota em {today.replace(month=today.month + int(runway)):%m/%Y} (aprox)")
    print()
    print(f"  Para ampliar runway: reduzir burn {fmt(burn * 0.15)}/mês → +{0.15 / (1 - 0.15):.0%} de fôlego")


if __name__ == "__main__":
    main()
