#!/usr/bin/env python3
"""
avaliar.py — Avaliação estratégica com alternativas, tradeoffs e recomendação.

Uso:
  python3 avaliar.py --questao crescer_vs_consolidar
  python3 avaliar.py --questao investir_vs_economizar --contexto auto
  python3 avaliar.py --format json --questao crescer_vs_consolidar
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
SNAPSHOT_PY = SCRIPTS_DIR / "snapshot_financeiro.py"

FORMAT = "text"
QUESTAO = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--questao" and i + 1 < len(sys.argv): QUESTAO = sys.argv[i + 1]; i += 2
    elif a in ("--contexto",) and i + 1 < len(sys.argv): i += 2  # auto = default
    else: i += 1


def get_snap() -> dict:
    if not SNAPSHOT_PY.exists(): return {}
    r = subprocess.run(["python3", str(SNAPSHOT_PY), "--get"],
                       capture_output=True, text=True, timeout=10)
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def fmt(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def avaliar_crescer_vs_consolidar(snap: dict) -> dict:
    runway = float(snap.get("runway_meses") or 0)
    burn = float(snap.get("burn_mensal_estimado") or 0)
    inad = float(snap.get("inadimplencia_pct") or 0)
    balance = float(snap.get("balance") or 0)

    # Score dinâmico baseado nos dados
    crescer_score = 5  # base
    consolidar_score = 5

    if runway >= 9: crescer_score += 2
    elif runway >= 6: crescer_score += 1
    elif runway < 3: crescer_score -= 3; consolidar_score += 2

    if inad > 15: crescer_score -= 1; consolidar_score += 1
    if inad < 5: crescer_score += 1

    crescer_score = max(1, min(10, crescer_score))
    consolidar_score = max(1, min(10, consolidar_score))

    marcos_pick = ""
    if runway < 4:
        marcos_pick = f"Consolidar — runway de {runway:.1f} meses está abaixo do mínimo de 6 que considero seguro para crescimento em PME. Corrija o caixa primeiro."
    elif runway >= 8 and inad < 10:
        marcos_pick = f"Crescer — runway de {runway:.1f} meses e inadimplência de {inad:.0f}% dão espaço. Use os próximos 3 meses pra validar canal antes de escalar."
    else:
        marcos_pick = f"Crescimento gradual — runway de {runway:.1f}m é ok mas não confortável. Cresça sem aumentar burn mais que 15% por mês."

    return {
        "questao": "Crescer agora vs Consolidar",
        "contexto": {"runway_meses": runway, "inadimplencia_pct": inad, "balance": balance},
        "alternativas": [
            {
                "titulo": "Crescer (agressivo)",
                "pros": ["Captura demanda antes do concorrente", "Diluição de custos fixos", "Momentum"],
                "contras": ["Queima caixa mais rápido", "Risco de capital de giro", "Estresse operacional"],
                "premissa": f"Receita crescer ≥20% sem burn subir mais de 15%. Runway atual: {runway:.1f}m.",
                "risco": "alto" if runway < 6 else "médio",
                "recomendacao_score": crescer_score,
            },
            {
                "titulo": "Consolidar (cautela)",
                "pros": ["Melhora margem", "Reduz inadimplência", "Fortalece base operacional"],
                "contras": ["Concorrente pode avançar", "Crescimento mais lento", "Time pode desmotivar"],
                "premissa": "Burn estável ou caindo. Focar em eficiência antes de expansão.",
                "risco": "baixo",
                "recomendacao_score": consolidar_score,
            },
            {
                "titulo": "Crescimento gradual (meio-termo)",
                "pros": ["Controla risco", "Aprende antes de escalar", "Mantém momentum"],
                "contras": ["Mais devagar que o mercado", "Complexidade de gestão bifurcada"],
                "premissa": f"Aumentar receita 10-15%/mês sem aumentar burn fixo. Investir só em receita comprovada.",
                "risco": "médio-baixo",
                "recomendacao_score": min(crescer_score + 1, consolidar_score + 1),
            },
        ],
        "marcos_pick": marcos_pick,
        "checkpoints": [
            {"dia": 30, "data": (date.today() + timedelta(days=30)).isoformat(),
             "acao": "Revisar: receita cresceu X%? Burn subiu?"},
            {"dia": 60, "data": (date.today() + timedelta(days=60)).isoformat(),
             "acao": "Rever estratégia se crescimento < 50% da meta"},
        ],
    }


def avaliar_investir_vs_economizar(snap: dict) -> dict:
    runway = float(snap.get("runway_meses") or 0)
    burn = float(snap.get("burn_mensal_estimado") or 0)
    balance = float(snap.get("balance") or 0)

    inv_score = 4 if runway < 4 else (7 if runway >= 8 else 6)
    eco_score = 8 if runway < 4 else (5 if runway >= 8 else 7)

    if runway < 3:
        pick = f"Economizar — com {runway:.1f} meses de runway, qualquer investimento não-essencial é risco existencial."
    elif runway >= 9:
        pick = f"Investir — {runway:.1f} meses de runway dá espaço. Priorize investimentos com ROI ≤ 6 meses."
    else:
        pick = f"Economizar até runway ≥ 6 meses, depois investir com critério. Corte primeiro, cresça depois."

    return {
        "questao": "Investir agora vs Economizar",
        "contexto": {"runway_meses": runway, "balance": balance},
        "alternativas": [
            {
                "titulo": "Investir agora",
                "pros": ["Acelera crescimento", "Pode capturar janela de mercado"],
                "contras": ["Aumenta burn", f"Runway cai de {runway:.1f} para ~{max(0, runway-2):.1f} meses"],
                "premissa": "ROI < 6 meses. Receita extra ≥ 1.5x custo do investimento.",
                "risco": "alto" if runway < 6 else "médio",
                "recomendacao_score": inv_score,
            },
            {
                "titulo": "Economizar agora",
                "pros": ["Aumenta runway", "Melhora margem", "Reduz risco"],
                "contras": ["Pode perder janela de mercado", "Time desanimado com restrições"],
                "premissa": "Foco em cortes não-essenciais. Manter investimentos com ROI provado.",
                "risco": "baixo",
                "recomendacao_score": eco_score,
            },
        ],
        "marcos_pick": pick,
        "checkpoints": [
            {"dia": 30, "data": (date.today() + timedelta(days=30)).isoformat(), "acao": "Reavaliar runway — meta ≥ 6 meses"}
        ],
    }


QUESTOES = {
    "crescer_vs_consolidar": avaliar_crescer_vs_consolidar,
    "crescer": avaliar_crescer_vs_consolidar,
    "consolidar": avaliar_crescer_vs_consolidar,
    "investir_vs_economizar": avaliar_investir_vs_economizar,
    "investir": avaliar_investir_vs_economizar,
}


def main():
    if not QUESTAO:
        questoes = list(QUESTOES.keys())
        print(json.dumps({"error": f"Informe --questao. Opções: {questoes}"}) if FORMAT == "json"
              else "Uso: python3 avaliar.py --questao <" + "|".join(questoes) + ">")
        return

    q = QUESTAO.lower().replace(" ", "_")
    fn = QUESTOES.get(q)
    if not fn:
        # Fallback para crescer_vs_consolidar
        fn = avaliar_crescer_vs_consolidar

    snap = get_snap()
    result = fn(snap)

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
        return

    # Texto
    print(f"⚖️ Decisão Estratégica: {result['questao']}")
    ctx = result.get("contexto", {})
    if ctx:
        ctx_parts = [f"Runway: {ctx.get('runway_meses',0):.1f}m",
                     f"Inadimplência: {ctx.get('inadimplencia_pct',0):.0f}%" if ctx.get('inadimplencia_pct') else "",
                     f"Caixa: {fmt(ctx.get('balance',0))}" if ctx.get('balance') else ""]
        print(f"   Contexto: {' | '.join(p for p in ctx_parts if p)}\n")

    for i, alt in enumerate(result.get("alternativas", []), 1):
        risk_emoji = {"alto": "🔴", "médio": "🟡", "médio-baixo": "🟡", "baixo": "🟢"}.get(alt["risco"], "⚪")
        print(f"  {i}. {alt['titulo']} (score: {alt['recomendacao_score']}/10 | risco: {risk_emoji})")
        print(f"     Prós: {', '.join(alt['pros'][:2])}")
        print(f"     Contras: {', '.join(alt['contras'][:2])}")
        print(f"     Premissa: {alt['premissa'][:80]}")
        print()

    print(f"  💡 Minha sugestão: {result['marcos_pick']}")
    print(f"\n  ⚡ Decisão final é do dono. Trago dados e perspectiva — não assino pelo dono.")

    if result.get("checkpoints"):
        cps = result["checkpoints"]
        cp_str = " → ".join("Dia " + str(c["dia"]) for c in cps)
        print(f"\n  🔁 Checkpoints: {cp_str}")


if __name__ == "__main__":
    main()
