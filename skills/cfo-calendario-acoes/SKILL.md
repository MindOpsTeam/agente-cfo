---
name: cfo-calendario-acoes
description: >
  Calendário acionável que combina obrigações fiscais, recebimentos a vencer,
  pagamentos e relatórios em uma única lista cronológica com ação recomendada
  por item. "O que devo fazer esta semana, Marcos?"
category: CFO/Planejamento
metadata:
  { "openclaw": { "emoji": "📅", "requires": { "bins": ["python3"] } } }
---

# CFO — Calendário de Ações

## Quando usar

| Situação | Comando |
|---|---|
| "o que acontece essa semana?" | `python3 $SKILL_DIR/scripts/proximos_eventos.py --dias 7` |
| "e no mês?" | `python3 $SKILL_DIR/scripts/proximos_eventos.py --dias 30` |
| "só os fiscais" | `python3 $SKILL_DIR/scripts/proximos_eventos.py --tipos fiscal --dias 30` |

## Tipos de eventos

| Tipo | O que inclui |
|------|-------------|
| `fiscal` | DAS, FGTS, IRPJ, IRRF, 13º (via cfo-tributacao-br) |
| `cobranca` | Recebíveis a vencer (ação: cobrar em D-3) |
| `pagamento` | Payables a vencer (ação: verificar caixa) |
| `relatorio` | Relatório semanal sex 16h, mensal dia 1 08h |
| `all` | Todos os tipos (default) |
