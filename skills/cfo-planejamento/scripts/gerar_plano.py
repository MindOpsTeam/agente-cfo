#!/usr/bin/env python3
"""
gerar_plano.py — Gera plano de ação com timeline, milestones e checkpoints.

Uso:
  python3 gerar_plano.py --objetivo reduzir_burn --horizonte 90
  python3 gerar_plano.py --objetivo aumentar_caixa --horizonte 60
  python3 gerar_plano.py --objetivo crescer --meta 20 --horizonte 180
  python3 gerar_plano.py --format json --objetivo reduzir_inadimplencia
  python3 gerar_plano.py --listar   # lista planos salvos
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
PLANOS_DIR = Path.home() / ".agente-cfo" / "memory" / "planos"
SNAPSHOT_PY = SCRIPTS_DIR / "snapshot_financeiro.py"

FORMAT = "text"
OBJETIVO = None
HORIZONTE = 90
META = None
LISTAR = False

i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a in ("--format",) and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--objetivo" and i + 1 < len(sys.argv): OBJETIVO = sys.argv[i + 1]; i += 2
    elif a == "--horizonte" and i + 1 < len(sys.argv): HORIZONTE = int(sys.argv[i + 1]); i += 2
    elif a == "--meta" and i + 1 < len(sys.argv): META = float(sys.argv[i + 1]); i += 2
    elif a == "--listar": LISTAR = True; i += 1
    else: i += 1

# ── Playbooks por objetivo ────────────────────────────────────────────────────

PLAYBOOKS: dict[str, dict] = {
    "reduzir_burn": {
        "descricao": "Reduzir despesas operacionais e burn rate",
        "kpis": ["burn_mensal", "runway_meses"],
        "milestones_template": [
            (1, "Mapear todos os gastos recorrentes e assinaturas", "R$500-2.000/mês", "dono"),
            (2, "Listar top 5 fornecedores por valor e contatar pra renegociar prazo/desconto", "R$1.000-5.000/mês", "dono"),
            (3, "Cortar contratos desnecessários (cancelar serviços sem uso)", "R$200-1.000/mês", "dono"),
            (4, "Revisar folha: horas extras, benefícios, terceiros", "variável", "dono/RH"),
            (6, "Reavaliar burn: comparar com baseline", "ver delta", "Marcos"),
            (8, "Ajuste fino: categorias que ainda excedem orçamento", "residual", "dono"),
        ],
        "riscos": [
            "Fornecedor recusa renegociar → buscar alternativa",
            "Corte afeta qualidade do produto/serviço → balancear com dono",
        ],
    },
    "aumentar_caixa": {
        "descricao": "Aumentar saldo de caixa disponível",
        "kpis": ["balance", "runway_meses"],
        "milestones_template": [
            (1, "Acionar cobrança de todos os vencidos há mais de 7 dias (cfo-inadimplencia)", "imediato", "Marcos"),
            (1, "Negociar antecipação de 20% dos recebíveis com clientes-chave", "variável", "dono"),
            (2, "Revisar prazos de pagamento: postergar vencimentos negociáveis", "libera caixa", "dono"),
            (3, "Verificar crédito bancário de curto prazo como hedge (não usar se não precisar)", "emergência", "dono"),
            (4, "Criar reserva de emergência: separar 30 dias de burn em conta separada", "meta", "dono"),
            (6, "Avaliar caixa vs meta — ajustar se necessário", "checkpoint", "Marcos"),
        ],
        "riscos": [
            "Antecipação de recebíveis tem custo (desconto) → só se runway < 3 meses",
            "Cliente principal não paga → concentração de risco",
        ],
    },
    "reduzir_inadimplencia": {
        "descricao": "Reduzir percentual de inadimplência sobre receivables",
        "kpis": ["inadimplencia_pct", "total_overdue"],
        "milestones_template": [
            (1, "Rodar aging (cfo-inadimplencia) e classificar: 0-30d, 31-60d, >60d", "diagnóstico", "Marcos"),
            (1, "Contatar todos os 0-30d com lembrete amigável", "R$ imediato", "Marcos/Asaas"),
            (2, "Emitir boleto novo para 31-60d com desconto pontualidade", "R$ médio", "dono+Marcos"),
            (3, "Escalation para >60d: avisar sobre encaminhamento jurídico preventivo", "R$ difícil", "dono"),
            (4, "Implantar cobrança automática pré-vencimento (D-3, D-1)", "preventivo", "Marcos/Asaas"),
            (6, "Medir inadimplência: meta < 8% das receivables", "checkpoint", "Marcos"),
            (8, "Revisar política de crédito para novos clientes", "preventivo longo", "dono"),
        ],
        "riscos": [
            "Cliente >60d pode ir a perdas → provisionar contabilmente",
            "Cobrança agressiva pode prejudicar relacionamento → calibrar tom",
        ],
    },
    "crescer": {
        "descricao": f"Crescimento de receita em {META or 20:.0f}% no horizonte",
        "kpis": ["total_receivables_mes", "burn_mensal"],
        "milestones_template": [
            (1, "Mapear funil atual: quantos leads → proposta → fechamento por mês", "diagnóstico", "dono+CRM"),
            (2, "Identificar a maior alavanca: ticket, volume ou conversão", "diagnóstico", "Marcos"),
            (3, "Calcular CAC (Custo de Aquisição) estimado e LTV mínimo viável", "diagnóstico", "Marcos"),
            (4, "Garantir capital de giro suficiente pra suportar crescimento (Marcos valida)", "validação", "Marcos"),
            (6, "Lançar iniciativa de crescimento (canal/produto/preço a escolher do dono)", "execução", "dono"),
            (8, "Primeira medição: receita cresceu X% pra meta de {meta_pct}%?", "checkpoint", "Marcos"),
            (12, "Ajuste de rota se abaixo de 50% da meta de crescimento", "correção", "dono+Marcos"),
        ],
        "riscos": [
            f"Crescimento acima de runway atual → travar capital de giro",
            "CAC maior que previsto → crescimento pode consumir margem",
        ],
    },
    "equilibrar": {
        "descricao": "Atingir break-even e construir reserva de 30 dias",
        "kpis": ["burn_mensal", "runway_meses", "inadimplencia_pct"],
        "milestones_template": [
            (1, "Calcular ponto de equilíbrio atual (cfo-projecao ponto_equilibrio.py)", "diagnóstico", "Marcos"),
            (2, "Identificar gap: quanto falta em receita OU quanto cortar em despesa", "meta", "Marcos"),
            (3, "Executar corte de burn (ver plano reduzir_burn em paralelo)", "execução", "dono"),
            (4, "Cobrança ativa de inadimplentes (mínimo +10% de caixa)", "execução", "Marcos"),
            (6, "Verificar se atingiu break-even: receita ≥ burn mensal", "checkpoint", "Marcos"),
            (8, "Com break-even atingido: acumular reserva de 30 dias (1x burn)", "meta", "dono"),
        ],
        "riscos": [
            "Break-even depende de receita crescer E burn cair simultaneamente",
            "Sazonalidade pode atrasar o break-even em 1-2 meses",
        ],
    },
}


def run_snapshot() -> dict:
    if not SNAPSHOT_PY.exists():
        return {}
    r = subprocess.run(
        ["python3", str(SNAPSHOT_PY), "--get"],
        capture_output=True, text=True, timeout=10,
    )
    try:
        d = json.loads(r.stdout) if r.stdout.strip() else {}
        return d
    except Exception:
        return {}


def fmt(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def list_planos():
    PLANOS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(PLANOS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    planos = []
    for f in files[:10]:
        try:
            d = json.loads(f.read_text())
            planos.append({"nome": f.stem, "objetivo": d.get("objetivo"), "horizonte": d.get("horizonte_dias"),
                           "gerado_em": d.get("gerado_em", "?")[:10]})
        except Exception:
            pass
    return planos


def main():
    if LISTAR:
        planos = list_planos()
        if FORMAT == "json":
            print(json.dumps(planos, ensure_ascii=False))
        else:
            if not planos:
                print("Nenhum plano salvo.")
            else:
                print("📋 Planos salvos:")
                for p in planos:
                    print(f"  • [{p['gerado_em']}] {p['objetivo']} ({p['horizonte']}d) — {p['nome']}")
        return

    if not OBJETIVO:
        print(json.dumps({"error": "Informe --objetivo (reduzir_burn|aumentar_caixa|reduzir_inadimplencia|crescer|equilibrar)"}))
        return

    obj = OBJETIVO.lower()
    if obj not in PLAYBOOKS:
        # Fallback genérico
        obj = "equilibrar"

    playbook = PLAYBOOKS[obj]
    snap = run_snapshot()
    today = date.today()
    horizonte_semanas = max(HORIZONTE // 7, 4)

    # Metas numéricas baseadas no snapshot
    balance = float(snap.get("balance") or 0)
    burn = float(snap.get("burn_mensal_estimado") or 0)
    runway = float(snap.get("runway_meses") or 0)
    inad = float(snap.get("inadimplencia_pct") or 0)
    overdue = float(snap.get("total_overdue") or 0)

    meta_txt = ""
    if obj == "reduzir_burn" and burn > 0:
        target = burn * 0.80
        meta_txt = f"Reduzir burn de {fmt(burn)}/mês para {fmt(target)}/mês (-20%)"
    elif obj == "aumentar_caixa" and burn > 0:
        target = balance + burn * (HORIZONTE / 30)
        meta_txt = f"Saldo de {fmt(balance)} → {fmt(target)} (+{HORIZONTE}d de burn coberto)"
    elif obj == "reduzir_inadimplencia":
        meta_txt = f"Inadimplência de {inad:.0f}% → abaixo de 8% (recuperar {fmt(overdue)})"
    elif obj == "crescer":
        pct = META or 20
        meta_txt = f"Crescimento de {pct:.0f}% na receita em {HORIZONTE} dias"
    elif obj == "equilibrar":
        meta_txt = f"Atingir break-even e 30 dias de reserva (= {fmt(burn)}) em {HORIZONTE} dias"

    # Monta milestones dentro do horizonte
    milestones = []
    semanas = horizonte_semanas
    for week, acao, impacto, owner in playbook["milestones_template"]:
        if week > semanas:
            break
        # Formata acao com valores reais
        acao_fmt = acao.replace("{meta_pct}", f"{META or 20:.0f}%")
        milestone_date = (today + timedelta(weeks=week)).isoformat()
        milestones.append({
            "semana": week,
            "data_alvo": milestone_date,
            "acao": acao_fmt,
            "impacto_estimado": impacto,
            "responsavel": owner,
        })

    # Checkpoints
    checkpoints = []
    for pct in [0.33, 0.67, 1.0]:
        days = int(HORIZONTE * pct)
        checkpoints.append({
            "dia": days,
            "data": (today + timedelta(days=days)).isoformat(),
            "acao": f"Revisar KPIs: {', '.join(playbook['kpis'])}",
        })

    plano = {
        "objetivo": obj,
        "horizonte_dias": HORIZONTE,
        "horizonte_semanas": horizonte_semanas,
        "descricao": playbook["descricao"],
        "meta_numerica": meta_txt or f"Melhorar {obj} em {HORIZONTE} dias",
        "estado_atual": {"balance": balance, "burn": burn, "runway": runway,
                         "inadimplencia_pct": inad} if snap else {},
        "milestones": milestones,
        "kpis_acompanhar": playbook["kpis"],
        "riscos": playbook["riscos"],
        "checkpoints": checkpoints,
        "gerado_em": today.isoformat(),
        "dados_suficientes": bool(snap and balance > 0),
    }

    # Salva
    PLANOS_DIR.mkdir(parents=True, exist_ok=True)
    nome_arquivo = f"{obj}-{today.isoformat()}"
    (PLANOS_DIR / f"{nome_arquivo}.json").write_text(
        json.dumps(plano, indent=2, ensure_ascii=False)
    )

    if FORMAT == "json":
        print(json.dumps(plano, ensure_ascii=False))
        return

    # Output texto
    if not plano["dados_suficientes"]:
        print(f"⚠️ Dados ERP insuficientes para plan personalizado. Mostrando playbook genérico.")

    print(f"🗓️ Plano: {plano['descricao']}")
    print(f"   Meta: {plano['meta_numerica']}")
    print(f"   Horizonte: {HORIZONTE} dias ({horizonte_semanas} semanas)\n")
    print("📍 Milestones:")
    for m in milestones[:6]:
        print(f"  Sem.{m['semana']:2d} ({m['data_alvo'][5:]}) — {m['acao'][:60]}")
        if m['impacto_estimado'] not in ("diagnóstico", "checkpoint", "meta", "execução", "variável"):
            print(f"           Impacto: {m['impacto_estimado']} | Owner: {m['responsavel']}")
    print(f"\n📊 KPIs a monitorar: {', '.join(playbook['kpis'])}")
    print("\n⚠️ Riscos:")
    for r in playbook["riscos"]:
        print(f"  • {r}")
    cp_str = " | ".join("Dia " + str(c["dia"]) for c in checkpoints)
    print(f"\n🔁 Checkpoints: {cp_str}")


if __name__ == "__main__":
    main()
