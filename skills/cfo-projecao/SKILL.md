---
name: cfo-projecao
description: >
  Projeções de fluxo de caixa multi-cenário (otimista/realista/pessimista),
  runway, burn rate e ponto de equilíbrio. Marcos usa para responder
  "quantos meses ainda temos?" e "qual a receita mínima pra cobrir os custos?".
category: CFO/Projeção
metadata:
  { "openclaw": { "emoji": "🔮", "requires": { "bins": ["python3"] } } }
---

# CFO — Projeção Financeira

## Quando usar

| Situação | Comando |
|---|---|
| "quanto tempo até zerar o caixa?" | `python3 $SKILL_DIR/scripts/runway.py` |
| "projeção pros próximos 90 dias" | `python3 $SKILL_DIR/scripts/cenario.py --periodo 90` |
| "quanto estou queimando por mês?" | `python3 $SKILL_DIR/scripts/burn.py` |
| "qual receita mínima pra não fechar?" | `python3 $SKILL_DIR/scripts/ponto_equilibrio.py` |

## Cenários

| Cenário | Premissa |
|---------|----------|
| **Otimista** | Recebimento 90% do previsto, inadimplência 5%, custos estáveis |
| **Realista** | Recebimento 75%, inadimplência 12%, custos +3% |
| **Pessimista** | Recebimento 55%, inadimplência 25%, custos +8% |

## Uso correto

Marcos apresenta os 3 cenários lado a lado e diz em qual a empresa está operando hoje.
Nunca apresenta projeção como certeza — sempre "no cenário X, com os dados atuais...".
