#!/usr/bin/env python3
"""
relatorio_mensal.py — Relatório executivo mensal completo.

Uso:
  python3 relatorio_mensal.py                      # mês anterior
  python3 relatorio_mensal.py --mes 2026-04
  python3 relatorio_mensal.py --format markdown    # full markdown pra painel
  python3 relatorio_mensal.py --format text        # resumo WA (600 chars)
  python3 relatorio_mensal.py --format json
"""
import json
import subprocess
import sys
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
CFO_SKILLS = Path(__file__).parent.parent.parent

FORMAT = "text"
MES_ARG = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--mes" and i+1 < len(sys.argv): MES_ARG = sys.argv[i+1]; i += 2
    else: i += 1


def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def run_skill(skill, script, extra_args=None):
    p = CFO_SKILLS / skill / "scripts" / script
    if not p.exists(): return {}
    cmd = ["python3", str(p), "--format", "json"] + (extra_args or [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def sum_r(r):
    lst = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(lst, list): return 0.0
    return sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0) for x in lst if isinstance(x, dict))


def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")


def main():
    today = date.today()
    if MES_ARG:
        y, m = map(int, MES_ARG.split("-"))
    else:
        d = today.replace(day=1) - timedelta(days=1)
        y, m = d.year, d.month

    _, ld = monthrange(y, m)
    s = f"{y}-{m:02d}-01"; e = f"{y}-{m:02d}-{ld}"

    # Mês anterior para comparativo
    d_prev = date(y, m, 1) - timedelta(days=1)
    yp, mp = d_prev.year, d_prev.month
    _, ldp = monthrange(yp, mp)
    sp = f"{yp}-{mp:02d}-01"; ep = f"{yp}-{mp:02d}-{ldp}"

    # Dados do mês
    rec = run_erp(["list_receivables", "--from", s, "--to", e, "--limit", "500"])
    pay = run_erp(["list_payables", "--from", s, "--to", e, "--limit", "500"])
    overdue = run_erp(["list_overdue"])
    bal = run_erp(["get_balance"])

    rec_prev = run_erp(["list_receivables", "--from", sp, "--to", ep, "--limit", "500"])
    pay_prev = run_erp(["list_payables", "--from", sp, "--to", ep, "--limit", "500"])

    rec_total = sum_r(rec)
    pay_total = sum_r(pay)
    rec_prev_total = sum_r(rec_prev)
    pay_prev_total = sum_r(pay_prev)
    overdue_total = sum_r(overdue)
    caixa = float(bal.get("balance") or bal.get("saldo") or bal.get("saldo_total") or 0)

    delta_rec = ((rec_total - rec_prev_total) / rec_prev_total * 100) if rec_prev_total else 0
    delta_pay = ((pay_total - pay_prev_total) / pay_prev_total * 100) if pay_prev_total else 0

    # Skills especializadas
    kpis = run_skill("cfo-analise-estrategica", "kpis.py")
    aging = run_skill("cfo-inadimplencia", "aging.py")
    top_dev = run_skill("cfo-inadimplencia", "top_devedores.py", ["--n", "5"])
    vert = run_skill("cfo-analise-estrategica", "analise_vertical.py")

    runway = float(kpis.get("runway_meses") or 0)
    burn = float(kpis.get("burn_mensal_estimado") or 0)
    dso = float(kpis.get("dso_dias") or 0)
    dpo = float(kpis.get("dpo_dias") or 0)

    # Recomendações automáticas
    recomendacoes = []
    if runway < 3:
        recomendacoes.append(f"Runway crítico ({runway:.1f}m): cortar custos variáveis e acelerar recebíveis.")
    if overdue_total > rec_total * 0.15:
        recomendacoes.append(f"Inadimplência acima de 15% do faturamento: executar campanha de cobrança.")
    if delta_rec < -15:
        recomendacoes.append(f"Receita caiu {abs(delta_rec):.0f}% vs mês anterior: investigar causas e pipeline CRM.")
    if delta_pay > 20:
        recomendacoes.append(f"Despesas subiram {delta_pay:.0f}%: mapear categoria de maior crescimento.")
    if not recomendacoes:
        recomendacoes.append("Mês estável. Focar em crescimento de receita e redução de DSO.")
    recomendacoes = recomendacoes[:3]

    data = {
        "periodo": f"{m:02d}/{y}", "gerado_em": today.isoformat(),
        "receita": rec_total, "pagamentos": pay_total, "resultado": rec_total - pay_total,
        "receita_prev": rec_prev_total, "delta_receita_pct": round(delta_rec, 1),
        "overdue_total": overdue_total,
        "caixa_atual": caixa, "runway_meses": runway, "burn_mensal": burn,
        "dso_dias": dso, "dpo_dias": dpo,
        "aging": aging.get("buckets") or {},
        "top_devedores": top_dev.get("clientes") or [],
        "categorias": vert.get("categorias") or [],
        "recomendacoes": recomendacoes,
    }

    if FORMAT == "json":
        print(json.dumps(data, ensure_ascii=False)); return

    res_signal = "🟢" if data["resultado"] >= 0 else "🔴"
    rec_delta = f" ({'▲' if delta_rec >= 0 else '▼'}{abs(delta_rec):.0f}% vs anterior)"

    if FORMAT == "markdown":
        print(f"# 📑 Relatório Mensal — {m:02d}/{y}")
        print(f"\n_Gerado em {today.strftime('%d/%m/%Y')}_\n")
        headline = f"{'Positivo' if data['resultado'] >= 0 else 'Negativo'}: {fmt(data['resultado'])} no mês. Receita {fmt(rec_total)}{rec_delta}."
        print(f"**{headline}**\n")

        print(f"## 💰 Resultado")
        print(f"| | Valor | vs Anterior |")
        print(f"|---|---|---|")
        print(f"| Receita | {fmt(rec_total)} | {'▲' if delta_rec >= 0 else '▼'}{abs(delta_rec):.0f}% |")
        print(f"| Pagamentos | {fmt(pay_total)} | {'▲' if delta_pay >= 0 else '▼'}{abs(delta_pay):.0f}% |")
        print(f"| **Resultado** | **{fmt(data['resultado'])}** | {res_signal} |")

        print(f"\n## 📊 KPIs")
        print(f"- Caixa: {fmt(caixa)} | Runway: {runway:.1f} meses | Burn: {fmt(burn)}/mês")
        print(f"- DSO: {dso:.0f}d | DPO: {dpo:.0f}d")

        print(f"\n## ⚠️ Inadimplência")
        print(f"- Total vencido: {fmt(overdue_total)}")
        for b in (data["aging"] or {}).values():
            if isinstance(b, dict) and b.get("count", 0) > 0:
                print(f"  - {b}")

        print(f"\n## 📋 Top 3 Recomendações")
        for i, r in enumerate(recomendacoes, 1): print(f"{i}. {r}")
        return

    # text WA
    print(f"📑 Relatório {m:02d}/{y}")
    print(f"Receita: {fmt(rec_total)}{rec_delta}")
    print(f"Pagamentos: {fmt(pay_total)}")
    print(f"Resultado: {fmt(data['resultado'])} {res_signal}")
    print(f"Runway: {runway:.1f}m | Vencidos: {fmt(overdue_total)}")
    print(f"")
    for i, r in enumerate(recomendacoes, 1): print(f"{i}. {r}")


if __name__ == "__main__":
    main()
