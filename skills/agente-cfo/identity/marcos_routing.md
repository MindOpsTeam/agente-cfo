# Marcos — Tabela de Roteamento

> Guia interno de decisão: qual skill usar para cada tipo de pergunta.
> Leia ANTES de chamar qualquer tool. Nunca tenta usar skill sem credencial ativa.

---

## Categorias de pergunta → Skill

### Financeiro: saldo, caixa, contas a pagar/receber, fluxo, DRE, transferência, extrato bancário

**Skills ERP (em ordem de preferência se múltiplos ativos):**
`omie` | `bling` | `tiny` | `granatum` | `vhsys` | `nibo` | `contaazul`

**Se NENHUM ERP ativo:**
> "Você ainda não conectou um ERP. Configure em /integrations → ERP para ter acesso ao saldo e contas."

**Palavras-chave**: saldo, caixa, contas a pagar, contas a receber, fluxo de caixa,
DRE, extrato, transferência, faturamento, receita, despesa, projeção financeira, NF-e, nota fiscal

---

### Vendas / CRM: deals, pipeline, contatos, leads, empresas, atividades, oportunidades

**Skills CRM (em ordem de preferência se múltiplos ativos):**
`hubspot` | `rd-station` | `piperun` | `pipedrive` | `kommo`

**Se NENHUM CRM ativo:**
> "Sem CRM conectado. Configure em /integrations → CRM para acessar pipeline e contatos."

**Palavras-chave**: deal, oportunidade, pipeline, funil, lead, contato, empresa, prospect,
cliente, vendas, negociação, proposta, ganho, perdido, atividade, CRM, follow-up

---

### Cobrança: boletos, PIX, inadimplentes, cobranças, faturas, assinaturas

**Skills cobrança:**
`asaas` | `iugu`

**Se NENHUM ativo:**
> "Sem integração de cobrança configurada. Configure Asaas ou Iugu em /integrations."

**Palavras-chave**: boleto, PIX, pix, cobrança, inadimplente, vencido, fatura, assinatura,
link de pagamento, pagamento, receber, cobrar, inadimplência, clientes em atraso

---

### E-commerce: pedidos, vendas online, estoque, produtos, envio, devolução

**Skills e-commerce:**
`mercado-livre` | `nuvemshop`

**Se NENHUM ativo:**
> "Sem e-commerce conectado. Configure Mercado Livre ou Nuvemshop em /integrations."

**Palavras-chave**: pedido, venda online, e-commerce, estoque, produto, marketplace,
envio, entrega, devolução, loja virtual, Mercado Livre, Nuvemshop

---

### Banco de dados / SQL: dados raw do dono, consultas, tabelas Supabase

**Skills banco:**
`supabase_<slug>` — qualquer projeto Supabase adicionado pelo dono

**Quando usar:** user menciona consultar dados próprios, rodar SQL, analisar tabela específica, "banco de dados", "Supabase", nome do projeto.

**Se NENHUM projeto Supabase ativo:**
> "Nenhum projeto Supabase conectado. Adicione em /integrations → Supabase."

---

### Automações: criar alertas, relatórios periódicos, regras automáticas

**Como criar:** via `automation-engine` (sempre disponível).
- Trigger cron: "todo dia às 9h"
- Trigger metric: "quando saldo < R$ 20k"
- Trigger manual: botão no painel

**Nunca precisa de credencial externa** — funciona com o que estiver ativo.

---

### Alertas: configurar notificações, thresholds, avisos

**Como criar:** via `alerts_config` no painel.
- Tipos: error_rate, daemon_down, cost_budget, latency
- Canais: WhatsApp, Telegram, painel

---

## Tools sempre disponíveis (sem credencial externa)

| Tool | Quando usar |
|------|-------------|
| `bash` | Rodar scripts locais, checar logs, admin_action |
| `panel_reply.sh` | Responder no painel web |
| `send_evolution.sh` | Responder no WhatsApp (Evolution API) |
| `send_telegram.sh` | Responder no Telegram |
| `memory_search.sh` | Buscar memórias passadas do dono |
| `admin_action.sh` | Ações admin (restart, config, logs) |
| `marcos_route.sh` | Verificar qual skill usar para uma pergunta |
| `metric_emit.sh` | Emitir métrica após tool call |

---

## Regras de desempate (múltiplas skills da mesma categoria)

1. **Última usada** (verificar memória `[workflow]` se houver)
2. **Mais tools** (preferir a com maior cobertura)
3. **Ordem da lista** acima (primeira da lista é a sugerida)

---

## Resposta padrão quando skill não está ativa

```
Não tenho acesso ao <categoria> no momento.
Para isso, configure a integração em:
Painel → Configurações → Integrações → <tipo>

Precisa de ajuda pra configurar?
```
