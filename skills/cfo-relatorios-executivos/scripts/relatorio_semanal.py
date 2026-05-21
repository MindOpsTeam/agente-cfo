#!/usr/bin/env python3
"""
relatorio_semanal.py — Relatório executivo semanal do CFO.

Uso:
  python3 relatorio_semanal.py
  python3 relatorio_semanal.py --format markdown   # markdown completo pra painel
  python3 relatorio_semanal.py --format text        # WA-friendly (fragmentado)
  python3 relatorio_semanal.py --format json
"""
import json
import math
import subprocess
import sys
from datetime import date, timedelta
from collections import defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
CFO_SKILLS = Path(__file__).parent.parent.parent
FORMAT = sys.argv[sys.argv.index("--format") + 1] if "--format" in sys.argv else "text"


def run(script_rel: str, cmd: list[str]) -> dict:
    script = SCRIPTS_DIR / script_rel
    if not script.exists(): return {"error": f"{script_rel} não encontrado"}
    r = subprocess.run(["python3", str(script)] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def run_skill(skill: str, script: str, cmd: list[str]) -> dict:
    p = CFO_SKILLS / skill / "scripts" / script
    if not p.exists(): return {"error": f"{skill}/{script} não encontrado"}
    r = subprocess.run(["python3", str(p)] + cmd + ["--format", "json"],
                       capture_output=True, text=True, timeout=30)
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")


def main():
    today = date.today()
    semana_ini = (today - timedelta(days=today.weekday() + 7)).isoformat()
    semana_fim = (today - timedelta(days=today.weekday() + 1)).isoformat()
    mes_ini = today.replace(day=1).isoformat()

    # Coleta dados
    bal = run("erp_gateway.py", ["get_balance"])
    rec_sem = run("erp_gateway.py", ["list_receivables", "--from", semana_ini, "--to", semana_fim, "--limit", "200"])
    pay_sem = run("erp_gateway.py", ["list_payables", "--from", semana_ini, "--to", semana_fim, "--limit", "200"])
    overdue = run("erp_gateway.py", ["list_overdue"])

    def sum_r(r):
        lst = r.get("records") or r.get("items") or r.get("data") or []
        if not isinstance(lst, list): return 0.0
        return sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0) for x in lst if isinstance(x, dict))

    caixa = float(bal.get("balance") or bal.get("saldo") or bal.get("saldo_total") or 0)
    rec_total = sum_r(rec_sem)
    pay_total = sum_r(pay_sem)
    overdue_total = sum_r(overdue)
    overdue_count = len(overdue.get("records") or overdue.get("items") or overdue.get("data") or [])

    # KPIs via skill
    kpis = run_skill("cfo-analise-estrategica", "kpis.py", [])
    runway = float(kpis.get("runway_meses") or 0)
    burn = float(kpis.get("burn_mensal_estimado") or 0)

    # Anomalias
    anomalias = run_skill("cfo-anomalias", "zscore.py", [])
    zscore = float(anomalias.get("zscore") or 0)
    has_anomaly = anomalias.get("anomalia", False)

    # Top inadimplentes
    top_dev = run_skill("cfo-inadimplencia", "top_devedores.py", ["--n", "3"])
    top_lista = top_dev.get("clientes") or []

    # Gera recomendações automáticas
    recomendacoes = []
    if runway < 3:
        recomendacoes.append(f"🔴 URGENTE: Runway de {runway:.1f} meses — revisar custos e antecipar recebíveis esta semana.")
    if overdue_total > 0:
        pct_inad = (overdue_total / max(rec_total + overdue_total, 1)) * 100
        if pct_inad > 15:
            recomendacoes.append(f"🟠 Inadimplência em {pct_inad:.0f}% — executar cobrança dos {overdue_count} vencidos ({fmt(overdue_total)}).")
    if has_anomaly:
        recomendacoes.append(f"🟡 Anomalia de despesas (z={zscore:.1f}σ) — verificar qual categoria está crescendo.")
    if not recomendacoes:
        recomendacoes.append(f"🟢 Semana sem alertas críticos. Manter acompanhamento semanal.")
    recomendacoes = recomendacoes[:3]

    data = {
        "periodo": f"Semana {semana_ini} a {semana_fim}",
        "gerado_em": today.isoformat(),
        "caixa": caixa,
        "recebimentos_semana": rec_total,
        "pagamentos_semana": pay_total,
        "saldo_semana": rec_total - pay_total,
        "overdue_total": overdue_total,
        "overdue_count": overdue_count,
        "runway_meses": runway,
        "burn_mensal": burn,
        "anomalia": has_anomaly,
        "zscore": zscore,
        "top_devedores": top_lista,
        "recomendacoes": recomendacoes,
    }

    if FORMAT == "json":
        print(json.dumps(data, ensure_ascii=False)); return

    saldo_sem_signal = "▲" if data["saldo_semana"] >= 0 else "▼"
    runway_signal = "🔴" if runway < 2 else ("🟡" if runway < 4 else "🟢")

    if FORMAT == "markdown":
        print(f"# 📊 Relatório Semanal — {today.strftime('%d/%m/%Y')}")
        print(f"\n**Período:** {semana_ini} a {semana_fim}\n")
        print(f"## 💰 Snapshot")
        print(f"- Caixa: **{fmt(caixa)}**")
        print(f"- Runway: **{runway:.1f} meses** {runway_signal} (burn {fmt(burn)}/mês)")
        print(f"- Semana: +{fmt(rec_total)} receitas | -{fmt(pay_total)} pagamentos | saldo {saldo_sem_signal}{fmt(abs(data['saldo_semana']))}")
        print(f"\n## ⚠️ Inadimplência")
        print(f"- Total vencido: **{fmt(overdue_total)}** ({overdue_count} registros)")
        if top_lista:
            for c in top_lista[:3]:
                print(f"  - {c['nome']}: {fmt(c['valor'])} ({c['pct']}%)")
        print(f"\n## 🔍 Anomalias")
        if has_anomaly: print(f"- ⚠️ Z-score {zscore:.1f}σ — despesas acima do padrão histórico")
        else: print(f"- ✅ Despesas dentro do padrão histórico")
        print(f"\n## 📋 Recomendações")
        for i, r in enumerate(recomendacoes, 1): print(f"{i}. {r}")
        return

    # text (WA-friendly, ~600 chars)
    print(f"📊 Relatório Semanal — {today.strftime('%d/%m/%Y')}")
    print(f"")
    print(f"Caixa: {fmt(caixa)} | Runway: {runway:.1f}m {runway_signal}")
    print(f"Semana: +{fmt(rec_total)} / -{fmt(pay_total)} = {saldo_sem_signal}{fmt(abs(data['saldo_semana']))}")
    if overdue_total > 0:
        print(f"Vencidos: {fmt(overdue_total)} ({overdue_count} registros)")
    print(f"")
    print(f"Recomendações:")
    for i, r in enumerate(recomendacoes, 1): print(f"{i}. {r}")


if __name__ == "__main__":
    main()
