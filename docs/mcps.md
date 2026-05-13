# MCP Servers — Agente CFO

Cada skill expõe um MCP server stdio (`mcp_server.py`) consumível por qualquer cliente MCP (Claude Code, OpenClaw, etc).

**Última atualização:** Sprint 24 — 1280 tools totais (era 1084 no Sprint 23)

## Como rodar

```bash
# Ativar venv (requer pacote mcp)
source /opt/agente-cfo/.venv/bin/activate

# Rodar qualquer skill como MCP server
python3 skills/<nome>/mcp_server.py
```

## Tabela de cobertura (Sprint 24)

| Skill | Categoria | Tools | Principais recursos cobertos | URL doc |
|-------|-----------|------:|------------------------------|---------|
| omie | ERP | **96** | clientes, produtos, pedidos venda/compra, financeiro (pagar/receber), NF-e, NFS-e, estoque, departamentos, projetos, contas correntes, fluxo de caixa, fornecedores, vendedores, transportadoras, centros de custo, serviços, categorias CRUD, transferências entre contas, tags CRUD, download XML | https://developer.omie.com.br/service-list/ |
| bling | ERP | **116** | produtos, pedidos de venda/compra, NF-e, NFC-e, NFS-e, clientes, fornecedores, estoque, categorias, contas a pagar/receber, depositos CRUD, logísticas, webhooks, contratos CRUD, propostas, ordens produção, campos customizados, serviços, naturezas de operação CRUD, tributações, unidades de medida, vendedores CRUD | https://developer.bling.com.br/referencia |
| tiny | ERP | **28** | produtos, pedidos, NF-e, clientes, fornecedores, estoque, contas, cancelamento, XML | https://www.tiny.com.br/ajuda/api |
| granatum | ERP | **39** | contas, lançamentos, categorias, clientes, fornecedores, contatos, centros de custo, relatórios, saldo | https://granatum.docs.apiary.io/ |
| vhsys | ERP | **54** | clientes, produtos, pedidos de venda/compra, NF-e, contas bancárias, financeiro, fornecedores, vendedores, categorias, centro de custo | https://developers.vhsys.com.br/ |
| nibo | ERP | **40** | contas bancárias, clientes, fornecedores, contas a pagar/receber, categorias, centros de custo, transferências, conciliação | https://api.nibo.com.br/docs |
| contaazul | ERP | **32** | clientes, produtos, pedidos de venda, contas a pagar/receber, NF-e, contas bancárias, categorias | https://developers.contaazul.com/reference |
| hubspot | CRM | **463** | CRM Core (contacts, companies, deals, tickets, line items, quotes, notes, calls, emails, meetings, tasks, products, associations, batch ops, custom objects full), CMS (blog posts, site/landing pages, redirects, domains, HubDB, source code, templates, themes, blog authors/tags, site search, audit), Files, Conversations (threads, messages, inboxes, custom channels), Marketing (events, campaigns, subscriptions, transactional email, forms v3, email stats, workflows v1), Settings (users batch, teams, roles/permissions, account info, API usage, activity logs, property options), Automation (workflows v4, sequences full + steps + enrollments, custom actions), Analytics (event definitions, behavioral events, web analytics, goals), OAuth/App info, Webhooks v3, KB articles + categories, feedback surveys | https://developers.hubspot.com/docs/api/crm/contacts |
| rd-station | CRM | **27** | contatos, leads, oportunidades, funil, segmentações, automações, campos customizados, conversões, webhooks | https://developers.rdstation.com/reference |
| piperun | CRM | **27** | deals, pipelines, stages, contatos, empresas, atividades, campos custom, produtos, usuários | https://vendas.developers.pipe.run/ |
| pipedrive | CRM | **144** | deals, persons, organizations, activities, products, pipelines, stages, notes, users, webhooks, goals, filters, leads, lead labels, call logs, mailbox, custom fields, roles, files, currencies, item search, subscriptions, projects, meetings providers, changelogs | https://developers.pipedrive.com/docs/api/v1/ |
| kommo | CRM | **85** | leads, contacts, companies, customers, tasks, pipelines, users, account, custom fields, custom field groups, catalogs, events, calls, tags, webhooks, notes, links, segments, sources, chats, roles, shortlinks, salesbot | https://www.kommo.com/developers/content/api/ |
| asaas | Cobrança | **33** | clientes, cobranças (boleto/cartão/pix), assinaturas, notificações, split, transferências, extrato, webhook, subcontas | https://docs.asaas.com/reference |
| iugu | Cobrança | **33** | clientes, cobranças, faturas, planos, assinaturas, transferências, extrato, split, marketplace, webhooks | https://dev.iugu.com/reference |
| mercado-livre | E-commerce | **27** | itens (publicações), pedidos, perguntas/respostas, mensagens, vendedor, categorias, envios, devoluções | https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br |
| nuvemshop | E-commerce | **35** | produtos, variantes, categorias, clientes, pedidos, cupons, páginas, frete, metafields, webhooks | https://dev.tiendanube.com/pt/api |

**Total Sprint 24: 16 skills · 1280 tools · 16/16 smoke tests passando**

### Cobertura HubSpot por hub

| Hub | Tools | Endpoints cobertos |
|-----|------:|-------------------|
| CRM Core | 133 | contacts, companies, deals, tickets, line items, quotes, notes, calls, emails, meetings, tasks, products, associations, properties, pipelines, owners, search, batch ops, custom objects, communications, postal mail, forms, feedback, marketing emails |
| CMS Hub | 49 | blog posts, site pages, landing pages, URL redirects, domains, site performance, HubDB tables + rows |
| Files Hub | 12 | files CRUD, signed URLs, import from URL, folders |
| Conversations Hub | 13 | threads, messages, inboxes, channels |
| Marketing Hub | 20 | marketing events, campaigns, subscription preferences, transactional email |
| Settings Hub | 13 | users, teams, business units, currencies |
| Automation Hub | 9 | workflows, sequences |
| CRM Extras | 18 | imports, exports, lists + memberships, audit logs, behavioral events |
| **Sprint 24 additions** | | |
| Marketing Workflows & Forms v3 | 37 | workflows legacy v1 (CRUD + enroll), forms v3 (CRUD + submissions + fields), email stats, marketing emails extras (create/clone/schedule), lists v3 extras (search, batch, folders) |
| Automation Sequences full | 25 | sequences v4 (CRUD + steps), sequence enrollments (pause/resume), custom workflow actions (CRUD + functions + revisions) |
| CMS Source Code + Templates | 32 | source code files (CRUD + validate + metadata), templates v2, themes (settings + fields), site search, blog authors/tags CRUD, CMS audit logs |
| Analytics & Behavioral Events | 19 | event definitions (CRUD + properties), fire events v3, analytics reports, web analytics, contact events, goals CRUD |
| OAuth & App Info | 14 | OAuth token info/refresh/revoke, app info, installed apps, webhooks v3 subscriptions (CRUD + batch + settings) |
| Settings Users/Roles full | 17 | users batch create/update, user roles/teams list, permission sets CRUD, account info/API usage/limits, login/security activity, property options CRUD |
| Service Hub / KB | 20 | KB articles (CRUD + publish + clone + batch), KB categories CRUD, feedback surveys/responses, conversations custom channels (CRUD + accounts) |
| CRM Objects Extras | 32 | products/quotes/lineitems/calls/emails/meetings/notes search + batch, postal mail CRUD, custom objects (update/delete/search/batch/schema CRUD + labels) |
| **Total HubSpot** | **463** | |

---

## Evolução

| Sprint | Total tools | Skills completas |
|--------|------------|-----------------|
| Sprint 20 | 134 | 15/15 (esqueletos ~8-25 tools cada) |
| Sprint 21 | **524** | 15/15 (expandidas via doc oficial) |
| Sprint 22 | **878** | 16/16 (+kommo do zero, 4 skills expandidas) |
| Sprint 23 | **1084** | 16/16 (HubSpot 100% hubs, gaps Kommo/Pipedrive/Omie/Bling) |
| Sprint 24 | **1280** | 16/16 (HubSpot 267→463 — 8 hubs novos: workflows v1, forms v3, sequences full, CMS source/templates/themes, analytics/events, OAuth/webhooks v3, settings full, KB/service hub, CRM extras) |

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
for skill in omie bling tiny granatum vhsys nibo contaazul hubspot rd-station piperun pipedrive kommo asaas iugu mercado-livre nuvemshop; do
  echo -n "[$skill] " && python3 skills/$skill/tests/test_mcp.py
done
```

## Atualização na VPS do cliente

```bash
cd /opt/agente-cfo && git pull
# Instalar/atualizar mcp se necessário:
.venv/bin/pip install --upgrade mcp
# Validar:
for skill in omie bling tiny granatum vhsys nibo contaazul hubspot rd-station piperun pipedrive kommo asaas iugu mercado-livre nuvemshop; do
  echo -n "[$skill] " && .venv/bin/python3 skills/$skill/tests/test_mcp.py
done
```
