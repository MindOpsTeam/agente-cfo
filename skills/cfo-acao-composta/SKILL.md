---
name: cfo-acao-composta
description: >
  Workflow atômico multi-passo com checkpoint e retomada. Permite orquestrar
  ações compostas (ex: "cobre todos os inadimplentes acima de R$500") que
  envolvem múltiplos steps, cada um com estado persistido. Se um step falha,
  o workflow retoma de onde parou no próximo turn.
category: CFO/Orquestração
metadata:
  { "openclaw": { "emoji": "⚙️", "requires": { "bins": ["python3"] } } }
---

# CFO — Ação Composta (Workflow Multi-step)

## Quando usar

| Situação | Comando |
|---|---|
| Orquestrar cobrança em lote | `python3 $SKILL_DIR/scripts/iniciar_workflow.py --nome "cobrar-inadimplentes-500"` |
| Ver workflows em andamento | `python3 $SKILL_DIR/scripts/iniciar_workflow.py --listar` |
| Retomar workflow interrompido | `python3 $SKILL_DIR/scripts/iniciar_workflow.py --retomar <id>` |

## Fluxo típico

```
Dono: "cobre os inadimplentes acima de R$500"
Marcos:
  1. iniciar_workflow.py --nome "cobrar-inadimplentes" → cria workflow-id
  2. Step 1: lista inadimplentes > R$500 (cfo-inadimplencia aging)
  3. Step 2: para cada, mostra plano → pede SIM do dono (confirmação batch)
  4. Step 3: executa cobranças via cobranca_gateway
  5. Step 4: registra cada em cfo_write_events
  6. Step 5: confirma ao dono "12/15 cobranças enviadas"
  Cada step salva checkpoint — se travar em Step 3, retoma de lá.
```

## Persistência

`~/.agente-cfo/memory/workflows/<workflow-id>.json`

## Design

- Um workflow por conversa ativa por vez
- Confirmação no início do batch (não pede pra cada item)
- Timeout: 10 minutos sem resposta = workflow expirado
