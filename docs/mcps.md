# MCP Servers — Agente CFO

Cada skill expõe um MCP server stdio (`mcp_server.py`) consumível por qualquer cliente MCP (Claude Code, OpenClaw, etc).

**Última atualização:** Sprint 21 — 524 tools totais (era 134 no Sprint 20)

## Como rodar

```bash
# Ativar venv (requer pacote mcp)
source /opt/agente-cfo/.venv/bin/activate

# Rodar qualquer skill como MCP server
python3 skills/<nome>/mcp_server.py
```

## Tabela de cobertura (Sprint 21)

| Skill | Categoria | Tools | Principais recursos cobertos | URL doc |
|-------|-----------|------:|------------------------------|---------|
| omie | ERP | **41** | clientes, produtos, pedidos, financeiro (pagar/receber), NF-e, estoque, departamentos, projetos, contas correntes, fluxo de caixa | https://developer.omie.com.br/service-list/ |
| bling | ERP | **35** | produtos, pedidos de venda, NF-e, NFC-e, clientes, fornecedores, estoque, categorias, contas a pagar/receber | https://developer.bling.com.br/referencia |
| tiny | ERP | **28** | produtos, pedidos, NF-e, clientes, fornecedores, estoque, contas, cancelamento, XML | https://www.tiny.com.br/ajuda/api |
| granatum | ERP | **39** | contas, lançamentos, categorias, clientes, fornecedores, contatos, centros de custo, relatórios, saldo | https://granatum.docs.apiary.io/ |
| vhsys | ERP | **54** | clientes, produtos, pedidos de venda/compra, NF-e, contas bancárias, financeiro, fornecedores, vendedores, categorias, centro de custo | https://developers.vhsys.com.br/ |
| nibo | ERP | **40** | contas bancárias, clientes, fornecedores, contas a pagar/receber, categorias, centros de custo, transferências, conciliação | https://api.nibo.com.br/docs |
| contaazul | ERP | **32** | clientes, produtos, pedidos de venda, contas a pagar/receber, NF-e, contas bancárias, categorias | https://developers.contaazul.com/reference |
| hubspot | CRM | **38** | contacts, companies, deals, tickets, line items, notes, calls, emails, meetings, tasks, properties, owners, pipelines, associations | https://developers.hubspot.com/docs/api/crm/contacts |
| rd-station | CRM | **27** | contatos, leads, oportunidades, funil, segmentações, automações, campos customizados, conversões, webhooks | https://developers.rdstation.com/reference |
| piperun | CRM | **27** | deals, pipelines, stages, contatos, empresas, atividades, campos custom, produtos, usuários | https://vendas.developers.pipe.run/ |
| pipedrive | CRM | **35** | deals, persons, organizations, activities, products, pipelines, stages, notes, users, webhooks, goals, filters | https://developers.pipedrive.com/docs/api/v1/ |
| asaas | Cobrança | **33** | clientes, cobranças (boleto/cartão/pix), assinaturas, notificações, split, transferências, extrato, webhook, subcontas | https://docs.asaas.com/reference |
| iugu | Cobrança | **33** | clientes, cobranças, faturas, planos, assinaturas, transferências, extrato, split, marketplace, webhooks | https://dev.iugu.com/reference |
| mercado-livre | E-commerce | **27** | itens (publicações), pedidos, perguntas/respostas, mensagens, vendedor, categorias, envios, devoluções | https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br |
| nuvemshop | E-commerce | **35** | produtos, variantes, categorias, clientes, pedidos, cupons, páginas, frete, metafields, webhooks | https://dev.tiendanube.com/pt/api |

**Total Sprint 21: 15 skills · 524 tools · 15/15 smoke tests passando**

---

## Evolução

| Sprint | Total tools | Skills completas |
|--------|------------|-----------------|
| Sprint 20 | 134 | 15/15 (esqueletos ~8-25 tools cada) |
| Sprint 21 | **524** | 15/15 (expandidas via doc oficial) |

---

## Arquitetura

- Cada `mcp_server.py` importa o `*_client.py` existente (retrocompatível)
- Instanciação lazy: client criado no primeiro `call_tool`, não crasha sem secrets
- Secrets: `~/.openclaw/secrets/<skill>.env` (mesmo padrão do `connect.sh`)
- Transport: stdio JSON-RPC 2.0 (newline-delimited)
- Python 3.12+ / venv em `.venv/`

## Smoke test

```bash
cd /opt/agente-cfo
source .venv/bin/activate

# Testar todas as skills
for skill in omie bling tiny granatum vhsys nibo contaazul hubspot rd-station piperun pipedrive asaas iugu mercado-livre nuvemshop; do
  echo -n "[$skill] " && python3 skills/$skill/tests/test_mcp.py
done
```

## Atualização na VPS do cliente

```bash
cd /opt/agente-cfo && git pull
# Instalar/atualizar mcp se necessário:
.venv/bin/pip install --upgrade mcp
# Validar:
for skill in omie bling tiny granatum vhsys nibo contaazul hubspot rd-station piperun pipedrive asaas iugu mercado-livre nuvemshop; do
  echo -n "[$skill] " && .venv/bin/python3 skills/$skill/tests/test_mcp.py
done
```
