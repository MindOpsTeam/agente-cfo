#!/usr/bin/env python3
"""
analise.py — Análise de sensibilidade: qual variável tem mais impacto no target.

Uso:
  python3 analise.py --target caixa_final --horizonte 90
  python3 analise.py --target runway_meses --horizonte 60
  python3 analise.py --format json --target caixa_final
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
SNAPSHOT_PY = SCRIPTS_DIR / "snapshot_financeiro.py"

FORMAT = "text"
TARGET = "caixa_final"
HORIZONTE = 90
VARIACAO = 0.10  # ±10%
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--target" and i + 1 < len(sys.argv): TARGET = sys.argv[i + 1]; i += 2
    elif a == "--horizonte" and i + 1 < len(sys.argv): HORIZONTE = int(sys.argv[i + 1]); i += 2
    elif a == "--variacao" and i + 1 < len(sys.argv): VARIACAO = float(sys.argv[i + 1]) / 100; i += 2
    else: i += 1


def get_snap() -> dict:
    if not SNAPSHOT_PY.exists(): return {}
    r = subprocess.run(["python3", str(SNAPSHOT_PY), "--get"],
                       capture_output=True, text=True, timeout=10)
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def project(snap: dict, overrides: dict, horizonte: int) -> float:
    balance = float(snap.get("balance") or 0)
    burn = float(overrides.get("burn", snap.get("burn_mensal_estimado") or 0))
    receita = float(overrides.get("receita", snap.get("total_receivables_mes") or 0))
    inad = float(overrides.get("inadimplencia_pct", snap.get("inadimplencia_pct") or 10)) / 100

    rec_ef = receita * (1 - inad)
    saldo_mes = rec_ef - burn
    caixa_final = balance + saldo_mes * (horizonte / 30)

    if TARGET == "runway_meses":
        return round(caixa_final / burn, 2) if burn > 0 else 99.0
    elif TARGET == "margem_pct":
        return round(saldo_mes / rec_ef * 100, 1) if rec_ef > 0 else 0
    return round(caixa_final, 2)


def fmt(v: float) -> str:
    if TARGET in ("runway_meses", "margem_pct"):
        return f"{v:.1f}{'m' if TARGET == 'runway_meses' else '%'}"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    snap = get_snap()
    base_val = project(snap, {}, HORIZONTE)

    VARIABLES = {
        "receita": ("receita", "Receita mensal"),
        "burn": ("burn", "Despesas/burn"),
        "inadimplencia_pct": ("inadimplencia_pct", "Inadimplência"),
    }

    results = []
    for var_key, (override_key, label) in VARIABLES.items():
        base_num = float(snap.get(override_key if var_key != "inadimplencia_pct" else "inadimplencia_pct")
                         or snap.get("burn_mensal_estimado" if var_key == "burn" else "total_receivables_mes")
                         or 0)
        if base_num == 0:
            base_num = 1  # evita div zero

        up_val = project(snap, {override_key: base_num * (1 + VARIACAO)}, HORIZONTE)
        dn_val = project(snap, {override_key: base_num * (1 - VARIACAO)}, HORIZONTE)

        impact_up = up_val - base_val
        impact_dn = dn_val - base_val
        avg_abs = (abs(impact_up) + abs(impact_dn)) / 2

        results.append({
            "variavel": var_key,
            "label": label,
            "variacao_pct": VARIACAO * 100,
            "base": base_val,
            "up": up_val,
            "dn": dn_val,
            "impacto_up": impact_up,
            "impacto_dn": impact_dn,
            "alavanca_media": avg_abs,
        })

    results.sort(key=lambda r: r["alavanca_media"], reverse=True)

    # Stars
    max_alav = max(r["alavanca_media"] for r in results) if results else 1

    def stars(v, mx):
        if mx == 0: return "⭐"
        ratio = v / mx
        if ratio >= 0.7: return "⭐⭐⭐ Alta"
        if ratio >= 0.4: return "⭐⭐ Média"
        return "⭐ Baixa"

    for r in results:
        r["alavanca_label"] = stars(r["alavanca_media"], max_alav)

    result = {
        "target": TARGET, "horizonte_dias": HORIZONTE, "variacao_pct": VARIACAO * 100,
        "base": base_val, "variaveis": results,
        "maior_alavanca": results[0] if results else None,
        "sem_dados": not bool(snap and float(snap.get("balance") or 0) > 0),
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    if result["sem_dados"]:
        print(f"⚠️ Sem dados ERP — análise com valores zerados (placeholder)\n")

    print(f"📐 Análise de Sensibilidade — target: {TARGET} | horizonte: {HORIZONTE}d | variação: ±{VARIACAO*100:.0f}%")
    print(f"   Base atual: {fmt(base_val)}\n")
    print(f"   {'Variável':<22} {'+'+str(int(VARIACAO*100))+'%':>14} {'-'+str(int(VARIACAO*100))+'%':>14} {'Alavanca'}")
    print(f"   {'-'*65}")
    for r in results:
        up_s = (f"+{fmt(r['impacto_up'])}" if r['impacto_up'] >= 0 else fmt(r['impacto_up']))
        dn_s = (f"+{fmt(r['impacto_dn'])}" if r['impacto_dn'] >= 0 else fmt(r['impacto_dn']))
        print(f"   {r['label']:<22} {up_s:>14} {dn_s:>14}   {r['alavanca_label']}")

    if results:
        top = results[0]
        print(f"\n   💡 Maior alavanca: {top['label']}")
        print(f"      Cada ±{VARIACAO*100:.0f}% move {TARGET} em ±{fmt(top['alavanca_media'])}")


if __name__ == "__main__":
    main()
