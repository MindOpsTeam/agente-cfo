---
name: cfo-planejamento
description: >
  Gera planos de ação com timeline acionável para objetivos financeiros
  (reduzir burn, aumentar caixa, reduzir inadimplência, crescer X%).
  Marcos usa para transformar "quero melhorar as finanças" em ações
  semanais concretas com milestones, KPIs e checkpoints.
category: CFO/Planejamento
metadata:
  { "openclaw": { "emoji": "🗓️", "requires": { "bins": ["python3"] } } }
---

# CFO — Planejamento de Ações

## Quando usar

| Situação | Comando |
|---|---|
| "como posso reduzir o burn?" | `python3 $SKILL_DIR/scripts/gerar_plano.py --objetivo reduzir_burn --horizonte 90` |
| "quero aumentar caixa em 3 meses" | `python3 $SKILL_DIR/scripts/gerar_plano.py --objetivo aumentar_caixa --horizonte 90` |
| "diminuir inadimplência" | `python3 $SKILL_DIR/scripts/gerar_plano.py --objetivo reduzir_inadimplencia --horizonte 60` |
| "crescer 20% nos próximos 6 meses" | `python3 $SKILL_DIR/scripts/gerar_plano.py --objetivo crescer --meta 20 --horizonte 180` |

## Objetivos suportados

| Objetivo | O que planeja |
|----------|--------------|
| `reduzir_burn` | Cortes + renegociações de fornecedores |
| `aumentar_caixa` | Antecipação de recebíveis + cobrança ativa |
| `reduzir_inadimplencia` | Campanha de cobrança + política preventiva |
| `crescer` | Investimento vs capital de giro disponível |
| `equilibrar` | Break-even + reserva 30 dias |

## Persiste em

`~/.agente-cfo/memory/planos/<objetivo>-<data>.json`
