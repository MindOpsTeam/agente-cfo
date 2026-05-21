---
name: cfo-cobranca-orquestrada
description: >
  Workflow agentic de cobrança end-to-end: classifica inadimplentes por bucket,
  decide ação automaticamente, executa via cobranca_gateway (Asaas/Iugu) e
  registra em cfo_write_events. Marcos usa após aprovação do dono para
  executar cobranças em lote com confirmação prévia.
category: CFO/Cobrança
metadata:
  { "openclaw": { "emoji": "💸", "requires": { "bins": ["python3"] } } }
---

# CFO — Cobrança Orquestrada

> ⚠️ **Requer confirmação explícita** antes de executar qualquer cobrança.

## Quando usar

| Situação | Comando |
|---|---|
| "executa as cobranças" (após ver sugestão) | `python3 $SKILL_DIR/scripts/orquestrar_cobranca.py --dry-run` |
| Após dono confirmar lote | `python3 $SKILL_DIR/scripts/orquestrar_cobranca.py --executar` |

## Fluxo obrigatório

1. Marcos chama `--dry-run` → mostra o plano
2. Marcos apresenta plano ao dono com total de cobranças + valor
3. Dono responde "SIM" ou aprova lote específico
4. Marcos chama `--executar` com os IDs aprovados

## Política de ação por bucket

| Dias vencido | Ação automática |
|---|---|
| 0–7 | Lembrete via WhatsApp (send_payment_link) |
| 8–30 | Notificação formal + link de pagamento |
| 31–60 | Boleto novo + mensagem de cobrança |
| >60 | Apenas marcar para análise — NÃO executa automaticamente |
