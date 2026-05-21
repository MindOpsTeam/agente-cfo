#!/usr/bin/env python3
"""
analise_horizontal.py — Variação % entre dois períodos (MoM, YoY).

Uso:
  python3 analise_horizontal.py                        # mês atual vs anterior
  python3 analise_horizontal.py --periodo1 2026-04 --periodo2 2026-05
  python3 analise_horizontal.py --format json
"""
import json
import subprocess
import sys
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
P1 = None
P2 = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--periodo1" and i + 1 < len(sys.argv): P1 = sys.argv[i+1]; i += 2
    elif a == "--periodo2" and i + 1 < len(sys.argv): P2 = sys.argv[i+1]; i += 2
    else: i += 1


def period_range(ym: str):
    y, m = map(int, ym.split("-"))
    _, ld = monthrange(y, m)
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{ld:02d}"


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


def delta(cur, prev):
    if prev == 0: return None
    return ((cur - prev) / abs(prev)) * 100


def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    today = date.today()
    if not P2:
        ym2 = f"{today.year}-{today.month:02d}"
    else:
        ym2 = P2
    if not P1:
        y2, m2 = map(int, ym2.split("-"))
        d2 = date(y2, m2, 1) - timedelta(days=1)
        ym1 = f"{d2.year}-{d2.month:02d}"
    else:
        ym1 = P1

    s1, e1 = period_range(ym1)
    s2, e2 = period_range(ym2)

    rec1 = sum_amounts(run_erp(["list_receivables", "--from", s1, "--to", e1, "--limit", "500"]))
    rec2 = sum_amounts(run_erp(["list_receivables", "--from", s2, "--to", e2, "--limit", "500"]))
    pay1 = sum_amounts(run_erp(["list_payables", "--from", s1, "--to", e1, "--limit", "500"]))
    pay2 = sum_amounts(run_erp(["list_payables", "--from", s2, "--to", e2, "--limit", "500"]))

    result = {
        "periodo1": ym1, "periodo2": ym2,
        "receitas": {"p1": rec1, "p2": rec2, "delta_pct": delta(rec2, rec1)},
        "pagamentos": {"p1": pay1, "p2": pay2, "delta_pct": delta(pay2, pay1)},
        "saldo_liquido": {"p1": rec1 - pay1, "p2": rec2 - pay2,
                          "delta_pct": delta(rec2 - pay2, rec1 - pay1)},
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
        return

    def row(label, p1v, p2v, d):
        arrow = ""
        if d is not None:
            arrow = f" {'▲' if d >= 0 else '▼'}{abs(d):.1f}%"
            if label == "Receitas" and d < -10:
                arrow += " ⚠"
            if label == "Pagamentos" and d > 15:
                arrow += " ⚠"
        return f"  {label:<18} {fmt(p1v):>15} → {fmt(p2v):>15}{arrow}"

    print(f"📊 Análise Horizontal: {ym1} vs {ym2}")
    print(f"  {'Métrica':<18} {'Período 1':>15}   {'Período 2':>15}  Δ%")
    print(f"  {'-'*65}")
    for lbl, key in [("Receitas", "receitas"), ("Pagamentos", "pagamentos"), ("Saldo líquido", "saldo_liquido")]:
        d = result[key]
        print(row(lbl, d["p1"], d["p2"], d["delta_pct"]))


if __name__ == "__main__":
    main()
