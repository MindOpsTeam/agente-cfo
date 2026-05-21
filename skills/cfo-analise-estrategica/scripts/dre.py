#!/usr/bin/env python3
"""
dre.py — DRE simplificado (Demonstração do Resultado do Exercício).

Uso:
  python3 dre.py                         # mês atual
  python3 dre.py --mes 2026-04           # mês específico
  python3 dre.py --format json

Estrutura:
  (+) Receita bruta
  (-) Deduções / impostos sobre receita (estimativa)
  (=) Receita líquida
  (-) CMV / Custo dos serviços (estimativa)
  (=) Lucro bruto
  (-) Despesas operacionais
  (=) EBITDA aproximado
  (-) Depreciação (opcional / zero se não informado)
  (=) EBIT
  (-) Despesas financeiras
  (=) EBT (lucro antes do IR)
  (-) IR/CSLL (estimativa por regime)
  (=) Lucro Líquido
"""
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
MES = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--mes" and i + 1 < len(sys.argv):
        MES = sys.argv[i + 1]; i += 2
    else:
        i += 1


def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def sum_amounts(r):
    lst = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(lst, list):
        return 0.0
    return sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
               for x in lst if isinstance(x, dict))


def fmt(v, indent=0):
    prefix = "  " * indent
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sign = "+" if v >= 0 else "-"
    return f"{prefix}R$ {s}"


def main():
    today = date.today()
    if MES:
        year, month = map(int, MES.split("-"))
        from calendar import monthrange
        _, last_day = monthrange(year, month)
        mes_inicio = f"{year}-{month:02d}-01"
        mes_fim = f"{year}-{month:02d}-{last_day:02d}"
    else:
        mes_inicio = today.replace(day=1).isoformat()
        mes_fim = today.isoformat()
        year, month = today.year, today.month

    rec_r = run_erp(["list_receivables", "--from", mes_inicio, "--to", mes_fim, "--limit", "500"])
    pay_r = run_erp(["list_payables", "--from", mes_inicio, "--to", mes_fim, "--limit", "500"])

    receita_bruta = sum_amounts(rec_r)
    total_saidas = sum_amounts(pay_r)

    # Estimativas BR típicas para PME Simples Nacional
    env_file = Path.home() / ".agente-cfo" / ".env"
    regime = "SN"  # default
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("CFO_REGIME_TRIBUTARIO="):
                regime = line.split("=", 1)[1].strip().upper()

    if regime in ("LP", "LUCRO_PRESUMIDO"):
        aliquota_ir = 0.132   # IRPJ 15% + CSLL 9% sobre 8% receita
        aliquota_pis_cofins = 0.0365
    elif regime in ("LR", "LUCRO_REAL"):
        aliquota_ir = 0.34    # 25% IRPJ + 9% CSLL
        aliquota_pis_cofins = 0.0925
    else:  # Simples Nacional
        aliquota_ir = 0.0
        aliquota_pis_cofins = 0.0  # incluso no DAS

    deducoes = receita_bruta * aliquota_pis_cofins
    receita_liquida = receita_bruta - deducoes

    # Estrutura de custos estimada
    cmv = total_saidas * 0.42
    lucro_bruto = receita_liquida - cmv

    desp_op = total_saidas * 0.38
    ebitda = lucro_bruto - desp_op

    desp_fin = total_saidas * 0.07
    ebt = ebitda - desp_fin

    ir_csll = ebt * aliquota_ir if ebt > 0 else 0
    lucro_liquido = ebt - ir_csll

    dre = {
        "periodo": f"{year}-{month:02d}",
        "regime_tributario": regime,
        "receita_bruta": receita_bruta,
        "deducoes": -deducoes,
        "receita_liquida": receita_liquida,
        "cmv": -cmv,
        "lucro_bruto": lucro_bruto,
        "despesas_operacionais": -desp_op,
        "ebitda": ebitda,
        "despesas_financeiras": -desp_fin,
        "ebt": ebt,
        "ir_csll": -ir_csll,
        "lucro_liquido": lucro_liquido,
        "margem_liquida_pct": round((lucro_liquido / receita_bruta * 100) if receita_bruta else 0, 1),
        "estimado": True,
    }

    if FORMAT == "json":
        print(json.dumps(dre, ensure_ascii=False))
        return

    # Formatado para leitura
    lbl = lambda s, v: f"  {s:<35} {fmt(v)}"
    print(f"📋 DRE — {month:02d}/{year} (estimativa{' ' + regime})")
    print(f"  {'=' * 50}")
    print(lbl("(+) Receita Bruta", receita_bruta))
    if deducoes:
        print(lbl("(-) Deduções/PIS-COFINS", -deducoes))
        print(lbl("(=) Receita Líquida", receita_liquida))
    print(lbl("(-) CMV / Custo Serviços", -cmv))
    print(lbl("(=) LUCRO BRUTO", lucro_bruto))
    print(lbl("(-) Despesas Operacionais", -desp_op))
    print(lbl("(=) EBITDA aprox.", ebitda))
    print(lbl("(-) Despesas Financeiras", -desp_fin))
    print(lbl("(=) Lucro Antes IR", ebt))
    if ir_csll:
        print(lbl("(-) IR + CSLL", -ir_csll))
    print(lbl("(=) LUCRO LÍQUIDO", lucro_liquido))
    print(f"  {'=' * 50}")
    m_l = dre["margem_liquida_pct"]
    signal = "🔴" if m_l < 3 else ("🟡" if m_l < 8 else "🟢")
    print(f"  Margem líquida: {m_l:.1f}% {signal}")
    print(f"  ⚠ Valores estimados — use contador para DRE oficial.")


if __name__ == "__main__":
    main()
