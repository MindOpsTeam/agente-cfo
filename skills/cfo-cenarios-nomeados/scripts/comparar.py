#!/usr/bin/env python3
"""
comparar.py — Compara dois cenários nomeados lado-a-lado.

Uso:
  python3 comparar.py --a "crescimento" --b "cautela"
  python3 comparar.py --a X --b Y --metrica caixa_final|runway_meses|margem_pct
  python3 comparar.py --format json --a X --b Y
"""
import json, sys
from pathlib import Path

CENARIOS_DIR = Path.home() / ".agente-cfo" / "memory" / "cenarios"
FORMAT = "text"
A = None; B = None; METRICA = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--a" and i+1 < len(sys.argv): A = sys.argv[i+1]; i += 2
    elif a == "--b" and i+1 < len(sys.argv): B = sys.argv[i+1]; i += 2
    elif a == "--metrica" and i+1 < len(sys.argv): METRICA = sys.argv[i+1]; i += 2
    else: i += 1

def load(nome: str) -> dict | None:
    safe = nome.replace(" ","_").replace("/","_")
    for f in [CENARIOS_DIR / f"{safe}.json", CENARIOS_DIR / f"{nome}.json"]:
        if f.exists():
            try: return json.loads(f.read_text())
            except: pass
    return None

def fmt(v):
    try: return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return str(v)

METRICAS = ["caixa_final", "runway_meses", "margem_pct", "receita_mensal_projetada", "burn_mensal_projetado", "saldo_mensal"]
LABELS = {
    "caixa_final": "Caixa final",
    "runway_meses": "Runway (meses)",
    "margem_pct": "Margem (%)",
    "receita_mensal_projetada": "Receita/mês",
    "burn_mensal_projetado": "Burn/mês",
    "saldo_mensal": "Saldo mensal",
}

def main():
    if not A or not B:
        print(json.dumps({"error": "--a e --b obrigatórios"}) if FORMAT=="json"
              else "Uso: python3 comparar.py --a <nome> --b <nome>"); return

    ca = load(A)
    cb = load(B)
    if not ca: print(f"Cenário '{A}' não encontrado."); return
    if not cb: print(f"Cenário '{B}' não encontrado."); return

    pa = ca.get("projecao", {}); pb = cb.get("projecao", {})
    metricas = [METRICA] if METRICA else METRICAS
    comparison = []
    for m in metricas:
        va = pa.get(m); vb = pb.get(m)
        if va is None and vb is None: continue
        delta = None
        if va is not None and vb is not None:
            try: delta = round(float(vb) - float(va), 2)
            except: pass
        comparison.append({"metrica": m, "label": LABELS.get(m, m),
                           "cenario_a": va, "cenario_b": vb, "delta_b_vs_a": delta})

    result = {"cenario_a": A, "cenario_b": B, "horizonte_dias": ca.get("horizonte_dias"),
              "comparacao": comparison}

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🗂️ Comparação: '{A}' vs '{B}' ({ca.get('horizonte_dias')}d)\n")
    print(f"  {'Métrica':<28} {'A: '+A[:18]:<22} {'B: '+B[:18]:<22} {'Δ B-A'}")
    print(f"  {'-'*80}")
    for c in comparison:
        va_s = fmt(c['cenario_a']) if isinstance(c['cenario_a'], (int, float)) else str(c['cenario_a'])
        vb_s = fmt(c['cenario_b']) if isinstance(c['cenario_b'], (int, float)) else str(c['cenario_b'])
        d = c.get('delta_b_vs_a')
        delta_s = (f"+{fmt(d)}" if d and d > 0 else fmt(d)) if d is not None else "—"
        signal = "🟢" if d and d > 0 else ("🔴" if d and d < 0 else "")
        print(f"  {c['label']:<28} {va_s:<22} {vb_s:<22} {delta_s} {signal}")

if __name__ == "__main__":
    main()
