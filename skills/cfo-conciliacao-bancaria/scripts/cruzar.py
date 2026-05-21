#!/usr/bin/env python3
"""
cruzar.py — Cruza extrato bancário (importado) vs lançamentos ERP.

PLACEHOLDER — requer importar_extrato.py ter sido rodado antes.
Uso:
  python3 cruzar.py --periodo 30
  python3 cruzar.py --format json
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
EXTRATO_FILE = Path.home() / ".agente-cfo" / "extrato-temp.json"

FORMAT = "text"
PERIODO = 30
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a in ("--format", "--formato") and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--periodo" and i + 1 < len(sys.argv):
        PERIODO = int(sys.argv[i + 1]); i += 2
    else:
        i += 1


def run_erp(cmd: list) -> dict:
    s = SCRIPTS_DIR / "erp_gateway.py"
    r = subprocess.run(["python3", str(s)] + cmd, capture_output=True, text=True,
                       timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def fmt(v): return f"R$ {abs(float(v or 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    if not EXTRATO_FILE.exists():
        msg = ("⚠️ Extrato bancário não importado. "
               "Execute primeiro: python3 importar_extrato.py --arquivo <extrato.ofx>")
        print(json.dumps({"error": msg}) if FORMAT == "json" else msg)
        return

    extrato = json.loads(EXTRATO_FILE.read_text())
    today = date.today()
    start = (today - timedelta(days=PERIODO)).isoformat()
    end = today.isoformat()

    extrato_period = [t for t in extrato if start <= str(t.get("data", ""))[:10] <= end]
    creditos = [t for t in extrato_period if float(t.get("valor", 0)) > 0]
    debitos = [t for t in extrato_period if float(t.get("valor", 0)) < 0]

    erp_rec = (run_erp(["list_receivables", "--from", start, "--to", end, "--limit", "200"])
               .get("records") or [])
    erp_pay = (run_erp(["list_payables", "--from", start, "--to", end, "--limit", "200"])
               .get("records") or [])
    if not isinstance(erp_rec, list): erp_rec = []
    if not isinstance(erp_pay, list): erp_pay = []

    # Match créditos bancários vs recebimentos ERP
    matched_rec = set()
    credito_sem_erp = []
    for t in creditos:
        val = float(t.get("valor", 0))
        dt = str(t.get("data", ""))[:10]
        found = False
        for j, e in enumerate(erp_rec):
            if j in matched_rec: continue
            ev = float(e.get("amount_brl") or e.get("amount") or 0)
            ed = str(e.get("due_date") or e.get("date") or "")[:10]
            if abs(val - ev) <= 0.01 and abs((date.fromisoformat(dt) - date.fromisoformat(ed)).days) <= 1 if dt and ed else False:
                matched_rec.add(j); found = True; break
        if not found:
            credito_sem_erp.append({"data": dt, "valor": val, "descricao": t.get("descricao", "")[:40]})

    result = {
        "periodo_dias": PERIODO,
        "extrato_creditos": len(creditos),
        "extrato_debitos": len(debitos),
        "erp_recebimentos": len(erp_rec),
        "erp_pagamentos": len(erp_pay),
        "credito_sem_erp": credito_sem_erp,
        "divergencias": len(credito_sem_erp),
        "placeholder": True,
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🏦 Conciliação Bancária ↔ ERP — últimos {PERIODO} dias (PLACEHOLDER)")
    print(f"  Créditos banco: {len(creditos)} | ERP recebimentos: {len(erp_rec)}")
    if credito_sem_erp:
        print(f"  ❌ Créditos sem lançamento ERP ({len(credito_sem_erp)}):")
        for x in credito_sem_erp[:5]:
            print(f"    • {x['data']} {fmt(x['valor'])} — {x['descricao']}")
    else:
        print(f"  ✅ Sem divergências detectadas.")
    print(f"\n  ⚠️ Integração bancária via Open Finance/Pluggy: pendente.")


if __name__ == "__main__":
    main()
