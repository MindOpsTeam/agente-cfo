#!/usr/bin/env python3
"""
margem.py — Calcula margens (bruta, operacional, líquida) a partir dos dados do ERP.

Uso:
  python3 margem.py                     # texto resumido
  python3 margem.py --format json
  python3 margem.py --receita 50000 --cmv 20000 --desp_op 15000 --desp_fin 2000 --impostos 3000

Quando sem args, usa list_receivables + list_payables do mês pra estimar.
"""
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
args = {k: None for k in ["receita", "cmv", "desp_op", "desp_fin", "impostos"]}
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a.startswith("--") and i + 1 < len(sys.argv):
        args[a[2:]] = float(sys.argv[i + 1]); i += 2
    else:
        i += 1


def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def sum_amounts(r: dict) -> float:
    lst = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(lst, list):
        lst = []
    return sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
               for x in lst if isinstance(x, dict))


def pct(num, den):
    return (num / den * 100) if den else 0


def fmt(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    today = date.today()
    mes = today.replace(day=1).isoformat()

    # Usa args manuais ou estima do ERP
    if args["receita"] is not None:
        receita = args["receita"]
        cmv = args.get("cmv") or 0
        desp_op = args.get("desp_op") or 0
        desp_fin = args.get("desp_fin") or 0
        impostos = args.get("impostos") or 0
    else:
        rec_r = run_erp(["list_receivables", "--from", mes, "--to", today.isoformat(), "--limit", "200"])
        pay_r = run_erp(["list_payables", "--from", mes, "--to", today.isoformat(), "--limit", "200"])
        receita = sum_amounts(rec_r)
        total_saidas = sum_amounts(pay_r)
        # Estimativas conservadoras sem DRE real
        cmv = total_saidas * 0.45       # ~45% custo mercadoria (estimativa)
        desp_op = total_saidas * 0.35   # ~35% despesas operacionais
        desp_fin = total_saidas * 0.08  # ~8% financeiras
        impostos = receita * 0.06       # ~6% SN médio

    lucro_bruto = receita - cmv
    lucro_operacional = lucro_bruto - desp_op
    lucro_antes_ir = lucro_operacional - desp_fin
    lucro_liquido = lucro_antes_ir - impostos

    m_bruta = pct(lucro_bruto, receita)
    m_operacional = pct(lucro_operacional, receita)
    m_liquida = pct(lucro_liquido, receita)

    result = {
        "date": today.isoformat(),
        "receita": receita, "cmv": cmv,
        "lucro_bruto": lucro_bruto, "margem_bruta_pct": round(m_bruta, 1),
        "desp_op": desp_op, "lucro_operacional": lucro_operacional,
        "margem_operacional_pct": round(m_operacional, 1),
        "desp_fin": desp_fin, "impostos": impostos,
        "lucro_liquido": lucro_liquido, "margem_liquida_pct": round(m_liquida, 1),
        "estimado": args["receita"] is None,
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
        return

    nota = " (estimativa baseada em proporções típicas BR)" if result["estimado"] else ""
    signal_b = "🔴" if m_bruta < 20 else ("🟡" if m_bruta < 35 else "🟢")
    signal_o = "🔴" if m_operacional < 5 else ("🟡" if m_operacional < 12 else "🟢")
    signal_l = "🔴" if m_liquida < 3 else ("🟡" if m_liquida < 8 else "🟢")

    print(f"📉 Margens — {today.strftime('%m/%Y')}{nota}")
    print(f"")
    print(f"Receita:          {fmt(receita)}")
    print(f"(-) CMV/Custos:   {fmt(cmv)}")
    print(f"Lucro Bruto:      {fmt(lucro_bruto)} → {m_bruta:.1f}% {signal_b}")
    print(f"(-) Desp. Op.:    {fmt(desp_op)}")
    print(f"Lucro Operac.:    {fmt(lucro_operacional)} → {m_operacional:.1f}% {signal_o}")
    print(f"(-) Fin+Impostos: {fmt(desp_fin + impostos)}")
    print(f"Lucro Líquido:    {fmt(lucro_liquido)} → {m_liquida:.1f}% {signal_l}")
    print(f"")
    ref = "Ref PME BR: bruta>30% 🟢, operacional>10% 🟢, líquida>5% 🟢"
    print(ref)


if __name__ == "__main__":
    main()
