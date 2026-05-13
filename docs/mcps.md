# MCP Servers — Agente CFO

Cada skill expoe um MCP server stdio (`mcp_server.py`) que pode ser consumido por qualquer cliente MCP (Claude Code, OpenClaw, etc).

## Como rodar

```bash
# Ativar venv (precisa do pacote mcp)
source .venv/bin/activate

# Rodar qualquer skill como MCP server
python3 skills/<nome>/mcp_server.py
```

## Tabela de cobertura

| Skill | Categoria | Tools | Endpoints cobertos | URL doc |
|-------|-----------|-------|--------------------|---------|
| omie | ERP | 25 | clientes, produtos, pedidos, financeiro (pagar/receber), NF-e, estoque, empresa, saldo, vencidos | https://developer.omie.com.br/service-list/ |
| bling | ERP | 8 | saldo, contas a pagar, contas a receber, baixa, criacao, empresa | https://developer.bling.com.br/referencia |
| tiny | ERP | 9 | saldo, contas a pagar, contas a receber, baixa, criacao, cancelamento, empresa | https://www.tiny.com.br/ajuda/api |
| granatum | ERP | 9 | saldo, contas a pagar, contas a receber, baixa, criacao, cancelamento, empresa | https://granatum.docs.apiary.io/ |
| vhsys | ERP | 8 | saldo, contas a pagar, contas a receber, baixa, criacao, empresa | https://developers.vhsys.com.br/ |
| nibo | ERP | 8 | saldo, contas a pagar, contas a receber, baixa, criacao, empresa | https://api.nibo.com.br/docs |
| contaazul | ERP | 9 | saldo, contas a pagar, contas a receber, baixa, criacao, cancelamento, empresa | https://developers.contaazul.com/reference |
| hubspot | CRM | 8 | deals (listar, mover, atualizar, criar, nota, ganho, perdido), empresa | https://developers.hubspot.com/docs/api/crm/contacts |
| rd-station | CRM | 8 | deals (listar, mover, atualizar, criar, nota, ganho, perdido), empresa | https://developers.rdstation.com/reference |
| piperun | CRM | 8 | deals (listar, mover, atualizar, criar, nota, ganho, perdido), empresa | https://vendas.developers.pipe.run/ |
| pipedrive | CRM | 8 | deals (listar, mover, atualizar, criar, nota, ganho, perdido), empresa | https://developers.pipedrive.com/docs/api/v1/ |
| asaas | Cobranca | 9 | cobrancas, detalhe, cliente, criar, cancelar, baixa manual, link pagamento, meios, empresa | https://docs.asaas.com/reference |
| iugu | Cobranca | 9 | cobrancas, detalhe, cliente, criar, cancelar, baixa manual, link pagamento, meios, empresa | https://dev.iugu.com/reference |
| mercado-livre | E-commerce | 9 | pedidos, detalhe, produtos, estoque, preco, enviar, cancelar, empresa | https://developers.mercadolivre.com.br/pt_br/api-docs-pt-br |
| nuvemshop | E-commerce | 9 | pedidos, detalhe, produtos, estoque, preco, enviar, cancelar, empresa | https://dev.tiendanube.com/pt/api |

**Total: 15 skills, 134 tools**

## Arquitetura

- Cada `mcp_server.py` importa o `*_client.py` existente (classe `*Client`)
- Instanciacao lazy: o client so e criado no primeiro `call_tool`, evitando crash se secrets nao estao configurados
- Secrets carregados de `~/.openclaw/secrets/<skill>.env` pelo proprio client
- Transport: stdio (JSON-RPC 2.0, newline-delimited)
- Python: requer 3.12+ (venv em `.venv/`)

## Smoke test

```bash
# Rodar smoke test de qualquer skill
cd skills/<nome>
../../.venv/bin/python3 tests/test_mcp.py
```
