#!/usr/bin/env python3
"""
calendario_fiscal.py — Próximas obrigações fiscais (30 dias).

Uso:
  python3 calendario_fiscal.py
  python3 calendario_fiscal.py --regime SN      # filtra pelo regime
  python3 calendario_fiscal.py --dias 60
  python3 calendario_fiscal.py --format json
"""
import json
import os
import sys
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

ENV_FILE = Path.home() / ".agente-cfo" / ".env"
REGIME = "SN"
FORMAT = "text"
DIAS = 30
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--regime" and i+1 < len(sys.argv): REGIME = sys.argv[i+1].upper(); i += 2
    elif a == "--dias" and i+1 < len(sys.argv): DIAS = int(sys.argv[i+1]); i += 2
    else: i += 1

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("CFO_REGIME_TRIBUTARIO="):
            REGIME = line.split("=",1)[1].strip().upper()

def next_workday(d: date) -> date:
    while d.weekday() >= 5:  # sab=5, dom=6
        d += timedelta(days=1)
    return d

def this_month_day(day: int, d: date = None) -> date:
    ref = d or date.today()
    _, last = monthrange(ref.year, ref.month)
    return ref.replace(day=min(day, last))

def next_month_day(day: int, d: date = None) -> date:
    ref = d or date.today()
    m = ref.month + 1; y = ref.year
    if m > 12: m = 1; y += 1
    _, last = monthrange(y, m)
    return date(y, m, min(day, last))

def main():
    today = date.today()
    horizon = today + timedelta(days=DIAS)
    y, m = today.year, today.month

    obrigacoes = []

    # DAS Simples Nacional — dia 20 mês seguinte
    if REGIME in ("SN", "SIMPLES", "SIMPLES_NACIONAL", "TODOS"):
        d = next_workday(next_month_day(20))
        if today <= d <= horizon:
            obrigacoes.append({"obrigacao": "DAS (Simples Nacional)", "vencimento": d.isoformat(),
                               "regime": "SN", "recorrencia": "Mensal"})

    # FGTS — dia 7 mês seguinte
    d_fgts = next_workday(next_month_day(7))
    if today <= d_fgts <= horizon:
        obrigacoes.append({"obrigacao": "FGTS", "vencimento": d_fgts.isoformat(),
                           "regime": "Todos", "recorrencia": "Mensal"})

    # GPS / INSS empresa — dia 20 mês seguinte
    d_inss = next_workday(next_month_day(20))
    if today <= d_inss <= horizon and d_inss != obrigacoes[0]["vencimento"] if obrigacoes else True:
        obrigacoes.append({"obrigacao": "GPS/INSS Empresa", "vencimento": d_inss.isoformat(),
                           "regime": "LP/LR", "recorrencia": "Mensal"})

    # IRRF sobre salários — dia 20
    if today <= d_inss <= horizon:
        obrigacoes.append({"obrigacao": "IRRF s/ Salários (DARF)", "vencimento": d_inss.isoformat(),
                           "regime": "Todos", "recorrencia": "Mensal"})

    # DARF trimestral — jan/abr/jul/out (último dia útil)
    trim_months = [1, 4, 7, 10]
    for tm in trim_months:
        ty = y if tm >= m else y + 1
        if tm < m: ty = y; tm_actual = tm + 3 if tm + 3 <= 12 else tm + 3 - 12
        else: tm_actual = tm
        _, ld = monthrange(ty, tm_actual)
        d_trim = next_workday(date(ty, tm_actual, ld))
        if today <= d_trim <= horizon:
            obrigacoes.append({"obrigacao": f"DARF IRPJ/CSLL {tm_actual:02d}/{ty}", "vencimento": d_trim.isoformat(),
                               "regime": "LP/LR", "recorrencia": "Trimestral"})

    # 13º salário (novembro/dezembro)
    if m == 11 or (m == 10 and (date(y, 11, 30) - today).days <= DIAS):
        obrigacoes.append({"obrigacao": "13º Salário — 1ª parcela", "vencimento": f"{y}-11-30",
                           "regime": "Todos", "recorrencia": "Anual"})
    if m == 12 or (m == 11 and (date(y, 12, 20) - today).days <= DIAS):
        obrigacoes.append({"obrigacao": "13º Salário — 2ª parcela + INSS", "vencimento": f"{y}-12-20",
                           "regime": "Todos", "recorrencia": "Anual"})

    obrigacoes = [o for o in obrigacoes if today <= date.fromisoformat(o["vencimento"]) <= horizon]
    obrigacoes.sort(key=lambda x: x["vencimento"])

    if FORMAT == "json":
        print(json.dumps({"date": today.isoformat(), "regime": REGIME, "obrigacoes": obrigacoes}, ensure_ascii=False))
        return

    print(f"🧾 Calendário Fiscal — próximos {DIAS} dias (regime: {REGIME})")
    if not obrigacoes:
        print("  ✅ Nenhuma obrigação fiscal nos próximos dias"); return
    for o in obrigacoes:
        d = date.fromisoformat(o["vencimento"])
        dias_ate = (d - today).days
        urgency = "🔴" if dias_ate <= 7 else ("🟡" if dias_ate <= 15 else "🟢")
        print(f"  {urgency} {o['obrigacao']:<35} {d.strftime('%d/%m/%Y')} (em {dias_ate}d)")

if __name__ == "__main__":
    main()
