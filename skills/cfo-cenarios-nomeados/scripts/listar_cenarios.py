#!/usr/bin/env python3
"""listar_cenarios.py — Lista cenários salvos."""
import json, sys
from pathlib import Path

CENARIOS_DIR = Path.home() / ".agente-cfo" / "memory" / "cenarios"
FORMAT = "text"
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    else: i += 1

def fmt(v):
    try: return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except: return str(v)

def main():
    CENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(CENARIOS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    cenarios = []
    for f in files:
        try:
            d = json.loads(f.read_text())
            cenarios.append(d)
        except: pass

    if FORMAT == "json":
        print(json.dumps(cenarios, ensure_ascii=False)); return

    if not cenarios:
        print("Nenhum cenário salvo. Use criar_cenario.py para criar um."); return
    print(f"🗂️ Cenários salvos ({len(cenarios)}):")
    print(f"  {'Nome':<25} {'Caixa Final':>15} {'Runway':>10} {'Margem':>8} {'Data'}")
    print(f"  {'-'*70}")
    for c in cenarios:
        p = c.get("projecao", {})
        print(f"  {c['nome']:<25} {fmt(p.get('caixa_final',0)):>15} "
              f"{p.get('runway_meses',0):>9.1f}m {p.get('margem_pct',0):>7.1f}% "
              f"  {c.get('criado_em','?')[:10]}")

if __name__ == "__main__":
    main()
