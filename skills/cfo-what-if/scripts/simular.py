#!/usr/bin/env python3
"""
simular.py — Simulador "e se?" mês-a-mês comparado com cenário base.

Uso:
  python3 simular.py --variaveis '{"despesa_mensal":-3000}' --horizonte 90
  python3 simular.py --variaveis '{"receita_mensal_pct":20,"inadimplencia_pct":5}' --horizonte 60
  python3 simular.py --format json --variaveis '{...}'
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
SNAPSHOT_PY = SCRIPTS_DIR / "snapshot_financeiro.py"

FORMAT = "text"
VARS: dict = {}
HORIZONTE = 90
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--variaveis" and i + 1 < len(sys.argv):
        try: VARS = json.loads(sys.argv[i + 1])
        except: VARS = {}
        i += 2
    elif a == "--horizonte" and i + 1 < len(sys.argv): HORIZONTE = int(sys.argv[i + 1]); i += 2
    else: i += 1


def get_snap() -> dict:
    if not SNAPSHOT_PY.exists(): return {}
    r = subprocess.run(["python3", str(SNAPSHOT_PY), "--get"],
                       capture_output=True, text=True, timeout=10)
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def simulate_months(snap: dict, vars: dict, horizonte: int) -> list[dict]:
    """Simula mês-a-mês com as variáveis aplicadas."""
    balance = float(snap.get("balance") or 0)
    burn_base = float(snap.get("burn_mensal_estimado") or 0)
    receita_base = float(snap.get("total_receivables_mes") or 0)
    overdue = float(snap.get("total_overdue") or 0)
    inad_base = float(snap.get("inadimplencia_pct") or 10) / 100

    # Aplica variáveis
    desp_delta = float(vars.get("despesa_mensal") or 0)
    rec_delta = float(vars.get("receita_mensal") or 0)
    rec_pct = 1 + float(vars.get("receita_mensal_pct") or 0) / 100
    inad_new = float(vars.get("inadimplencia_pct") or (inad_base * 100)) / 100
    cobrar = vars.get("cobrar_inadimplentes", False)
    antecip_pct = float(vars.get("antecipacao_recebivel_pct") or 0) / 100

    receita_mes = (receita_base * rec_pct + rec_delta) * (1 - inad_new)
    burn_mes = max(0, burn_base + desp_delta)

    saldo_corrente = balance
    if cobrar and overdue > 0:
        saldo_corrente += overdue  # assume recuperação total (otimista)
    if antecip_pct > 0:
        saldo_corrente += receita_base * antecip_pct  # antecipação única mês 1

    months = []
    for m in range(1, int(horizonte / 30) + 1):
        saldo_corrente += receita_mes - burn_mes
        months.append({
            "mes": m,
            "saldo": round(saldo_corrente, 2),
            "receita_mes": round(receita_mes, 2),
            "burn_mes": round(burn_mes, 2),
            "saldo_mensal": round(receita_mes - burn_mes, 2),
        })
    return months


def simulate_base(snap: dict, horizonte: int) -> list[dict]:
    return simulate_months(snap, {}, horizonte)


def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")


def main():
    if not VARS:
        print(json.dumps({"error": "Informe --variaveis '{...}'"}) if FORMAT == "json"
              else "Uso: python3 simular.py --variaveis '{\"despesa_mensal\":-3000}'")
        return

    snap = get_snap()
    base = simulate_base(snap, HORIZONTE)
    simul = simulate_months(snap, VARS, HORIZONTE)

    burn_base = float(snap.get("burn_mensal_estimado") or 0)
    caixa_base = base[-1]["saldo"] if base else 0
    caixa_simul = simul[-1]["saldo"] if simul else 0
    delta_caixa = caixa_simul - caixa_base
    runway_simul = (caixa_simul / burn_base) if burn_base > 0 else 99.0

    result = {
        "variaveis": VARS,
        "horizonte_dias": HORIZONTE,
        "cenario_base": {"caixa_final": caixa_base, "runway_meses": round(burn_base and caixa_base/burn_base or 0, 1)},
        "cenario_simulado": {"caixa_final": caixa_simul, "runway_meses": round(runway_simul, 1)},
        "delta_caixa": round(delta_caixa, 2),
        "meses": simul,
        "sem_dados": not bool(snap and float(snap.get("balance") or 0) > 0),
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    if result["sem_dados"]:
        print("⚠️ Sem dados do ERP — simulação com valores zerados (placeholder)")

    delta_s = f"+{fmt(delta_caixa)}" if delta_caixa >= 0 else fmt(delta_caixa)
    signal = "🟢" if delta_caixa > 0 else "🔴"
    print(f"🔬 Simulação 'E se?' — {HORIZONTE} dias")
    print(f"   Variáveis: {VARS}")
    print()
    print(f"   Caixa final BASE:      {fmt(caixa_base)}")
    print(f"   Caixa final SIMULADO:  {fmt(caixa_simul)}  {delta_s} {signal}")
    print(f"   Runway simulado:       {runway_simul:.1f} meses")
    print()
    print(f"   {'Mês':<5} {'Base':>14} {'Simulado':>14} {'Δ':>12}")
    print(f"   {'-'*48}")
    for b, s in zip(base, simul):
        d = s["saldo"] - b["saldo"]
        ds = f"+{fmt(d)}" if d >= 0 else fmt(d)
        print(f"   {b['mes']:<5} {fmt(b['saldo']):>14} {fmt(s['saldo']):>14} {ds:>12}")


if __name__ == "__main__":
    main()
