#!/usr/bin/env python3
"""
multi_simular.py — Varredura de N simulações pra encontrar ponto ótimo.

Uso:
  python3 multi_simular.py --variavel despesa_mensal --de -500 --ate -5000 --passo 500 \
    --target runway_meses --valor 6
  → Encontra o corte mínimo em despesa pra atingir runway de 6 meses.
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
SNAPSHOT_PY = SCRIPTS_DIR / "snapshot_financeiro.py"

FORMAT = "text"
VARIAVEL = None; DE = None; ATE = None; PASSO = None
TARGET = "runway_meses"; VALOR_META = None; HORIZONTE = 90
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--variavel" and i+1 < len(sys.argv): VARIAVEL = sys.argv[i+1]; i += 2
    elif a == "--de" and i+1 < len(sys.argv): DE = float(sys.argv[i+1]); i += 2
    elif a == "--ate" and i+1 < len(sys.argv): ATE = float(sys.argv[i+1]); i += 2
    elif a == "--passo" and i+1 < len(sys.argv): PASSO = float(sys.argv[i+1]); i += 2
    elif a == "--target" and i+1 < len(sys.argv): TARGET = sys.argv[i+1]; i += 2
    elif a == "--valor" and i+1 < len(sys.argv): VALOR_META = float(sys.argv[i+1]); i += 2
    elif a == "--horizonte" and i+1 < len(sys.argv): HORIZONTE = int(sys.argv[i+1]); i += 2
    else: i += 1


def get_snap() -> dict:
    if not SNAPSHOT_PY.exists(): return {}
    r = subprocess.run(["python3", str(SNAPSHOT_PY), "--get"], capture_output=True, text=True, timeout=10)
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def simulate_once(snap: dict, var: str, val: float, horizonte: int) -> dict:
    balance = float(snap.get("balance") or 0)
    burn = float(snap.get("burn_mensal_estimado") or 0)
    receita = float(snap.get("total_receivables_mes") or 0)
    inad = float(snap.get("inadimplencia_pct") or 10) / 100

    if var == "despesa_mensal":
        burn_sim = max(0, burn + val)
        rec_sim = receita * (1 - inad)
    elif var == "receita_mensal":
        burn_sim = burn
        rec_sim = (receita + val) * (1 - inad)
    elif var == "receita_mensal_pct":
        burn_sim = burn
        rec_sim = receita * (1 + val / 100) * (1 - inad)
    else:
        burn_sim = burn; rec_sim = receita * (1 - inad)

    saldo_mes = rec_sim - burn_sim
    caixa_final = balance + saldo_mes * (horizonte / 30)
    runway = (caixa_final / burn_sim) if burn_sim > 0 else 99.0
    margem = (saldo_mes / rec_sim * 100) if rec_sim > 0 else 0
    return {"caixa_final": round(caixa_final, 2), "runway_meses": round(runway, 1),
            "margem_pct": round(margem, 1), "saldo_mensal": round(saldo_mes, 2)}


def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")


def main():
    if not VARIAVEL or DE is None or ATE is None or PASSO is None:
        print(json.dumps({"error": "--variavel, --de, --ate, --passo são obrigatórios"}) if FORMAT=="json"
              else "Uso: python3 multi_simular.py --variavel X --de V1 --ate V2 --passo P")
        return

    snap = get_snap()
    steps = []
    current = DE
    direction = 1 if ATE >= DE else -1
    while (direction == 1 and current <= ATE) or (direction == -1 and current >= ATE):
        res = simulate_once(snap, VARIAVEL, current, HORIZONTE)
        steps.append({"valor": current, **res})
        current += PASSO * direction

    # Encontra ponto onde TARGET >= VALOR_META (se especificado)
    ponto_otimo = None
    if VALOR_META is not None:
        for s in steps:
            if s.get(TARGET, 0) >= VALOR_META:
                ponto_otimo = s
                break

    result = {"variavel": VARIAVEL, "de": DE, "ate": ATE, "passo": PASSO,
              "target": TARGET, "valor_meta": VALOR_META,
              "ponto_otimo": ponto_otimo, "simulacoes": steps}

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🔬 Varredura: '{VARIAVEL}' de {fmt(DE)} a {fmt(ATE)} (passo {fmt(PASSO)})")
    print(f"   Target: {TARGET} ≥ {VALOR_META}\n")
    print(f"   {'Valor':<14} {'Caixa Final':>14} {'Runway':>10} {'Margem':>8}")
    print(f"   {'-'*50}")
    for s in steps:
        mark = " ← ✅ META" if ponto_otimo and s["valor"] == ponto_otimo["valor"] else ""
        print(f"   {fmt(s['valor']):<14} {fmt(s['caixa_final']):>14} {s['runway_meses']:>9.1f}m {s['margem_pct']:>7.1f}%{mark}")
    if ponto_otimo:
        print(f"\n   ✅ Ponto mínimo para {TARGET} ≥ {VALOR_META}: {VARIAVEL} = {fmt(ponto_otimo['valor'])}")
    else:
        print(f"\n   ❌ Meta de {TARGET} ≥ {VALOR_META} não atingida no intervalo testado")


if __name__ == "__main__":
    main()
