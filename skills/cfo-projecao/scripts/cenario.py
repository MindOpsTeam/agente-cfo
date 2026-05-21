#!/usr/bin/env python3
"""
cenario.py — Projeção multi-cenário de fluxo de caixa.

Uso:
  python3 cenario.py --periodo 30        # projeção 30 dias (default)
  python3 cenario.py --periodo 90        # 90 dias
  python3 cenario.py --cenario realista  # só um cenário
  python3 cenario.py --format json
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
PERIODO = 30
CENARIO = "all"
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--periodo" and i + 1 < len(sys.argv): PERIODO = int(sys.argv[i+1]); i += 2
    elif a == "--cenario" and i + 1 < len(sys.argv): CENARIO = sys.argv[i+1]; i += 2
    else: i += 1

CENARIOS = {
    "otimista":   {"rec_fator": 0.90, "inadimplencia": 0.05, "custo_fator": 1.00},
    "realista":   {"rec_fator": 0.75, "inadimplencia": 0.12, "custo_fator": 1.03},
    "pessimista": {"rec_fator": 0.55, "inadimplencia": 0.25, "custo_fator": 1.08},
}


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
    end = today + timedelta(days=PERIODO)

    bal = run_erp(["get_balance"])
    caixa = float(bal.get("balance") or bal.get("saldo") or bal.get("saldo_total") or 0)

    rec_r = run_erp(["list_receivables", "--from", today.isoformat(), "--to", end.isoformat(), "--limit", "500"])
    pay_r = run_erp(["list_payables", "--from", today.isoformat(), "--to", end.isoformat(), "--limit", "500"])

    receitas_previstas = sum_amounts(rec_r)
    pagamentos_previstos = sum_amounts(pay_r)

    cenarios_calc = {}
    for nome, params in CENARIOS.items():
        if CENARIO != "all" and CENARIO != nome:
            continue
        rec_efetivo = receitas_previstas * params["rec_fator"] * (1 - params["inadimplencia"])
        pag_efetivo = pagamentos_previstos * params["custo_fator"]
        saldo_proj = caixa + rec_efetivo - pag_efetivo
        cenarios_calc[nome] = {
            "caixa_inicial": caixa,
            "receitas_previstas": receitas_previstas,
            "receitas_efetivas": round(rec_efetivo, 2),
            "pagamentos": round(pag_efetivo, 2),
            "saldo_projetado": round(saldo_proj, 2),
            "variacao": round(saldo_proj - caixa, 2),
            "params": params,
        }

    result = {
        "data_base": today.isoformat(),
        "periodo_dias": PERIODO,
        "cenarios": cenarios_calc,
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
        return

    print(f"🔮 Projeção {PERIODO} dias — base {today.strftime('%d/%m/%Y')}")
    print(f"  Caixa atual:        {fmt(caixa)}")
    print(f"  Receber previstos:  {fmt(receitas_previstas)}")
    print(f"  Pagar previstos:    {fmt(pagamentos_previstos)}")
    print()
    for nome, c in cenarios_calc.items():
        signal = "🔴" if c["saldo_projetado"] < 0 else ("🟡" if c["saldo_projetado"] < caixa * 0.5 else "🟢")
        print(f"  [{nome.upper():12}] Saldo: {fmt(c['saldo_projetado'])} {signal}  (Δ {fmt(c['variacao'])})")
    print()
    print(f"  Cenário realista é o mais provável para PME BR.")


if __name__ == "__main__":
    main()
