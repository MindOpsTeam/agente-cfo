#!/usr/bin/env python3
"""
criar_cenario.py — Cria e salva um cenário financeiro nomeado.

Uso:
  python3 criar_cenario.py --nome "crescimento" --params "receita_mensal_pct=+30;despesa_pct=+15"
  python3 criar_cenario.py --nome "cautela" --params "despesa_pct=-15;inadimplencia_pct=5"
  python3 criar_cenario.py --format json --nome X --params Y
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
CENARIOS_DIR = Path.home() / ".agente-cfo" / "memory" / "cenarios"
SNAPSHOT_PY = SCRIPTS_DIR / "snapshot_financeiro.py"

FORMAT = "text"
NOME = None
PARAMS_STR = None
HORIZONTE = 90

i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--nome" and i + 1 < len(sys.argv): NOME = sys.argv[i + 1]; i += 2
    elif a == "--params" and i + 1 < len(sys.argv): PARAMS_STR = sys.argv[i + 1]; i += 2
    elif a == "--horizonte" and i + 1 < len(sys.argv): HORIZONTE = int(sys.argv[i + 1]); i += 2
    else: i += 1


def parse_params(s: str) -> dict:
    """Parses 'receita_mensal_pct=+30;despesa_pct=-15'"""
    result = {}
    if not s: return result
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            try: result[k.strip()] = float(v.strip())
            except: result[k.strip()] = v.strip()
    return result


def get_snapshot() -> dict:
    if not SNAPSHOT_PY.exists(): return {}
    r = subprocess.run(["python3", str(SNAPSHOT_PY), "--get"],
                       capture_output=True, text=True, timeout=10)
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def project_scenario(snap: dict, params: dict, horizonte: int) -> dict:
    """Projeta saldo final, burn e runway dado o cenário."""
    balance = float(snap.get("balance") or 0)
    burn = float(snap.get("burn_mensal_estimado") or 0)
    receita = float(snap.get("total_receivables_mes") or 0)

    # Aplica parâmetros
    rec_pct = 1 + params.get("receita_mensal_pct", 0) / 100
    desp_pct = 1 + params.get("despesa_pct", 0) / 100
    receita_extra = params.get("receita_fixa_adicional", 0)
    desp_extra = params.get("despesa_extra", 0)
    inad = params.get("inadimplencia_pct", float(snap.get("inadimplencia_pct") or 10)) / 100

    receita_mes = (receita * rec_pct + receita_extra) * (1 - inad)
    burn_mes = burn * desp_pct + desp_extra
    saldo_mensal = receita_mes - burn_mes
    meses = horizonte / 30

    caixa_final = balance + saldo_mensal * meses
    runway = (caixa_final / burn_mes) if burn_mes > 0 else 99.0
    margem = (saldo_mensal / receita_mes * 100) if receita_mes > 0 else 0

    return {
        "caixa_inicial": balance,
        "receita_mensal_projetada": round(receita_mes, 2),
        "burn_mensal_projetado": round(burn_mes, 2),
        "saldo_mensal": round(saldo_mensal, 2),
        "caixa_final": round(caixa_final, 2),
        "runway_meses": round(runway, 1),
        "margem_pct": round(margem, 1),
        "horizonte_dias": horizonte,
    }


def main():
    if not NOME:
        print(json.dumps({"error": "Informe --nome e --params"}) if FORMAT == "json"
              else "Uso: python3 criar_cenario.py --nome X --params 'key=val;key2=val2'")
        return

    params = parse_params(PARAMS_STR or "")
    snap = get_snapshot()
    projecao = project_scenario(snap, params, HORIZONTE)

    cenario = {
        "nome": NOME,
        "params": params,
        "horizonte_dias": HORIZONTE,
        "projecao": projecao,
        "snapshot_base": snap,
        "criado_em": date.today().isoformat(),
    }

    CENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    safe_nome = NOME.replace(" ", "_").replace("/", "_")
    (CENARIOS_DIR / f"{safe_nome}.json").write_text(
        json.dumps(cenario, indent=2, ensure_ascii=False)
    )

    if FORMAT == "json":
        print(json.dumps(cenario, ensure_ascii=False))
        return

    def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    p = projecao
    print(f"🗂️ Cenário '{NOME}' criado")
    print(f"   Parâmetros: {params}")
    print(f"   Horizonte: {HORIZONTE} dias")
    print(f"   Receita/mês projetada: {fmt(p['receita_mensal_projetada'])}")
    print(f"   Burn/mês projetado:    {fmt(p['burn_mensal_projetado'])}")
    print(f"   Caixa final:           {fmt(p['caixa_final'])}")
    print(f"   Runway projetado:      {p['runway_meses']:.1f} meses")
    print(f"   Margem projetada:      {p['margem_pct']:.1f}%")


if __name__ == "__main__":
    main()
