#!/usr/bin/env python3
"""
zscore.py — Z-score do gasto total do mês atual vs média histórica 3 meses.

Detecta se o nível de despesas atual é anômalo.
Uso:
  python3 zscore.py
  python3 zscore.py --meses 6    # janela histórica maior
  python3 zscore.py --format json
"""
import json
import math
import subprocess
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"
MESES_HIST = 3
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--meses" and i+1 < len(sys.argv): MESES_HIST = int(sys.argv[i+1]); i += 2
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
    historico = []
    for offset in range(1, MESES_HIST + 1):
        m = today.month - offset
        y = today.year
        while m <= 0: m += 12; y -= 1
        _, ld = monthrange(y, m)
        total = sum_amounts(run_erp(["list_payables", "--from", f"{y}-{m:02d}-01", "--to", f"{y}-{m:02d}-{ld:02d}", "--limit","500"]))
        historico.append(total)

    mes_init = today.replace(day=1).isoformat()
    atual = sum_amounts(run_erp(["list_payables", "--from", mes_init, "--to", today.isoformat(), "--limit","500"]))
    # Normaliza atual para 30 dias
    atual_norm = (atual / max(today.day, 1)) * 30

    media = sum(historico) / max(len(historico), 1)
    if len(historico) > 1:
        var = sum((x - media) ** 2 for x in historico) / (len(historico) - 1)
        std = math.sqrt(var)
    else:
        std = 0

    zscore = ((atual_norm - media) / std) if std > 0 else 0.0
    is_anomaly = abs(zscore) > 2.0
    is_critical = abs(zscore) > 3.0

    result = {
        "date": today.isoformat(),
        "despesas_mes_atual": round(atual, 2),
        "despesas_mes_normalizado": round(atual_norm, 2),
        "media_historica": round(media, 2),
        "std_historica": round(std, 2),
        "zscore": round(zscore, 2),
        "anomalia": is_anomaly,
        "critico": is_critical,
        "meses_historico": MESES_HIST,
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    signal = "🔴 ANOMALIA CRÍTICA" if is_critical else ("🟠 ANOMALIA" if is_anomaly else "🟢 Normal")
    print(f"🔍 Z-score de Despesas — {today.strftime('%d/%m/%Y')}")
    print(f"  Despesas mês atual (norm.): {fmt(atual_norm)}")
    print(f"  Média histórica ({MESES_HIST}m):    {fmt(media)}")
    print(f"  Desvio padrão:              {fmt(std)}")
    print(f"  Z-score:                    {zscore:.2f}σ  → {signal}")
    if is_anomaly:
        diff = atual_norm - media
        print(f"  ⚠ Despesas {fmt(diff)} acima do normal — investigar.")

if __name__ == "__main__":
    main()
