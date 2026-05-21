---
name: cfo-conciliacao-crm-erp
description: >
  Cruza Deals "Won" no CRM (HubSpot/Pipedrive/etc) com receitas lançadas no ERP.
  Detecta negócios fechados que ainda não converteram em receita registrada.
  Marcos usa para garantir que cada deal ganho virou fatura.
category: CFO/Conciliação
metadata:
  { "openclaw": { "emoji": "🤝", "requires": { "bins": ["python3"] } } }
---

# CFO — Conciliação CRM ↔ ERP

## Quando usar

| Situação | Comando |
|---|---|
| "deals fechados viraram receita?" | `python3 $SKILL_DIR/scripts/cruzar.py --periodo 60` |
| Cron diário | `python3 $SKILL_DIR/scripts/cruzar.py --periodo 7 --format json` |

## Match logic

Para cada Deal Won: procura receita no ERP com:
- Valor próximo (±20% — deal pode ser parcelado ou ter desconto)
- Data de fechamento ≤ data da receita ≤ data de fechamento + 30 dias
- (opcional) Nome cliente fuzzy

## Ação quando sem match

"Deal '{titulo}' fechado em {data} por {valor} mas sem receita no ERP nos 30 dias seguintes.
O cliente pagou? Se sim, criar recebível agora?"
