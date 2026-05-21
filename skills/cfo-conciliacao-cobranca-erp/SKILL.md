---
name: cfo-conciliacao-cobranca-erp
description: >
  Cruza pagamentos confirmados na plataforma de cobrança (Asaas/Iugu) com
  recebimentos lançados no ERP (Omie/Bling/etc). Identifica divergências:
  pago no Asaas mas não no ERP; recebido no ERP sem correspondência na cobrança.
  Marcos usa para garantir que nenhum recebimento cai no vazio.
category: CFO/Conciliação
metadata:
  { "openclaw": { "emoji": "🔀", "requires": { "bins": ["python3"] } } }
---

# CFO — Conciliação Cobrança ↔ ERP

## Quando usar

| Situação | Comando |
|---|---|
| "tem divergência entre Asaas e Omie?" | `python3 $SKILL_DIR/scripts/cruzar.py --periodo 30` |
| Cron diário 06:30 | `python3 $SKILL_DIR/scripts/cruzar.py --periodo 7 --format json` |
| Após confirmar pagamento no Asaas | imediatamente |

## Match logic

Um pagamento Asaas e um recebimento ERP são considerados **correspondentes** quando:
- Valor: diferença < 2% (para acomodar taxas) ou diferença absoluta < R$5
- Data: mesma data ±3 dias
- (opcional) Nome do cliente: fuzzy match ≥ 80% de similaridade

## Saída

```json
{
  "periodo_dias": 30,
  "match_ok": [...],
  "pago_so_cobranca": [...],   // ← Asaas pagou mas ERP não registrou
  "recebido_so_erp": [...]     // ← ERP tem recebimento sem boleto correspondente
}
```

## Ação recomendada por divergência

- `pago_so_cobranca`: lançar manualmente no ERP (Marcos propõe `create_receivable`)
- `recebido_so_erp`: verificar se boleto foi cancelado / pagamento direto
