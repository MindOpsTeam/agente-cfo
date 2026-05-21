---
name: cfo-decisao-estrategica
description: >
  Recomendações estratégicas com 2-3 alternativas, tradeoffs explícitos,
  premissas, riscos e score de recomendação. Marcos usa para responder
  "devo crescer ou consolidar?" com dados reais e opinião formada.
category: CFO/Planejamento
metadata:
  { "openclaw": { "emoji": "⚖️", "requires": { "bins": ["python3"] } } }
---

# CFO — Decisão Estratégica

## Quando usar

| Situação | Comando |
|---|---|
| "devo crescer agora ou consolidar?" | `python3 $SKILL_DIR/scripts/avaliar.py --questao crescer_vs_consolidar` |
| "vale investir em marketing?" | `python3 $SKILL_DIR/scripts/avaliar.py --questao investir_vs_economizar` |
| "devo contratar ou esperar?" | `python3 $SKILL_DIR/scripts/avaliar.py --questao contratar_vs_esperar` |

## Questões suportadas

| Questão | O que avalia |
|---------|-------------|
| `crescer_vs_consolidar` | Runway atual vs oportunidade de crescimento |
| `investir_vs_economizar` | ROI estimado vs pressão de caixa |
| `contratar_vs_esperar` | Capacidade operacional vs custo fixo |
| `antecipar_cobranca` | Custo do desconto vs necessidade de caixa imediato |
| `expandir_canal` | Diversificação de receita vs complexidade operacional |

## Formato de resposta

Marcos NUNCA dá uma única resposta. Sempre 2-3 alternativas com:
- Prós e contras
- Premissa necessária (o que precisa ser verdade)
- Nível de risco
- Score de recomendação (1-10)
- `marcos_pick`: a recomendação explícita do Marcos baseada nos dados

## Guardrail

"Decisão é sua. Trago os dados e minha sugestão. Ação final é responsabilidade do dono."
