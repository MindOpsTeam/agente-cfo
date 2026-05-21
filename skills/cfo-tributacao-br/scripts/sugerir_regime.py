#!/usr/bin/env python3
"""sugerir_regime.py — Ilustra carga tributária estimada por regime (educativo)."""
import json
import sys

FORMAT = "text"; FAT = None; MARGEM = 0.30
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--faturamento_anual" and i+1 < len(sys.argv): FAT = float(sys.argv[i+1]); i += 2
    elif a == "--margem" and i+1 < len(sys.argv): MARGEM = float(sys.argv[i+1]) / 100; i += 2
    else: i += 1

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def main():
    if FAT is None:
        print(json.dumps({"error": "Informe --faturamento_anual"}) if FORMAT == "json"
              else "Uso: python3 sugerir_regime.py --faturamento_anual 500000 --margem 30")
        return

    # Estimativas simplificadas — apenas educativas
    lucro = FAT * MARGEM

    # SN: alíquota média estimada por faixa de faturamento
    if FAT <= 180_000: sn_aliq = 0.04
    elif FAT <= 360_000: sn_aliq = 0.075
    elif FAT <= 720_000: sn_aliq = 0.10
    elif FAT <= 1_800_000: sn_aliq = 0.14
    elif FAT <= 3_600_000: sn_aliq = 0.19
    else: sn_aliq = 0.225  # próximo do teto

    carga_sn = FAT * sn_aliq

    # LP: IRPJ 15% sobre 8% + CSLL 9% sobre 12% + PIS 0.65% + COFINS 3%
    lp_irpj = FAT * 0.08 * 0.15
    lp_csll = FAT * 0.12 * 0.09
    lp_pis_cofins = FAT * (0.0065 + 0.03)
    carga_lp = lp_irpj + lp_csll + lp_pis_cofins

    # LR: sobre lucro real
    lr_irpj = max(lucro, 0) * 0.15
    lr_adicional = max(lucro - 240_000, 0) * 0.10
    lr_csll = max(lucro, 0) * 0.09
    lr_pis_cofins = FAT * 0.0925  # não-cumulativo (sem créditos aqui)
    carga_lr = lr_irpj + lr_adicional + lr_csll + lr_pis_cofins

    cargas = [("Simples Nacional", carga_sn, "Disponível" if FAT <= 4_800_000 else "Fora da faixa"),
              ("Lucro Presumido", carga_lp, "Disponível" if FAT <= 78_000_000 else "Obrigatório LR"),
              ("Lucro Real", carga_lr, "Sempre disponível")]
    cargas_disp = [(n, c, s) for n, c, s in cargas if "Disponível" in s or "Obrigatório" in s or "Sempre" in s]
    melhor = min(cargas_disp, key=lambda x: x[1])

    result = {"faturamento_anual": FAT, "margem_pct": MARGEM * 100,
              "regimes": {n: {"carga_estimada": round(c, 2),
                              "pct_faturamento": round(c/FAT*100, 1), "status": s}
                          for n, c, s in cargas}}

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🧾 Estimativa de Carga Tributária — {fmt(FAT)}/ano, margem {MARGEM*100:.0f}%")
    print(f"  ⚠ ESTIMATIVA EDUCATIVA — consulte seu contador antes de qualquer decisão.")
    print()
    for nome, carga, status in cargas:
        pct = carga/FAT*100
        marker = "  ◀ menor carga" if nome == melhor[0] else ""
        print(f"  {nome:<20} {fmt(carga):>12} ({pct:.1f}%)  [{status}]{marker}")
    print()
    print(f"  Menor carga estimada: {melhor[0]} — diferença pode ser {fmt(abs(cargas[0][1]-cargas[1][1]))}/ano")
    print(f"  Mas carga não é tudo: regime afeta créditos, obrigações, etc.")

if __name__ == "__main__":
    main()
