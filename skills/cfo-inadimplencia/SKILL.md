---
name: cfo-inadimplencia
description: >
  Análise profunda de inadimplência: aging (bucket 0-30/31-60/61-90/>90d),
  concentração de devedores, scoring de risco e sugestão de ação de cobrança
  por bucket. Marcos usa para identificar quem cobrar, como e com qual urgência.
category: CFO/Inadimplência
metadata:
  { "openclaw": { "emoji": "⚠️", "requires": { "bins": ["python3"] } } }
---

# CFO — Inadimplência

## Quando usar

| Situação | Comando |
|---|---|
| "quem está devendo?", "inadimplentes" | `python3 $SKILL_DIR/scripts/aging.py` |
| "top devedores", "maiores atrasados" | `python3 $SKILL_DIR/scripts/top_devedores.py` |
| "como devo cobrar cada um?" | `python3 $SKILL_DIR/scripts/sugestao_cobranca.py` |

## Regras de Aging (padrão BR)

| Bucket | Dias | Ação sugerida |
|--------|------|---------------|
| 0–7 | Recente | Lembrete amigável |
| 8–30 | Atrasado | 1ª notificação formal |
| 31–60 | Vencido | Boleto novo + contato direto |
| 61–90 | Crítico | Escalation + jurídico preventivo |
| >90 | Irrecuperável | Provisionamento + medida judicial |

## Interpretação

- Inadimplência > 15% do faturamento = fogo na sala
- Concentração: 1 cliente > 30% da inadimplência = risco de concentração
- Aging > 60 dias: probabilidade de recuperação cai abaixo de 50%
