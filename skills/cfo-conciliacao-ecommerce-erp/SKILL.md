---
name: cfo-conciliacao-ecommerce-erp
description: >
  Cruza vendas do e-commerce (Mercado Livre / Nuvemshop) com receitas lançadas
  no ERP. Detecta vendas concluídas sem nota fiscal correspondente no ERP.
category: CFO/Conciliação
metadata:
  { "openclaw": { "emoji": "🛒", "requires": { "bins": ["python3"] } } }
---

# CFO — Conciliação E-commerce ↔ ERP

## Quando usar

| Situação | Comando |
|---|---|
| "vendas do ML estão no Omie?" | `python3 $SKILL_DIR/scripts/cruzar.py --periodo 30` |
| Cron diário | `python3 $SKILL_DIR/scripts/cruzar.py --periodo 7 --format json` |

## Match logic

- Valor: diferença < 10% (para acomodar taxas ML/NS que são descontadas)
- Data: ±5 dias (NF pode ser emitida alguns dias depois)

## Ação recomendada

- Venda sem NF: "Venda #{id} no ML (R$X em DD/MM) sem NF correspondente no ERP. Emitir NF?"
