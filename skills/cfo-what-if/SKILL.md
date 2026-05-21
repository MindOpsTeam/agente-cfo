---
name: cfo-what-if
description: >
  Simulador "e se?" multi-variável. Marcos simula impacto de mudanças específicas
  (ex: "e se eu reduzir R$3k/mês em despesas?") comparando com cenário base
  mês-a-mês. Inclui simulação em varredura para encontrar o ponto ótimo.
category: CFO/Planejamento
metadata:
  { "openclaw": { "emoji": "🔬", "requires": { "bins": ["python3"] } } }
---

# CFO — Simulador "E se?"

## Quando usar

| Situação | Comando |
|---|---|
| "e se eu cortar R$3k/mês?" | `python3 $SKILL_DIR/scripts/simular.py --variaveis '{"despesa_mensal":-3000}' --horizonte 90` |
| "e se receita crescer 20%?" | `python3 $SKILL_DIR/scripts/simular.py --variaveis '{"receita_mensal_pct":20}'` |
| "qual o corte mínimo pra ter 6 meses de runway?" | `python3 $SKILL_DIR/scripts/multi_simular.py --variavel despesa_mensal --de -500 --ate -5000 --passo 500 --target runway_meses --valor 6` |

## Variáveis suportadas

| Variável | Tipo | Exemplo |
|----------|------|---------|
| `despesa_mensal` | R$ delta | `-3000` (corta R$3k/mês) |
| `receita_mensal` | R$ delta | `+5000` |
| `receita_mensal_pct` | % | `+20` |
| `inadimplencia_pct` | % absoluto | `5` (baixa de X% pra 5%) |
| `cobrar_inadimplentes` | bool | `true` (adiciona overdue ao caixa) |
| `antecipacao_recebivel_pct` | % | `30` (antecipa 30% dos recebíveis) |
