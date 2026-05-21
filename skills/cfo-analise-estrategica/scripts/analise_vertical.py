#!/usr/bin/env python3
"""
analise_vertical.py — Representação % de cada categoria sobre a receita total.

Uso:
  python3 analise_vertical.py             # mês atual
  python3 analise_vertical.py --top 10    # top N categorias
  python3 analise_vertical.py --format json
"""
import json
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
TOP = 15
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--top" and i + 1 < len(sys.argv): TOP = int(sys.argv[i+1]); i += 2
    else: i += 1


def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def extract_items(r):
    lst = r.get("records") or r.get("items") or r.get("data") or []
    return lst if isinstance(lst, list) else []


def main():
    today = date.today()
    mes = today.replace(day=1).isoformat()
    fim = today.isoformat()

    rec_r = run_erp(["list_receivables", "--from", mes, "--to", fim, "--limit", "500"])
    pay_r = run_erp(["list_payables", "--from", mes, "--to", fim, "--limit", "500"])

    receitas = extract_items(rec_r)
    pagamentos = extract_items(pay_r)

    total_receita = sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
                       for x in receitas if isinstance(x, dict))

    # Agrupa saídas por categoria
    by_cat = defaultdict(float)
    for x in pagamentos:
        if not isinstance(x, dict): continue
        cat = (x.get("category") or x.get("categoria") or x.get("tipo") or "Sem categoria").strip()
        val = float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
        by_cat[cat] += val

    total_saidas = sum(by_cat.values())

    sorted_cats = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:TOP]

    result = {
        "periodo": f"{today.year}-{today.month:02d}",
        "receita_total": total_receita,
        "saidas_total": total_saidas,
        "categorias": [
            {"categoria": cat, "valor": val,
             "pct_receita": round(val / total_receita * 100, 1) if total_receita else 0,
             "pct_saidas": round(val / total_saidas * 100, 1) if total_saidas else 0}
            for cat, val in sorted_cats
        ],
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
        return

    def fmt(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    print(f"📊 Análise Vertical — {today.strftime('%m/%Y')}")
    print(f"  Receita total: {fmt(total_receita)}")
    print(f"  Saídas total:  {fmt(total_saidas)}")
    print()
    print(f"  {'Categoria':<28} {'Valor':>12} {'% Receita':>10} {'% Saídas':>10}")
    print(f"  {'-'*64}")
    for cat in result["categorias"]:
        signal = "🔴" if cat["pct_receita"] > 30 else ("🟡" if cat["pct_receita"] > 20 else "")
        print(f"  {cat['categoria']:<28} {fmt(cat['valor']):>12} {cat['pct_receita']:>8.1f}% {cat['pct_saidas']:>8.1f}% {signal}")


if __name__ == "__main__":
    main()
