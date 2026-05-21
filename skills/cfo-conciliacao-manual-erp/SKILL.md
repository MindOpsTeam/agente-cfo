---
name: cfo-conciliacao-manual-erp
description: >
  Gerencia lançamentos feitos via chat que ficaram no painel como
  erp="dashboard_only" (ERP estava indisponível). Lista pendentes e
  oferece migração em lote quando o ERP estiver disponível.
category: CFO/Conciliação
metadata:
  { "openclaw": { "emoji": "📋", "requires": { "bins": ["python3"] } } }
---

# CFO — Conciliação Lançamentos Manuais ↔ ERP

## Quando usar

| Situação | Comando |
|---|---|
| "tem lançamento manual que não foi pro Omie?" | `python3 $SKILL_DIR/scripts/listar_pendentes.py` |
| "migra os lançamentos pro ERP" (após user confirmar) | `python3 $SKILL_DIR/scripts/migrar.py --dry-run` → aprovação → `--executar` |

## O que são lançamentos "dashboard_only"?

Quando erp_gateway falha com erro de módulo/plano (ex: Omie modo teste HTTP 404),
o fallback atômico registra em `cfo_write_events` com `erp="dashboard_only"` e
`erp_record_id=NULL`. Esses lançamentos precisam ser migrados quando o ERP estiver OK.

## Fluxo de migração

1. `listar_pendentes.py` → lista N lançamentos pendentes
2. Marcos apresenta ao dono com total
3. Dono aprova: "SIM"
4. `migrar.py --executar` → cria no ERP via erp_gateway.py + atualiza cfo_write_events
