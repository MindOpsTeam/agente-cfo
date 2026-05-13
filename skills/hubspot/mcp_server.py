#!/usr/bin/env python3
"""
MCP server para HubSpot — 463 tools.
CRM completo: deals, contacts, companies, tickets, line_items, notes, calls,
emails, meetings, tasks, pipelines, owners, properties, quotes, associations,
products, forms, marketing emails, feedback, custom objects, communications,
postal mail. Batch operations para todos os objetos principais.
CMS Hub (blog posts, site pages, landing pages, redirects, domains, HubDB),
Files Hub, Conversations Hub, Marketing Hub (events, campaigns, subscriptions,
transactional email), Settings Hub (users, teams, business units, currencies),
Automation (workflows, sequences), CRM extras (imports, exports, lists,
audit logs, behavioral events).
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from hubspot_client import HubSpotClient
from base import http_request

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('hubspot')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = HubSpotClient()
    return _client


def _del(c, path):
    """Raw DELETE for endpoints not covered by c._delete_object."""
    url = f"{c.BASE_URL}/{path}"
    http_request("DELETE", url, headers=c.headers)
    return {"success": True, "deleted": path}


def _tool(name, desc, props=None, required=None):
    return types.Tool(
        name=name,
        description=desc,
        inputSchema={
            'type': 'object',
            'properties': props or {},
            'required': required or [],
        },
    )


_LIMIT = {'type': 'integer', 'description': 'Limite de resultados (default 50)', 'default': 50}
_ID = lambda entity: {'type': 'string', 'description': f'ID do {entity}'}
_PROPS_DICT = {'type': 'object', 'description': 'Dicionario de propriedades a atualizar', 'additionalProperties': {'type': 'string'}}


_BATCH_INPUTS = {'type': 'array', 'description': 'Lista de objetos para operacao em lote', 'items': {'type': 'object'}}
_BATCH_INPUTS_IDS = {'type': 'array', 'description': 'Lista de objetos com id [{id: "123"}, ...]', 'items': {'type': 'object'}}
_OBJ_TYPE = {'type': 'string', 'description': 'Tipo de objeto CRM (contacts, companies, deals, tickets, etc.)'}
_FROM_TYPE = {'type': 'string', 'description': 'Tipo de objeto de origem (contacts, companies, deals, etc.)'}
_TO_TYPE = {'type': 'string', 'description': 'Tipo de objeto de destino'}
_PIPELINE_OBJ_TYPE = {'type': 'string', 'description': 'Tipo de objeto (deals, tickets)', 'default': 'deals'}
_PIPELINE_ID = {'type': 'string', 'description': 'ID da pipeline'}
_STAGE_ID = {'type': 'string', 'description': 'ID do stage/etapa'}
_ASSOC_LIST = {'type': 'array', 'description': 'Lista de associacoes', 'items': {'type': 'object'}}
_PROPS_LIST = {'type': 'array', 'description': 'Lista de nomes de propriedades', 'items': {'type': 'string'}}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Deals (9 existing) ───────────────────────────────────────────
        _tool('hubspot_deals_listar', 'Lista deals/oportunidades do HubSpot (paginado)', {
            'status': {'type': 'string', 'description': 'Filtro de status (open, won, lost)', 'default': 'open'},
            'limit': _LIMIT,
            'page': {'type': 'integer', 'description': 'Pagina (default 1)', 'default': 1},
        }),
        _tool('hubspot_deal_obter', 'Obtem detalhes de um deal especifico', {
            'id': _ID('deal'),
        }, ['id']),
        _tool('hubspot_deal_criar', 'Cria novo deal/oportunidade no HubSpot', {
            'title': {'type': 'string', 'description': 'Titulo do deal'},
            'amount': {'type': 'number', 'description': 'Valor do deal'},
            'pipeline': {'type': 'string', 'description': 'Pipeline/funil'},
        }, ['title']),
        _tool('hubspot_deal_atualizar', 'Atualiza valor e/ou data de fechamento do deal', {
            'id': _ID('deal'),
            'amount': {'type': 'number', 'description': 'Novo valor do deal'},
            'close_date': {'type': 'string', 'description': 'Nova data de fechamento (YYYY-MM-DD)'},
        }, ['id']),
        _tool('hubspot_deal_mover', 'Move deal para outra etapa/stage', {
            'id': _ID('deal'),
            'to_stage': {'type': 'string', 'description': 'Nome ou ID da etapa destino'},
        }, ['id', 'to_stage']),
        _tool('hubspot_deal_nota', 'Adiciona nota/comentario a um deal', {
            'id': _ID('deal'),
            'note': {'type': 'string', 'description': 'Texto da nota'},
        }, ['id', 'note']),
        _tool('hubspot_deal_ganho', 'Marca deal como ganho/won', {
            'id': _ID('deal'),
        }, ['id']),
        _tool('hubspot_deal_perdido', 'Marca deal como perdido/lost', {
            'id': _ID('deal'),
            'reason': {'type': 'string', 'description': 'Motivo da perda'},
        }, ['id']),
        _tool('hubspot_deal_excluir', 'Exclui um deal do HubSpot', {
            'id': _ID('deal'),
        }, ['id']),

        # ── Deals batch (3 new) ──────────────────────────────────────────
        _tool('hubspot_deals_batch_criar', 'Cria deals em lote no HubSpot', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_deals_batch_atualizar', 'Atualiza deals em lote no HubSpot', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_deals_batch_arquivar', 'Arquiva/exclui deals em lote no HubSpot', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── Contacts (5 existing) ────────────────────────────────────────
        _tool('hubspot_contatos_listar', 'Lista contatos do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_contato_obter', 'Obtem detalhes de um contato', {
            'id': _ID('contato'),
        }, ['id']),
        _tool('hubspot_contato_criar', 'Cria novo contato no HubSpot', {
            'email': {'type': 'string', 'description': 'Email do contato'},
            'firstname': {'type': 'string', 'description': 'Primeiro nome'},
            'lastname': {'type': 'string', 'description': 'Sobrenome'},
            'phone': {'type': 'string', 'description': 'Telefone'},
        }, ['email']),
        _tool('hubspot_contato_atualizar', 'Atualiza propriedades de um contato', {
            'id': _ID('contato'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_contato_excluir', 'Exclui um contato do HubSpot', {
            'id': _ID('contato'),
        }, ['id']),

        # ── Contacts batch (4 new) ───────────────────────────────────────
        _tool('hubspot_contatos_batch_criar', 'Cria contatos em lote no HubSpot', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_contatos_batch_atualizar', 'Atualiza contatos em lote no HubSpot', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_contatos_batch_ler', 'Le contatos em lote por IDs', {
            'inputs': _BATCH_INPUTS_IDS,
            'properties': _PROPS_LIST,
        }, ['inputs']),
        _tool('hubspot_contatos_batch_arquivar', 'Arquiva/exclui contatos em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── Companies (5 existing) ───────────────────────────────────────
        _tool('hubspot_empresas_listar', 'Lista empresas do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_empresa_obter', 'Obtem detalhes de uma empresa', {
            'id': _ID('empresa'),
        }, ['id']),
        _tool('hubspot_empresa_criar', 'Cria nova empresa no HubSpot', {
            'name': {'type': 'string', 'description': 'Nome da empresa'},
            'domain': {'type': 'string', 'description': 'Dominio da empresa'},
            'industry': {'type': 'string', 'description': 'Industria/setor'},
        }, ['name']),
        _tool('hubspot_empresa_atualizar', 'Atualiza propriedades de uma empresa', {
            'id': _ID('empresa'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_empresa_excluir', 'Exclui uma empresa do HubSpot', {
            'id': _ID('empresa'),
        }, ['id']),

        # ── Companies batch (3 new) ──────────────────────────────────────
        _tool('hubspot_empresas_batch_criar', 'Cria empresas em lote no HubSpot', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_empresas_batch_atualizar', 'Atualiza empresas em lote no HubSpot', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_empresas_batch_arquivar', 'Arquiva/exclui empresas em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── Tickets (4 existing + 6 new = 10) ────────────────────────────
        _tool('hubspot_tickets_listar', 'Lista tickets de suporte do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_ticket_obter', 'Obtem detalhes de um ticket', {
            'id': _ID('ticket'),
        }, ['id']),
        _tool('hubspot_ticket_criar', 'Cria novo ticket de suporte', {
            'subject': {'type': 'string', 'description': 'Assunto do ticket'},
            'content': {'type': 'string', 'description': 'Descricao do ticket'},
            'priority': {'type': 'string', 'description': 'Prioridade (LOW, MEDIUM, HIGH)'},
        }, ['subject']),
        _tool('hubspot_ticket_atualizar', 'Atualiza propriedades de um ticket', {
            'id': _ID('ticket'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_ticket_excluir', 'Exclui um ticket do HubSpot', {
            'id': _ID('ticket'),
        }, ['id']),
        _tool('hubspot_tickets_buscar', 'Busca tickets por termo de pesquisa', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_tickets_batch_criar', 'Cria tickets em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_tickets_batch_atualizar', 'Atualiza tickets em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_tickets_batch_ler', 'Le tickets em lote por IDs', {
            'inputs': _BATCH_INPUTS_IDS,
            'properties': _PROPS_LIST,
        }, ['inputs']),
        _tool('hubspot_tickets_batch_arquivar', 'Arquiva/exclui tickets em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── Line Items (1 existing + 6 new = 7) ─────────────────────────
        _tool('hubspot_line_items_listar', 'Lista line items (itens de linha) do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_lineitem_obter', 'Obtem detalhes de um line item', {
            'id': _ID('line item'),
        }, ['id']),
        _tool('hubspot_lineitem_criar', 'Cria novo line item no HubSpot', {
            'properties': _PROPS_DICT,
        }, ['properties']),
        _tool('hubspot_lineitem_atualizar', 'Atualiza propriedades de um line item', {
            'id': _ID('line item'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_lineitem_excluir', 'Exclui um line item do HubSpot', {
            'id': _ID('line item'),
        }, ['id']),
        _tool('hubspot_lineitems_batch_criar', 'Cria line items em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_lineitems_batch_atualizar', 'Atualiza line items em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_lineitems_batch_arquivar', 'Arquiva/exclui line items em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── Quotes (5 new) ───────────────────────────────────────────────
        _tool('hubspot_quotes_listar', 'Lista orcamentos/quotes do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_quote_obter', 'Obtem detalhes de um orcamento/quote', {
            'id': _ID('quote'),
        }, ['id']),
        _tool('hubspot_quote_criar', 'Cria novo orcamento/quote no HubSpot', {
            'properties': _PROPS_DICT,
        }, ['properties']),
        _tool('hubspot_quote_atualizar', 'Atualiza propriedades de um orcamento/quote', {
            'id': _ID('quote'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_quote_excluir', 'Exclui um orcamento/quote do HubSpot', {
            'id': _ID('quote'),
        }, ['id']),

        # ── Notes (2 existing + 3 new = 5) ───────────────────────────────
        _tool('hubspot_notas_listar', 'Lista notas/engagements do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_nota_criar', 'Cria nota associada a contato ou deal', {
            'body': {'type': 'string', 'description': 'Texto da nota'},
            'contact_id': {'type': 'string', 'description': 'ID do contato associado'},
            'deal_id': {'type': 'string', 'description': 'ID do deal associado'},
        }, ['body']),
        _tool('hubspot_nota_obter', 'Obtem detalhes de uma nota', {
            'id': _ID('nota'),
        }, ['id']),
        _tool('hubspot_nota_atualizar', 'Atualiza propriedades de uma nota', {
            'id': _ID('nota'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_nota_excluir', 'Exclui uma nota do HubSpot', {
            'id': _ID('nota'),
        }, ['id']),

        # ── Calls (2 existing + 3 new = 5) ───────────────────────────────
        _tool('hubspot_calls_listar', 'Lista chamadas/ligacoes do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_call_criar', 'Registra nova chamada/ligacao no HubSpot', {
            'title': {'type': 'string', 'description': 'Titulo da chamada'},
            'body': {'type': 'string', 'description': 'Notas da chamada'},
            'duration_ms': {'type': 'integer', 'description': 'Duracao em milissegundos'},
            'contact_id': {'type': 'string', 'description': 'ID do contato associado'},
        }, ['title']),
        _tool('hubspot_call_obter', 'Obtem detalhes de uma chamada', {
            'id': _ID('chamada'),
        }, ['id']),
        _tool('hubspot_call_atualizar', 'Atualiza propriedades de uma chamada', {
            'id': _ID('chamada'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_call_excluir', 'Exclui uma chamada do HubSpot', {
            'id': _ID('chamada'),
        }, ['id']),

        # ── Emails (1 existing + 4 new = 5) ──────────────────────────────
        _tool('hubspot_emails_listar', 'Lista emails registrados no HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_email_obter', 'Obtem detalhes de um email registrado', {
            'id': _ID('email'),
        }, ['id']),
        _tool('hubspot_email_criar', 'Registra novo email no HubSpot', {
            'properties': _PROPS_DICT,
            'associations': _ASSOC_LIST,
        }, ['properties']),
        _tool('hubspot_email_atualizar', 'Atualiza propriedades de um email', {
            'id': _ID('email'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_email_excluir', 'Exclui um email do HubSpot', {
            'id': _ID('email'),
        }, ['id']),

        # ── Meetings (1 existing + 4 new = 5) ────────────────────────────
        _tool('hubspot_meetings_listar', 'Lista reunioes/meetings do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_meeting_obter', 'Obtem detalhes de uma reuniao', {
            'id': _ID('meeting'),
        }, ['id']),
        _tool('hubspot_meeting_criar', 'Registra nova reuniao no HubSpot', {
            'properties': _PROPS_DICT,
            'associations': _ASSOC_LIST,
        }, ['properties']),
        _tool('hubspot_meeting_atualizar', 'Atualiza propriedades de uma reuniao', {
            'id': _ID('meeting'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_meeting_excluir', 'Exclui uma reuniao do HubSpot', {
            'id': _ID('meeting'),
        }, ['id']),

        # ── Tasks (2 existing + 3 new = 5) ───────────────────────────────
        _tool('hubspot_tasks_listar', 'Lista tarefas do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_task_criar', 'Cria nova tarefa no HubSpot', {
            'subject': {'type': 'string', 'description': 'Assunto da tarefa'},
            'body': {'type': 'string', 'description': 'Descricao da tarefa'},
            'priority': {'type': 'string', 'description': 'Prioridade (LOW, MEDIUM, HIGH)'},
            'due_date': {'type': 'string', 'description': 'Data limite (YYYY-MM-DD)'},
        }, ['subject']),
        _tool('hubspot_task_obter', 'Obtem detalhes de uma tarefa', {
            'id': _ID('tarefa'),
        }, ['id']),
        _tool('hubspot_task_atualizar', 'Atualiza propriedades de uma tarefa', {
            'id': _ID('tarefa'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_task_excluir', 'Exclui uma tarefa do HubSpot', {
            'id': _ID('tarefa'),
        }, ['id']),

        # ── Products (5 new) ─────────────────────────────────────────────
        _tool('hubspot_products_listar', 'Lista produtos do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_product_obter', 'Obtem detalhes de um produto', {
            'id': _ID('produto'),
        }, ['id']),
        _tool('hubspot_product_criar', 'Cria novo produto no HubSpot', {
            'properties': _PROPS_DICT,
        }, ['properties']),
        _tool('hubspot_product_atualizar', 'Atualiza propriedades de um produto', {
            'id': _ID('produto'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_product_excluir', 'Exclui um produto do HubSpot', {
            'id': _ID('produto'),
        }, ['id']),

        # ── Associations (9 new) ─────────────────────────────────────────
        _tool('hubspot_associations_listar', 'Lista associacoes entre objetos CRM', {
            'from_type': _FROM_TYPE,
            'from_id': {'type': 'string', 'description': 'ID do objeto de origem'},
            'to_type': _TO_TYPE,
        }, ['from_type', 'from_id', 'to_type']),
        _tool('hubspot_association_criar', 'Cria associacao entre dois objetos CRM', {
            'from_type': _FROM_TYPE,
            'from_id': {'type': 'string', 'description': 'ID do objeto de origem'},
            'to_type': _TO_TYPE,
            'to_id': {'type': 'string', 'description': 'ID do objeto de destino'},
            'association_type_id': {'type': 'integer', 'description': 'ID do tipo de associacao HubSpot'},
        }, ['from_type', 'from_id', 'to_type', 'to_id', 'association_type_id']),
        _tool('hubspot_association_excluir', 'Remove associacao entre dois objetos CRM', {
            'from_type': _FROM_TYPE,
            'from_id': {'type': 'string', 'description': 'ID do objeto de origem'},
            'to_type': _TO_TYPE,
            'to_id': {'type': 'string', 'description': 'ID do objeto de destino'},
        }, ['from_type', 'from_id', 'to_type', 'to_id']),
        _tool('hubspot_associations_batch_criar', 'Cria associacoes em lote', {
            'from_type': _FROM_TYPE,
            'to_type': _TO_TYPE,
            'inputs': _BATCH_INPUTS,
        }, ['from_type', 'to_type', 'inputs']),
        _tool('hubspot_associations_batch_excluir', 'Remove associacoes em lote', {
            'from_type': _FROM_TYPE,
            'to_type': _TO_TYPE,
            'inputs': _BATCH_INPUTS,
        }, ['from_type', 'to_type', 'inputs']),
        _tool('hubspot_associations_batch_ler', 'Le associacoes em lote', {
            'from_type': _FROM_TYPE,
            'to_type': _TO_TYPE,
            'inputs': _BATCH_INPUTS_IDS,
        }, ['from_type', 'to_type', 'inputs']),
        _tool('hubspot_association_labels_listar', 'Lista labels/tipos de associacao entre objetos', {
            'from_type': _FROM_TYPE,
            'to_type': _TO_TYPE,
        }, ['from_type', 'to_type']),
        _tool('hubspot_association_label_criar', 'Cria novo label de associacao customizado', {
            'from_type': _FROM_TYPE,
            'to_type': _TO_TYPE,
            'label': {'type': 'string', 'description': 'Label da associacao'},
            'name': {'type': 'string', 'description': 'Nome interno da associacao'},
        }, ['from_type', 'to_type', 'label', 'name']),
        _tool('hubspot_association_label_excluir', 'Remove label de associacao customizado', {
            'from_type': _FROM_TYPE,
            'to_type': _TO_TYPE,
            'label_id': {'type': 'integer', 'description': 'ID do label de associacao'},
        }, ['from_type', 'to_type', 'label_id']),

        # ── Properties (2 existing + 8 new = 10) ─────────────────────────
        _tool('hubspot_properties_listar', 'Lista propriedades de um tipo de objeto', {
            'object_type': {'type': 'string', 'description': 'Tipo de objeto (deals, contacts, companies, tickets)', 'default': 'deals'},
        }),
        _tool('hubspot_property_obter', 'Obtem detalhes de uma propriedade especifica', {
            'object_type': _OBJ_TYPE,
            'property_name': {'type': 'string', 'description': 'Nome da propriedade'},
        }, ['object_type', 'property_name']),
        _tool('hubspot_property_criar', 'Cria nova propriedade customizada', {
            'object_type': _OBJ_TYPE,
            'property_def': {'type': 'object', 'description': 'Definicao da propriedade (name, label, type, fieldType, groupName)'},
        }, ['object_type', 'property_def']),
        _tool('hubspot_property_atualizar', 'Atualiza uma propriedade existente', {
            'object_type': _OBJ_TYPE,
            'property_name': {'type': 'string', 'description': 'Nome da propriedade'},
            'property_def': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['object_type', 'property_name', 'property_def']),
        _tool('hubspot_property_excluir', 'Exclui uma propriedade customizada', {
            'object_type': _OBJ_TYPE,
            'property_name': {'type': 'string', 'description': 'Nome da propriedade'},
        }, ['object_type', 'property_name']),
        _tool('hubspot_property_groups_listar', 'Lista grupos de propriedades de um tipo de objeto', {
            'object_type': _OBJ_TYPE,
        }, ['object_type']),
        _tool('hubspot_property_group_criar', 'Cria novo grupo de propriedades', {
            'object_type': _OBJ_TYPE,
            'name': {'type': 'string', 'description': 'Nome interno do grupo'},
            'label': {'type': 'string', 'description': 'Label do grupo'},
        }, ['object_type', 'name', 'label']),
        _tool('hubspot_property_group_atualizar', 'Atualiza um grupo de propriedades', {
            'object_type': _OBJ_TYPE,
            'group_name': {'type': 'string', 'description': 'Nome do grupo'},
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['object_type', 'group_name', 'body']),
        _tool('hubspot_property_group_excluir', 'Exclui um grupo de propriedades', {
            'object_type': _OBJ_TYPE,
            'group_name': {'type': 'string', 'description': 'Nome do grupo'},
        }, ['object_type', 'group_name']),

        # ── Pipelines (2 existing + 9 new = 11) ─────────────────────────
        _tool('hubspot_pipelines_listar', 'Lista pipelines/funis de deals', {
            'object_type': _PIPELINE_OBJ_TYPE,
        }),
        _tool('hubspot_pipeline_stages', 'Lista etapas/stages de todas as pipelines de deals', {}),
        _tool('hubspot_pipeline_obter', 'Obtem detalhes de uma pipeline especifica', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'pipeline_id': _PIPELINE_ID,
        }, ['object_type', 'pipeline_id']),
        _tool('hubspot_pipeline_criar', 'Cria nova pipeline', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'body': {'type': 'object', 'description': 'Definicao da pipeline (label, stages, displayOrder)'},
        }, ['object_type', 'body']),
        _tool('hubspot_pipeline_atualizar', 'Atualiza uma pipeline existente', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'pipeline_id': _PIPELINE_ID,
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['object_type', 'pipeline_id', 'body']),
        _tool('hubspot_pipeline_excluir', 'Exclui uma pipeline', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'pipeline_id': _PIPELINE_ID,
        }, ['object_type', 'pipeline_id']),
        _tool('hubspot_pipeline_stage_obter', 'Obtem detalhes de um stage de pipeline', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'pipeline_id': _PIPELINE_ID,
            'stage_id': _STAGE_ID,
        }, ['object_type', 'pipeline_id', 'stage_id']),
        _tool('hubspot_pipeline_stage_criar', 'Cria novo stage em uma pipeline', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'pipeline_id': _PIPELINE_ID,
            'body': {'type': 'object', 'description': 'Definicao do stage (label, displayOrder)'},
        }, ['object_type', 'pipeline_id', 'body']),
        _tool('hubspot_pipeline_stage_atualizar', 'Atualiza um stage de pipeline', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'pipeline_id': _PIPELINE_ID,
            'stage_id': _STAGE_ID,
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['object_type', 'pipeline_id', 'stage_id', 'body']),
        _tool('hubspot_pipeline_stage_excluir', 'Exclui um stage de pipeline', {
            'object_type': _PIPELINE_OBJ_TYPE,
            'pipeline_id': _PIPELINE_ID,
            'stage_id': _STAGE_ID,
        }, ['object_type', 'pipeline_id', 'stage_id']),
        _tool('hubspot_deal_stages_listar', 'Lista todos os stages de deals em todas as pipelines', {}),

        # ── Owners (1 existing + 1 new = 2) ──────────────────────────────
        _tool('hubspot_owners_listar', 'Lista proprietarios/owners do HubSpot', {
            'limit': {'type': 'integer', 'description': 'Limite de resultados (default 100)', 'default': 100},
        }),
        _tool('hubspot_owner_obter', 'Obtem detalhes de um owner/proprietario', {
            'id': _ID('owner'),
        }, ['id']),

        # ── CRM Search generic (1 new) ───────────────────────────────────
        _tool('hubspot_crm_search', 'Busca generica em qualquer objeto CRM com filtros avancados', {
            'object_type': _OBJ_TYPE,
            'query': {'type': 'string', 'description': 'Termo de busca (opcional)'},
            'filters': {'type': 'array', 'description': 'Lista de filtros [{propertyName, operator, value}]', 'items': {'type': 'object'}},
            'sorts': {'type': 'array', 'description': 'Lista de ordenacoes [{propertyName, direction}]', 'items': {'type': 'object'}},
            'properties': _PROPS_LIST,
            'limit': _LIMIT,
            'after': {'type': 'string', 'description': 'Cursor de paginacao'},
        }, ['object_type']),

        # ── Account/Company info (1 existing) ────────────────────────────
        _tool('hubspot_conta_info', 'Informacoes da conta/empresa conectada ao HubSpot', {}),

        # ── Search (3 existing) ──────────────────────────────────────────
        _tool('hubspot_contatos_buscar', 'Busca contatos por email, nome ou telefone', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_empresas_buscar', 'Busca empresas por nome ou dominio', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_deals_buscar', 'Busca deals por nome', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),

        # ── Forms (2 new) ────────────────────────────────────────────────
        _tool('hubspot_forms_listar', 'Lista formularios do HubSpot', {}),
        _tool('hubspot_form_obter', 'Obtem detalhes de um formulario', {
            'id': _ID('formulario'),
        }, ['id']),

        # ── Marketing Emails (2 new) ─────────────────────────────────────
        _tool('hubspot_marketing_emails_listar', 'Lista emails de marketing do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_marketing_email_obter', 'Obtem detalhes de um email de marketing', {
            'id': _ID('email de marketing'),
        }, ['id']),

        # ── Feedback Submissions (2 new) ─────────────────────────────────
        _tool('hubspot_feedback_submissions_listar', 'Lista submissoes de feedback do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_feedback_submission_obter', 'Obtem detalhes de uma submissao de feedback', {
            'id': _ID('feedback submission'),
        }, ['id']),

        # ── Custom Objects (5 new) ───────────────────────────────────────
        _tool('hubspot_custom_objects_schemas_listar', 'Lista schemas de objetos customizados', {}),
        _tool('hubspot_custom_objects_schema_obter', 'Obtem schema de um objeto customizado', {
            'object_type': _OBJ_TYPE,
        }, ['object_type']),
        _tool('hubspot_custom_objects_listar', 'Lista objetos customizados de um tipo', {
            'object_type': _OBJ_TYPE,
            'limit': _LIMIT,
        }, ['object_type']),
        _tool('hubspot_custom_objects_obter', 'Obtem um objeto customizado especifico', {
            'object_type': _OBJ_TYPE,
            'id': _ID('objeto customizado'),
        }, ['object_type', 'id']),
        _tool('hubspot_custom_objects_criar', 'Cria novo objeto customizado', {
            'object_type': _OBJ_TYPE,
            'properties': _PROPS_DICT,
        }, ['object_type', 'properties']),

        # ── Communications (2 new) ───────────────────────────────────────
        _tool('hubspot_communications_listar', 'Lista comunicacoes do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_communication_obter', 'Obtem detalhes de uma comunicacao', {
            'id': _ID('comunicacao'),
        }, ['id']),

        # ── Postal Mail (2 new) ──────────────────────────────────────────
        _tool('hubspot_postal_mail_listar', 'Lista correspondencias postais do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_postal_mail_obter', 'Obtem detalhes de uma correspondencia postal', {
            'id': _ID('postal mail'),
        }, ['id']),

        # ══════════════════════════════════════════════════════════════════
        # GRUPO A — CMS Hub (Blog, Pages, Redirects, Domains, HubDB)
        # ══════════════════════════════════════════════════════════════════

        # ── CMS Blog Posts ───────────────────────────────────────────────
        _tool('hubspot_cms_blog_posts_list', 'Lista blog posts do HubSpot CMS', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_cms_blog_post_get', 'Obtem detalhes de um blog post', {
            'id': _ID('blog post'),
        }, ['id']),
        _tool('hubspot_cms_blog_post_create', 'Cria novo blog post no CMS', {
            'body': {'type': 'object', 'description': 'Corpo do blog post'},
        }, ['body']),
        _tool('hubspot_cms_blog_post_update', 'Atualiza um blog post existente', {
            'id': _ID('blog post'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_cms_blog_post_delete', 'Exclui um blog post', {
            'id': _ID('blog post'),
        }, ['id']),
        _tool('hubspot_cms_blog_post_clone', 'Clona um blog post existente', {
            'id': _ID('blog post'),
        }, ['id']),
        _tool('hubspot_cms_blog_post_schedule', 'Agenda publicacao de um blog post', {
            'id': _ID('blog post'),
            'dateTime': {'type': 'string', 'description': 'Data/hora de publicacao ISO 8601'},
        }, ['id', 'dateTime']),
        _tool('hubspot_cms_blog_post_push_live', 'Publica blog post imediatamente', {
            'id': _ID('blog post'),
        }, ['id']),
        _tool('hubspot_cms_blog_post_reset_draft', 'Reseta blog post para rascunho', {
            'id': _ID('blog post'),
        }, ['id']),
        _tool('hubspot_cms_blog_post_batch_read', 'Le blog posts em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),
        _tool('hubspot_cms_blog_post_batch_create', 'Cria blog posts em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_cms_blog_post_batch_update', 'Atualiza blog posts em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_cms_blog_post_batch_delete', 'Exclui blog posts em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── CMS Site Pages ───────────────────────────────────────────────
        _tool('hubspot_cms_pages_list', 'Lista site pages do HubSpot CMS', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_cms_page_get', 'Obtem detalhes de uma site page', {
            'id': _ID('site page'),
        }, ['id']),
        _tool('hubspot_cms_page_create', 'Cria nova site page no CMS', {
            'body': {'type': 'object', 'description': 'Corpo da page'},
        }, ['body']),
        _tool('hubspot_cms_page_update', 'Atualiza uma site page existente', {
            'id': _ID('site page'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_cms_page_delete', 'Exclui uma site page', {
            'id': _ID('site page'),
        }, ['id']),
        _tool('hubspot_cms_page_clone', 'Clona uma site page existente', {
            'id': _ID('site page'),
        }, ['id']),
        _tool('hubspot_cms_page_push_live', 'Publica site page imediatamente', {
            'id': _ID('site page'),
        }, ['id']),
        _tool('hubspot_cms_page_schedule', 'Agenda publicacao de uma site page', {
            'id': _ID('site page'),
            'dateTime': {'type': 'string', 'description': 'Data/hora de publicacao ISO 8601'},
        }, ['id', 'dateTime']),

        # ── CMS Landing Pages ────────────────────────────────────────────
        _tool('hubspot_cms_landing_pages_list', 'Lista landing pages do HubSpot CMS', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_cms_landing_page_get', 'Obtem detalhes de uma landing page', {
            'id': _ID('landing page'),
        }, ['id']),
        _tool('hubspot_cms_landing_page_create', 'Cria nova landing page no CMS', {
            'body': {'type': 'object', 'description': 'Corpo da landing page'},
        }, ['body']),
        _tool('hubspot_cms_landing_page_update', 'Atualiza uma landing page existente', {
            'id': _ID('landing page'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_cms_landing_page_delete', 'Exclui uma landing page', {
            'id': _ID('landing page'),
        }, ['id']),
        _tool('hubspot_cms_landing_page_push_live', 'Publica landing page imediatamente', {
            'id': _ID('landing page'),
        }, ['id']),

        # ── CMS URL Redirects ────────────────────────────────────────────
        _tool('hubspot_cms_redirects_list', 'Lista URL redirects do HubSpot CMS', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_cms_redirect_get', 'Obtem detalhes de um URL redirect', {
            'id': _ID('redirect'),
        }, ['id']),
        _tool('hubspot_cms_redirect_create', 'Cria novo URL redirect no CMS', {
            'body': {'type': 'object', 'description': 'Corpo do redirect (routePrefix, destination, redirectStyle)'},
        }, ['body']),
        _tool('hubspot_cms_redirect_update', 'Atualiza um URL redirect existente', {
            'id': _ID('redirect'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_cms_redirect_delete', 'Exclui um URL redirect', {
            'id': _ID('redirect'),
        }, ['id']),

        # ── CMS Domains ──────────────────────────────────────────────────
        _tool('hubspot_cms_domains_list', 'Lista dominios do HubSpot CMS', {}),
        _tool('hubspot_cms_domain_get', 'Obtem detalhes de um dominio', {
            'id': _ID('dominio'),
        }, ['id']),

        # ── CMS Performance ──────────────────────────────────────────────
        _tool('hubspot_cms_performance_get', 'Obtem metricas de performance do CMS', {
            'domain': {'type': 'string', 'description': 'Dominio para consultar'},
            'period': {'type': 'string', 'description': 'Periodo (e.g. LAST_30_DAYS)'},
        }),

        # ── HubDB Tables ────────────────────────────────────────────────
        _tool('hubspot_hubdb_tables_list', 'Lista tabelas HubDB', {}),
        _tool('hubspot_hubdb_table_get', 'Obtem detalhes de uma tabela HubDB', {
            'id': _ID('tabela HubDB'),
        }, ['id']),
        _tool('hubspot_hubdb_table_create', 'Cria nova tabela HubDB', {
            'body': {'type': 'object', 'description': 'Definicao da tabela (name, label, columns)'},
        }, ['body']),
        _tool('hubspot_hubdb_table_delete', 'Exclui uma tabela HubDB', {
            'id': _ID('tabela HubDB'),
        }, ['id']),
        _tool('hubspot_hubdb_table_clone', 'Clona uma tabela HubDB', {
            'id': _ID('tabela HubDB'),
            'newName': {'type': 'string', 'description': 'Nome da nova tabela'},
        }, ['id', 'newName']),
        _tool('hubspot_hubdb_table_publish', 'Publica uma tabela HubDB (draft -> live)', {
            'id': _ID('tabela HubDB'),
        }, ['id']),

        # ── HubDB Rows ──────────────────────────────────────────────────
        _tool('hubspot_hubdb_rows_list', 'Lista linhas de uma tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
        }, ['table_id']),
        _tool('hubspot_hubdb_row_get', 'Obtem uma linha de tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
            'row_id': _ID('linha'),
        }, ['table_id', 'row_id']),
        _tool('hubspot_hubdb_row_create', 'Cria nova linha em tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
            'body': {'type': 'object', 'description': 'Dados da linha (values)'},
        }, ['table_id', 'body']),
        _tool('hubspot_hubdb_row_update', 'Atualiza uma linha de tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
            'row_id': _ID('linha'),
            'body': {'type': 'object', 'description': 'Dados a atualizar'},
        }, ['table_id', 'row_id', 'body']),
        _tool('hubspot_hubdb_row_delete', 'Exclui uma linha de tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
            'row_id': _ID('linha'),
        }, ['table_id', 'row_id']),
        _tool('hubspot_hubdb_rows_batch_create', 'Cria linhas em lote em tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
            'inputs': _BATCH_INPUTS,
        }, ['table_id', 'inputs']),
        _tool('hubspot_hubdb_rows_batch_update', 'Atualiza linhas em lote em tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
            'inputs': _BATCH_INPUTS,
        }, ['table_id', 'inputs']),
        _tool('hubspot_hubdb_rows_batch_delete', 'Exclui linhas em lote de tabela HubDB', {
            'table_id': _ID('tabela HubDB'),
            'inputs': _BATCH_INPUTS_IDS,
        }, ['table_id', 'inputs']),

        # ══════════════════════════════════════════════════════════════════
        # GRUPO B — Files Hub
        # ══════════════════════════════════════════════════════════════════

        _tool('hubspot_files_list', 'Lista arquivos do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_file_get', 'Obtem detalhes de um arquivo', {
            'id': _ID('arquivo'),
        }, ['id']),
        _tool('hubspot_file_upload', 'Faz upload de arquivo via URL', {
            'body': {'type': 'object', 'description': 'Dados do upload (url, folderId, options)'},
        }, ['body']),
        _tool('hubspot_file_update', 'Atualiza metadados de um arquivo', {
            'id': _ID('arquivo'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_file_delete', 'Exclui um arquivo', {
            'id': _ID('arquivo'),
        }, ['id']),
        _tool('hubspot_file_signed_url', 'Gera URL assinada para um arquivo privado', {
            'id': _ID('arquivo'),
        }, ['id']),
        _tool('hubspot_file_import_from_url', 'Importa arquivo de URL externa', {
            'body': {'type': 'object', 'description': 'Dados de importacao (url, name, folderId)'},
        }, ['body']),
        _tool('hubspot_file_folders_list', 'Lista pastas de arquivos', {}),
        _tool('hubspot_file_folders_create', 'Cria nova pasta de arquivos', {
            'body': {'type': 'object', 'description': 'Dados da pasta (name, parentFolderId)'},
        }, ['body']),
        _tool('hubspot_file_folders_update', 'Atualiza uma pasta de arquivos', {
            'id': _ID('pasta'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_file_folders_delete', 'Exclui uma pasta de arquivos', {
            'id': _ID('pasta'),
        }, ['id']),
        _tool('hubspot_file_folders_get_by_path', 'Obtem pasta por caminho', {
            'path': {'type': 'string', 'description': 'Caminho da pasta (e.g. /folder/subfolder)'},
        }, ['path']),

        # ══════════════════════════════════════════════════════════════════
        # GRUPO C — Conversations Hub
        # ══════════════════════════════════════════════════════════════════

        # ── Threads ──────────────────────────────────────────────────────
        _tool('hubspot_conv_threads_list', 'Lista threads de conversacao', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_conv_thread_get', 'Obtem detalhes de uma thread', {
            'id': _ID('thread'),
        }, ['id']),
        _tool('hubspot_conv_thread_update', 'Atualiza uma thread de conversacao', {
            'id': _ID('thread'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_conv_thread_archive', 'Arquiva uma thread de conversacao', {
            'id': _ID('thread'),
        }, ['id']),
        _tool('hubspot_conv_thread_restore', 'Restaura uma thread arquivada', {
            'id': _ID('thread'),
        }, ['id']),
        _tool('hubspot_conv_thread_delete', 'Exclui uma thread de conversacao', {
            'id': _ID('thread'),
        }, ['id']),

        # ── Messages ─────────────────────────────────────────────────────
        _tool('hubspot_conv_messages_list', 'Lista mensagens de uma thread', {
            'thread_id': _ID('thread'),
            'limit': _LIMIT,
        }, ['thread_id']),
        _tool('hubspot_conv_message_get', 'Obtem detalhes de uma mensagem', {
            'thread_id': _ID('thread'),
            'message_id': _ID('mensagem'),
        }, ['thread_id', 'message_id']),
        _tool('hubspot_conv_message_create', 'Envia mensagem em uma thread', {
            'thread_id': _ID('thread'),
            'body': {'type': 'object', 'description': 'Corpo da mensagem'},
        }, ['thread_id', 'body']),
        _tool('hubspot_conv_message_original_content', 'Obtem conteudo original de uma mensagem', {
            'thread_id': _ID('thread'),
            'message_id': _ID('mensagem'),
        }, ['thread_id', 'message_id']),

        # ── Inboxes ──────────────────────────────────────────────────────
        _tool('hubspot_conv_inboxes_list', 'Lista inboxes de conversacao', {}),
        _tool('hubspot_conv_inbox_get', 'Obtem detalhes de um inbox', {
            'id': _ID('inbox'),
        }, ['id']),
        _tool('hubspot_conv_channels_list', 'Lista canais de conversacao', {
            'inbox_id': _ID('inbox'),
        }, ['inbox_id']),

        # ══════════════════════════════════════════════════════════════════
        # GRUPO D — Marketing Hub extra
        # ══════════════════════════════════════════════════════════════════

        # ── Marketing Events ─────────────────────────────────────────────
        _tool('hubspot_marketing_events_list', 'Lista marketing events do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_marketing_event_create', 'Cria novo marketing event', {
            'body': {'type': 'object', 'description': 'Dados do evento'},
        }, ['body']),
        _tool('hubspot_marketing_event_get', 'Obtem detalhes de um marketing event', {
            'id': _ID('marketing event'),
        }, ['id']),
        _tool('hubspot_marketing_event_update', 'Atualiza um marketing event', {
            'id': _ID('marketing event'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_marketing_event_delete', 'Exclui um marketing event', {
            'id': _ID('marketing event'),
        }, ['id']),
        _tool('hubspot_marketing_event_attendances_list', 'Lista participantes de um marketing event', {
            'id': _ID('marketing event'),
        }, ['id']),
        _tool('hubspot_marketing_event_attendances_create', 'Registra participantes em marketing event', {
            'id': _ID('marketing event'),
            'body': {'type': 'object', 'description': 'Dados dos participantes'},
        }, ['id', 'body']),
        _tool('hubspot_marketing_event_cancel', 'Cancela um marketing event', {
            'id': _ID('marketing event'),
        }, ['id']),
        _tool('hubspot_marketing_event_complete', 'Marca marketing event como completo', {
            'id': _ID('marketing event'),
        }, ['id']),

        # ── Campaigns ────────────────────────────────────────────────────
        _tool('hubspot_marketing_campaigns_list', 'Lista campanhas de marketing', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_marketing_campaign_get', 'Obtem detalhes de uma campanha', {
            'id': _ID('campanha'),
        }, ['id']),
        _tool('hubspot_marketing_campaign_create', 'Cria nova campanha de marketing', {
            'body': {'type': 'object', 'description': 'Dados da campanha'},
        }, ['body']),
        _tool('hubspot_marketing_campaign_update', 'Atualiza uma campanha de marketing', {
            'id': _ID('campanha'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_marketing_campaign_delete', 'Exclui uma campanha de marketing', {
            'id': _ID('campanha'),
        }, ['id']),
        _tool('hubspot_marketing_campaign_assets_list', 'Lista assets de uma campanha', {
            'id': _ID('campanha'),
        }, ['id']),

        # ── Subscription Preferences ─────────────────────────────────────
        _tool('hubspot_subscriptions_definitions_list', 'Lista definicoes de subscription do portal', {}),
        _tool('hubspot_subscriptions_status_get', 'Obtem status de subscription de um email', {
            'email': {'type': 'string', 'description': 'Email do contato'},
        }, ['email']),
        _tool('hubspot_subscriptions_status_update', 'Atualiza status de subscription', {
            'email': {'type': 'string', 'description': 'Email do contato'},
            'body': {'type': 'object', 'description': 'Dados de subscription a atualizar'},
        }, ['email', 'body']),
        _tool('hubspot_subscriptions_unsubscribe', 'Remove inscricao de um contato', {
            'email': {'type': 'string', 'description': 'Email do contato'},
        }, ['email']),

        # ── Transactional Email ──────────────────────────────────────────
        _tool('hubspot_transactional_email_send', 'Envia email transacional via HubSpot', {
            'body': {'type': 'object', 'description': 'Dados do email (emailId, message, contactProperties)'},
        }, ['body']),

        # ══════════════════════════════════════════════════════════════════
        # GRUPO E — Settings Hub
        # ══════════════════════════════════════════════════════════════════

        # ── Users ────────────────────────────────────────────────────────
        _tool('hubspot_settings_users_list', 'Lista usuarios do portal HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_settings_user_get', 'Obtem detalhes de um usuario', {
            'id': _ID('usuario'),
        }, ['id']),
        _tool('hubspot_settings_user_create', 'Cria novo usuario no portal', {
            'body': {'type': 'object', 'description': 'Dados do usuario (email, roleId)'},
        }, ['body']),
        _tool('hubspot_settings_user_update', 'Atualiza um usuario do portal', {
            'id': _ID('usuario'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_settings_user_delete', 'Exclui um usuario do portal', {
            'id': _ID('usuario'),
        }, ['id']),

        # ── Teams ────────────────────────────────────────────────────────
        _tool('hubspot_settings_teams_list', 'Lista times/equipes do portal HubSpot', {}),
        _tool('hubspot_settings_team_get', 'Obtem detalhes de um time', {
            'id': _ID('time'),
        }, ['id']),
        _tool('hubspot_settings_team_create', 'Cria novo time no portal', {
            'body': {'type': 'object', 'description': 'Dados do time (name)'},
        }, ['body']),
        _tool('hubspot_settings_team_update', 'Atualiza um time do portal', {
            'id': _ID('time'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_settings_team_delete', 'Exclui um time do portal', {
            'id': _ID('time'),
        }, ['id']),

        # ── Business Units ───────────────────────────────────────────────
        _tool('hubspot_business_units_list', 'Lista business units do portal', {
            'userId': _ID('usuario'),
        }, ['userId']),

        # ── Currencies ───────────────────────────────────────────────────
        _tool('hubspot_currencies_list', 'Lista moedas configuradas no portal', {}),
        _tool('hubspot_currencies_update', 'Atualiza configuracao de moedas', {
            'body': {'type': 'object', 'description': 'Dados de moedas a atualizar'},
        }, ['body']),

        # ══════════════════════════════════════════════════════════════════
        # GRUPO F — Automation + Workflows
        # ══════════════════════════════════════════════════════════════════

        # ── Workflows ────────────────────────────────────────────────────
        _tool('hubspot_workflows_list', 'Lista workflows/automacoes do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_workflow_get', 'Obtem detalhes de um workflow', {
            'id': _ID('workflow'),
        }, ['id']),
        _tool('hubspot_workflow_create', 'Cria novo workflow', {
            'body': {'type': 'object', 'description': 'Definicao do workflow'},
        }, ['body']),
        _tool('hubspot_workflow_update', 'Atualiza um workflow existente', {
            'id': _ID('workflow'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_workflow_delete', 'Exclui um workflow', {
            'id': _ID('workflow'),
        }, ['id']),
        _tool('hubspot_workflow_enroll', 'Inscreve contatos em um workflow', {
            'id': _ID('workflow'),
            'body': {'type': 'object', 'description': 'Dados de inscricao (contactIds)'},
        }, ['id', 'body']),

        # ── Sequences ────────────────────────────────────────────────────
        _tool('hubspot_sequences_list', 'Lista sequences de automacao', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_sequence_get', 'Obtem detalhes de uma sequence', {
            'id': _ID('sequence'),
        }, ['id']),
        _tool('hubspot_sequence_enroll', 'Inscreve contato em uma sequence', {
            'id': _ID('sequence'),
            'body': {'type': 'object', 'description': 'Dados de inscricao (contactId, sender, etc.)'},
        }, ['id', 'body']),

        # ══════════════════════════════════════════════════════════════════
        # GRUPO G — CRM Extras (Imports, Exports, Lists, Audit)
        # ══════════════════════════════════════════════════════════════════

        # ── Imports ──────────────────────────────────────────────────────
        _tool('hubspot_imports_list', 'Lista importacoes do CRM', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_import_get', 'Obtem detalhes de uma importacao', {
            'id': _ID('importacao'),
        }, ['id']),
        _tool('hubspot_import_create', 'Inicia nova importacao no CRM', {
            'body': {'type': 'object', 'description': 'Dados da importacao'},
        }, ['body']),
        _tool('hubspot_import_cancel', 'Cancela uma importacao em andamento', {
            'id': _ID('importacao'),
        }, ['id']),
        _tool('hubspot_import_errors', 'Lista erros de uma importacao', {
            'id': _ID('importacao'),
        }, ['id']),

        # ── Exports ──────────────────────────────────────────────────────
        _tool('hubspot_exports_create', 'Inicia nova exportacao do CRM', {
            'body': {'type': 'object', 'description': 'Dados da exportacao (exportType, objectType, etc.)'},
        }, ['body']),
        _tool('hubspot_exports_status', 'Obtem status de uma exportacao', {
            'id': _ID('exportacao'),
        }, ['id']),

        # ── Lists ────────────────────────────────────────────────────────
        _tool('hubspot_lists_list', 'Lista listas do CRM', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_list_get', 'Obtem detalhes de uma lista', {
            'id': _ID('lista'),
        }, ['id']),
        _tool('hubspot_list_create', 'Cria nova lista no CRM', {
            'body': {'type': 'object', 'description': 'Dados da lista (name, objectTypeId, processingType, filterBranch)'},
        }, ['body']),
        _tool('hubspot_list_update', 'Atualiza uma lista do CRM', {
            'id': _ID('lista'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _tool('hubspot_list_delete', 'Exclui uma lista do CRM', {
            'id': _ID('lista'),
        }, ['id']),
        _tool('hubspot_list_memberships_get', 'Obtem membros de uma lista', {
            'id': _ID('lista'),
            'limit': _LIMIT,
        }, ['id']),
        _tool('hubspot_list_memberships_add', 'Adiciona membros a uma lista', {
            'id': _ID('lista'),
            'body': {'type': 'array', 'description': 'Lista de IDs de registros a adicionar', 'items': {'type': 'string'}},
        }, ['id', 'body']),
        _tool('hubspot_list_memberships_remove', 'Remove membros de uma lista', {
            'id': _ID('lista'),
            'body': {'type': 'array', 'description': 'Lista de IDs de registros a remover', 'items': {'type': 'string'}},
        }, ['id', 'body']),

        # ── Audit Logs & Behavioral Events ───────────────────────────────
        _tool('hubspot_audit_log_list', 'Lista logs de auditoria do portal', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_behavioral_events_list', 'Lista definicoes de eventos comportamentais', {}),
        _tool('hubspot_behavioral_event_send', 'Envia evento comportamental', {
            'body': {'type': 'object', 'description': 'Dados do evento (eventName, email/objectId, properties)'},
        }, ['body']),

        # ══════════════════════════════════════════════════════════════════
        # HUB 1 — Marketing Workflows & Forms v3
        # ══════════════════════════════════════════════════════════════════

        # ── Workflows Legacy v1 ──────────────────────────────────────────
        _tool('hubspot_workflows_v1_list', 'Lista workflows legacy v1', {}),
        _tool('hubspot_workflows_v1_get', 'Obtem workflow legacy v1', {
            'workflowId': _ID('workflow'),
        }, ['workflowId']),
        _tool('hubspot_workflows_v1_create', 'Cria workflow legacy v1', {
            'body': {'type': 'object', 'description': 'Definicao do workflow v1'},
        }, ['body']),
        _tool('hubspot_workflows_v1_update', 'Atualiza workflow legacy v1', {
            'workflowId': _ID('workflow'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['workflowId', 'body']),
        _tool('hubspot_workflows_v1_delete', 'Exclui workflow legacy v1', {
            'workflowId': _ID('workflow'),
        }, ['workflowId']),
        _tool('hubspot_workflows_v1_enroll', 'Inscreve contato em workflow legacy v1', {
            'workflowId': _ID('workflow'),
            'email': {'type': 'string', 'description': 'Email do contato'},
        }, ['workflowId', 'email']),
        _tool('hubspot_workflows_v1_unenroll', 'Remove contato de workflow legacy v1', {
            'workflowId': _ID('workflow'),
            'email': {'type': 'string', 'description': 'Email do contato'},
        }, ['workflowId', 'email']),
        _tool('hubspot_workflows_v1_enrollments_list', 'Lista workflows em que um contato esta inscrito', {
            'email': {'type': 'string', 'description': 'Email do contato'},
        }, ['email']),

        # ── Forms v3 ────────────────────────────────────────────────────
        _tool('hubspot_forms_v3_list', 'Lista forms v3 do marketing', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_forms_v3_get', 'Obtem form v3 por ID', {
            'formId': _ID('form'),
        }, ['formId']),
        _tool('hubspot_forms_v3_create', 'Cria form v3', {
            'body': {'type': 'object', 'description': 'Definicao do form'},
        }, ['body']),
        _tool('hubspot_forms_v3_update', 'Atualiza form v3', {
            'formId': _ID('form'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['formId', 'body']),
        _tool('hubspot_forms_v3_archive', 'Arquiva form v3', {
            'formId': _ID('form'),
        }, ['formId']),
        _tool('hubspot_forms_v3_submissions_list', 'Lista submissions de um form v3', {
            'formId': _ID('form'),
            'limit': _LIMIT,
        }, ['formId']),
        _tool('hubspot_forms_v3_submissions_get', 'Obtem submission especifica de form v3', {
            'formId': _ID('form'),
            'submissionId': _ID('submission'),
        }, ['formId', 'submissionId']),
        _tool('hubspot_forms_v3_fields_list', 'Lista campos de um form v3', {
            'formId': _ID('form'),
        }, ['formId']),
        _tool('hubspot_forms_v3_field_create', 'Cria campo em form v3', {
            'formId': _ID('form'),
            'body': {'type': 'object', 'description': 'Definicao do campo'},
        }, ['formId', 'body']),
        _tool('hubspot_forms_v3_field_update', 'Atualiza campo de form v3', {
            'formId': _ID('form'),
            'fieldId': _ID('campo'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['formId', 'fieldId', 'body']),
        _tool('hubspot_forms_v3_field_delete', 'Exclui campo de form v3', {
            'formId': _ID('form'),
            'fieldId': _ID('campo'),
        }, ['formId', 'fieldId']),

        # ── Email Marketing Stats ───────────────────────────────────────
        _tool('hubspot_email_stats_summary', 'Resumo de estatisticas de email marketing', {}),
        _tool('hubspot_email_stats_list', 'Lista estatisticas de emails marketing', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_email_stats_histogram', 'Histograma de estatisticas de um email', {
            'emailId': _ID('email'),
        }, ['emailId']),
        _tool('hubspot_email_preview', 'Preview de um email marketing', {
            'emailId': _ID('email'),
        }, ['emailId']),

        # ── Marketing Emails extras ─────────────────────────────────────
        _tool('hubspot_marketing_email_create', 'Cria email marketing v3', {
            'body': {'type': 'object', 'description': 'Definicao do email'},
        }, ['body']),
        _tool('hubspot_marketing_email_update', 'Atualiza email marketing v3', {
            'emailId': _ID('email'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['emailId', 'body']),
        _tool('hubspot_marketing_email_archive', 'Arquiva email marketing v3', {
            'emailId': _ID('email'),
        }, ['emailId']),
        _tool('hubspot_marketing_email_clone', 'Clona email marketing v3', {
            'emailId': _ID('email'),
        }, ['emailId']),
        _tool('hubspot_marketing_email_send_test', 'Envia email de teste', {
            'emailId': _ID('email'),
            'body': {'type': 'object', 'description': 'Dados do teste (emailAddress)'},
        }, ['emailId', 'body']),
        _tool('hubspot_marketing_email_schedule', 'Agenda envio de email marketing', {
            'emailId': _ID('email'),
            'body': {'type': 'object', 'description': 'Dados de agendamento (scheduledDate)'},
        }, ['emailId', 'body']),
        _tool('hubspot_marketing_email_unschedule', 'Cancela agendamento de email marketing', {
            'emailId': _ID('email'),
        }, ['emailId']),

        # ── Lists v3 extras ─────────────────────────────────────────────
        _tool('hubspot_lists_search', 'Busca listas por nome/tipo', {
            'body': {'type': 'object', 'description': 'Criterios de busca (query, listType)'},
        }, ['body']),
        _tool('hubspot_list_memberships_count', 'Conta membros de uma lista', {
            'id': _ID('lista'),
        }, ['id']),
        _tool('hubspot_lists_batch_read', 'Le listas em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),
        _tool('hubspot_lists_batch_archive', 'Arquiva listas em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),
        _tool('hubspot_lists_folders_list', 'Lista pastas de listas', {}),
        _tool('hubspot_lists_folders_create', 'Cria pasta de listas', {
            'body': {'type': 'object', 'description': 'Dados da pasta (name)'},
        }, ['body']),

        # ══════════════════════════════════════════════════════════════════
        # HUB 2 — Automation Sequences full
        # ══════════════════════════════════════════════════════════════════

        # ── Sequences v4 extras ─────────────────────────────────────────
        _tool('hubspot_sequences_create', 'Cria nova sequence de automacao', {
            'body': {'type': 'object', 'description': 'Definicao da sequence'},
        }, ['body']),
        _tool('hubspot_sequences_update', 'Atualiza sequence de automacao', {
            'sequenceId': _ID('sequence'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['sequenceId', 'body']),
        _tool('hubspot_sequences_delete', 'Exclui sequence de automacao', {
            'sequenceId': _ID('sequence'),
        }, ['sequenceId']),
        _tool('hubspot_sequences_steps_list', 'Lista steps de uma sequence', {
            'sequenceId': _ID('sequence'),
        }, ['sequenceId']),
        _tool('hubspot_sequences_steps_create', 'Cria step em sequence', {
            'sequenceId': _ID('sequence'),
            'body': {'type': 'object', 'description': 'Definicao do step'},
        }, ['sequenceId', 'body']),
        _tool('hubspot_sequences_steps_update', 'Atualiza step de sequence', {
            'sequenceId': _ID('sequence'),
            'stepId': _ID('step'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['sequenceId', 'stepId', 'body']),
        _tool('hubspot_sequences_steps_delete', 'Exclui step de sequence', {
            'sequenceId': _ID('sequence'),
            'stepId': _ID('step'),
        }, ['sequenceId', 'stepId']),

        # ── Sequence Enrollments v4 ─────────────────────────────────────
        _tool('hubspot_sequence_enrollments_list', 'Lista enrollments de sequences', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_sequence_enrollment_get', 'Obtem enrollment de sequence', {
            'enrollmentId': _ID('enrollment'),
        }, ['enrollmentId']),
        _tool('hubspot_sequence_enroll_contact', 'Inscreve contato em sequence v4', {
            'sequenceId': _ID('sequence'),
            'body': {'type': 'object', 'description': 'Dados de inscricao (contactId, sender, etc.)'},
        }, ['sequenceId', 'body']),
        _tool('hubspot_sequence_unenroll', 'Remove contato de sequence', {
            'enrollmentId': _ID('enrollment'),
        }, ['enrollmentId']),
        _tool('hubspot_sequence_enrollment_pause', 'Pausa enrollment de sequence', {
            'enrollmentId': _ID('enrollment'),
        }, ['enrollmentId']),
        _tool('hubspot_sequence_enrollment_resume', 'Retoma enrollment de sequence', {
            'enrollmentId': _ID('enrollment'),
        }, ['enrollmentId']),

        # ── Custom Workflow Actions ─────────────────────────────────────
        _tool('hubspot_workflow_actions_list', 'Lista custom actions de workflow de um app', {
            'appId': _ID('app'),
        }, ['appId']),
        _tool('hubspot_workflow_actions_get', 'Obtem custom action de workflow', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
        }, ['appId', 'definitionId']),
        _tool('hubspot_workflow_actions_create', 'Cria custom action de workflow', {
            'appId': _ID('app'),
            'body': {'type': 'object', 'description': 'Definicao da action'},
        }, ['appId', 'body']),
        _tool('hubspot_workflow_actions_update', 'Atualiza custom action de workflow', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['appId', 'definitionId', 'body']),
        _tool('hubspot_workflow_actions_delete', 'Exclui custom action de workflow', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
        }, ['appId', 'definitionId']),
        _tool('hubspot_workflow_actions_revisions_list', 'Lista revisoes de custom action', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
        }, ['appId', 'definitionId']),
        _tool('hubspot_workflow_actions_functions_list', 'Lista functions de custom action', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
        }, ['appId', 'definitionId']),
        _tool('hubspot_workflow_actions_function_get', 'Obtem function de custom action', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
            'functionType': {'type': 'string', 'description': 'Tipo da function'},
        }, ['appId', 'definitionId', 'functionType']),
        _tool('hubspot_workflow_actions_function_upsert', 'Cria/atualiza function de custom action', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
            'functionType': {'type': 'string', 'description': 'Tipo da function'},
            'body': {'type': 'object', 'description': 'Definicao da function'},
        }, ['appId', 'definitionId', 'functionType', 'body']),
        _tool('hubspot_workflow_actions_function_delete', 'Exclui function de custom action', {
            'appId': _ID('app'),
            'definitionId': _ID('definition'),
            'functionType': {'type': 'string', 'description': 'Tipo da function'},
        }, ['appId', 'definitionId', 'functionType']),

        # ══════════════════════════════════════════════════════════════════
        # HUB 3 — CMS Source Code + Templates
        # ══════════════════════════════════════════════════════════════════

        # ── Source Code Files ───────────────────────────────────────────
        _tool('hubspot_cms_source_list', 'Lista arquivos source code do CMS', {
            'environment': {'type': 'string', 'description': 'Ambiente (draft, published)', 'default': 'draft'},
            'path': {'type': 'string', 'description': 'Caminho raiz', 'default': '/'},
        }),
        _tool('hubspot_cms_source_get', 'Obtem conteudo de arquivo source code CMS', {
            'environment': {'type': 'string', 'description': 'Ambiente (draft, published)', 'default': 'draft'},
            'path': {'type': 'string', 'description': 'Caminho do arquivo'},
        }, ['path']),
        _tool('hubspot_cms_source_create', 'Cria arquivo source code no CMS', {
            'environment': {'type': 'string', 'description': 'Ambiente', 'default': 'draft'},
            'path': {'type': 'string', 'description': 'Caminho do arquivo'},
            'body': {'type': 'string', 'description': 'Conteudo do arquivo'},
        }, ['path', 'body']),
        _tool('hubspot_cms_source_update', 'Atualiza arquivo source code no CMS', {
            'environment': {'type': 'string', 'description': 'Ambiente', 'default': 'draft'},
            'path': {'type': 'string', 'description': 'Caminho do arquivo'},
            'body': {'type': 'string', 'description': 'Novo conteudo'},
        }, ['path', 'body']),
        _tool('hubspot_cms_source_delete', 'Exclui arquivo source code do CMS', {
            'environment': {'type': 'string', 'description': 'Ambiente', 'default': 'draft'},
            'path': {'type': 'string', 'description': 'Caminho do arquivo'},
        }, ['path']),
        _tool('hubspot_cms_source_metadata', 'Obtem metadata de arquivo source code CMS', {
            'environment': {'type': 'string', 'description': 'Ambiente', 'default': 'draft'},
            'path': {'type': 'string', 'description': 'Caminho do arquivo'},
        }, ['path']),
        _tool('hubspot_cms_source_validate', 'Valida arquivo source code CMS', {
            'environment': {'type': 'string', 'description': 'Ambiente', 'default': 'draft'},
            'path': {'type': 'string', 'description': 'Caminho do arquivo'},
        }, ['path']),

        # ── Templates (Design Manager) ──────────────────────────────────
        _tool('hubspot_cms_templates_list', 'Lista templates do CMS (design manager)', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_cms_template_get', 'Obtem template do CMS', {
            'template_id': _ID('template'),
        }, ['template_id']),
        _tool('hubspot_cms_template_create', 'Cria template no CMS', {
            'body': {'type': 'object', 'description': 'Definicao do template'},
        }, ['body']),
        _tool('hubspot_cms_template_update', 'Atualiza template do CMS', {
            'template_id': _ID('template'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['template_id', 'body']),
        _tool('hubspot_cms_template_delete', 'Exclui template do CMS', {
            'template_id': _ID('template'),
        }, ['template_id']),

        # ── Themes ──────────────────────────────────────────────────────
        _tool('hubspot_cms_themes_list', 'Lista temas do CMS', {}),
        _tool('hubspot_cms_theme_get', 'Obtem tema do CMS', {
            'themeId': _ID('tema'),
        }, ['themeId']),
        _tool('hubspot_cms_theme_settings_get', 'Obtem configuracoes de tema', {
            'themeId': _ID('tema'),
        }, ['themeId']),
        _tool('hubspot_cms_theme_settings_update', 'Atualiza configuracoes de tema', {
            'themeId': _ID('tema'),
            'body': {'type': 'object', 'description': 'Settings a atualizar'},
        }, ['themeId', 'body']),
        _tool('hubspot_cms_theme_fields_list', 'Lista campos de tema', {
            'themeId': _ID('tema'),
        }, ['themeId']),

        # ── Site Search ─────────────────────────────────────────────────
        _tool('hubspot_cms_site_search', 'Busca no site via CMS', {
            'q': {'type': 'string', 'description': 'Termo de busca'},
            'type': {'type': 'string', 'description': 'Tipo (LANDING_PAGE, BLOG_POST, SITE_PAGE, etc.)'},
            'limit': _LIMIT,
        }, ['q']),
        _tool('hubspot_cms_site_search_index_status', 'Status de indexacao de conteudo', {
            'contentId': _ID('conteudo'),
        }, ['contentId']),

        # ── Blog Authors ────────────────────────────────────────────────
        _tool('hubspot_cms_blog_authors_list', 'Lista autores do blog CMS', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_cms_blog_author_get', 'Obtem autor do blog', {
            'authorId': _ID('autor'),
        }, ['authorId']),
        _tool('hubspot_cms_blog_author_create', 'Cria autor de blog', {
            'body': {'type': 'object', 'description': 'Dados do autor'},
        }, ['body']),
        _tool('hubspot_cms_blog_author_update', 'Atualiza autor de blog', {
            'authorId': _ID('autor'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['authorId', 'body']),
        _tool('hubspot_cms_blog_author_delete', 'Exclui autor de blog', {
            'authorId': _ID('autor'),
        }, ['authorId']),

        # ── Blog Tags ───────────────────────────────────────────────────
        _tool('hubspot_cms_blog_tags_list', 'Lista tags do blog CMS', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_cms_blog_tag_get', 'Obtem tag do blog', {
            'tagId': _ID('tag'),
        }, ['tagId']),
        _tool('hubspot_cms_blog_tag_create', 'Cria tag de blog', {
            'body': {'type': 'object', 'description': 'Dados da tag'},
        }, ['body']),
        _tool('hubspot_cms_blog_tag_update', 'Atualiza tag de blog', {
            'tagId': _ID('tag'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['tagId', 'body']),
        _tool('hubspot_cms_blog_tag_delete', 'Exclui tag de blog', {
            'tagId': _ID('tag'),
        }, ['tagId']),

        # ── Crawling/Audit ──────────────────────────────────────────────
        _tool('hubspot_cms_audit_logs_list', 'Lista audit logs do CMS', {
            'limit': _LIMIT,
            'objectType': {'type': 'string', 'description': 'Tipo de objeto para filtrar'},
        }),
        _tool('hubspot_cms_content_audit', 'Auditoria de conteudo CMS', {}),

        # ══════════════════════════════════════════════════════════════════
        # HUB 4 — Analytics & Custom Behavioral Events
        # ══════════════════════════════════════════════════════════════════

        # ── Event Definitions ───────────────────────────────────────────
        _tool('hubspot_events_definitions_list', 'Lista definicoes de eventos custom', {}),
        _tool('hubspot_events_definition_get', 'Obtem definicao de evento custom', {
            'eventName': {'type': 'string', 'description': 'Nome do evento'},
        }, ['eventName']),
        _tool('hubspot_events_definition_create', 'Cria definicao de evento custom', {
            'body': {'type': 'object', 'description': 'Definicao do evento'},
        }, ['body']),
        _tool('hubspot_events_definition_update', 'Atualiza definicao de evento custom', {
            'eventName': {'type': 'string', 'description': 'Nome do evento'},
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['eventName', 'body']),
        _tool('hubspot_events_definition_delete', 'Exclui definicao de evento custom', {
            'eventName': {'type': 'string', 'description': 'Nome do evento'},
        }, ['eventName']),
        _tool('hubspot_events_definition_properties_list', 'Lista propriedades de evento custom', {
            'eventName': {'type': 'string', 'description': 'Nome do evento'},
        }, ['eventName']),
        _tool('hubspot_events_definition_property_create', 'Cria propriedade de evento custom', {
            'eventName': {'type': 'string', 'description': 'Nome do evento'},
            'body': {'type': 'object', 'description': 'Definicao da propriedade'},
        }, ['eventName', 'body']),
        _tool('hubspot_events_definition_property_update', 'Atualiza propriedade de evento custom', {
            'eventName': {'type': 'string', 'description': 'Nome do evento'},
            'propertyName': {'type': 'string', 'description': 'Nome da propriedade'},
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['eventName', 'propertyName', 'body']),
        _tool('hubspot_events_definition_property_delete', 'Exclui propriedade de evento custom', {
            'eventName': {'type': 'string', 'description': 'Nome do evento'},
            'propertyName': {'type': 'string', 'description': 'Nome da propriedade'},
        }, ['eventName', 'propertyName']),

        # ── Fire behavioral events ──────────────────────────────────────
        _tool('hubspot_events_send_v3', 'Envia evento comportamental v3', {
            'body': {'type': 'object', 'description': 'Dados do evento (eventName, objectId, properties)'},
        }, ['body']),

        # ── Analytics Reporting ─────────────────────────────────────────
        _tool('hubspot_analytics_reports_list', 'Lista reports de analytics', {}),
        _tool('hubspot_analytics_events_list', 'Lista eventos de analytics por objeto', {
            'objectType': {'type': 'string', 'description': 'Tipo de objeto (contacts, companies, etc.)'},
            'objectId': _ID('objeto'),
        }, ['objectType', 'objectId']),
        _tool('hubspot_analytics_web_analytics', 'Obtem web analytics por periodo', {
            'start': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'},
            'end': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
        }, ['start', 'end']),
        _tool('hubspot_analytics_contact_events', 'Lista eventos de um contato', {
            'contactId': _ID('contato'),
        }, ['contactId']),

        # ── Goals ───────────────────────────────────────────────────────
        _tool('hubspot_goals_list', 'Lista metas/goals do CRM', {}),
        _tool('hubspot_goal_get', 'Obtem meta/goal por ID', {
            'goalTargetId': _ID('goal'),
        }, ['goalTargetId']),
        _tool('hubspot_goal_create', 'Cria meta/goal no CRM', {
            'body': {'type': 'object', 'description': 'Definicao da meta'},
        }, ['body']),
        _tool('hubspot_goal_update', 'Atualiza meta/goal', {
            'goalTargetId': _ID('goal'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['goalTargetId', 'body']),
        _tool('hubspot_goal_delete', 'Exclui meta/goal', {
            'goalTargetId': _ID('goal'),
        }, ['goalTargetId']),

        # ══════════════════════════════════════════════════════════════════
        # HUB 5 — OAuth & App Info
        # ══════════════════════════════════════════════════════════════════

        _tool('hubspot_oauth_token_info', 'Obtem informacoes de um access token OAuth', {
            'token': {'type': 'string', 'description': 'Access token'},
        }, ['token']),
        _tool('hubspot_oauth_refresh', 'Renova access token via refresh token', {
            'refresh_token': {'type': 'string', 'description': 'Refresh token'},
            'client_id': {'type': 'string', 'description': 'Client ID do app'},
            'client_secret': {'type': 'string', 'description': 'Client secret do app'},
        }, ['refresh_token', 'client_id', 'client_secret']),
        _tool('hubspot_oauth_revoke', 'Revoga refresh token', {
            'token': {'type': 'string', 'description': 'Refresh token a revogar'},
        }, ['token']),
        _tool('hubspot_app_info_get', 'Obtem info da conta via private app token', {}),
        _tool('hubspot_integrations_installed_apps', 'Lista apps instalados na conta', {}),

        # ── Webhooks Subscriptions v3 ───────────────────────────────────
        _tool('hubspot_webhooks_app_settings_get', 'Obtem settings de webhooks do app', {
            'appId': _ID('app'),
        }, ['appId']),
        _tool('hubspot_webhooks_app_settings_update', 'Atualiza settings de webhooks do app', {
            'appId': _ID('app'),
            'body': {'type': 'object', 'description': 'Settings a atualizar (targetUrl, throttling)'},
        }, ['appId', 'body']),
        _tool('hubspot_webhooks_subscriptions_list', 'Lista subscriptions de webhooks do app', {
            'appId': _ID('app'),
        }, ['appId']),
        _tool('hubspot_webhooks_subscription_get', 'Obtem subscription de webhook', {
            'appId': _ID('app'),
            'subscriptionId': _ID('subscription'),
        }, ['appId', 'subscriptionId']),
        _tool('hubspot_webhooks_subscription_create', 'Cria subscription de webhook', {
            'appId': _ID('app'),
            'body': {'type': 'object', 'description': 'Definicao da subscription'},
        }, ['appId', 'body']),
        _tool('hubspot_webhooks_subscription_update', 'Atualiza subscription de webhook', {
            'appId': _ID('app'),
            'subscriptionId': _ID('subscription'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['appId', 'subscriptionId', 'body']),
        _tool('hubspot_webhooks_subscription_delete', 'Exclui subscription de webhook', {
            'appId': _ID('app'),
            'subscriptionId': _ID('subscription'),
        }, ['appId', 'subscriptionId']),
        _tool('hubspot_webhooks_subscriptions_batch_update', 'Atualiza subscriptions de webhook em lote', {
            'appId': _ID('app'),
            'inputs': _BATCH_INPUTS,
        }, ['appId', 'inputs']),

        # ══════════════════════════════════════════════════════════════════
        # HUB 6 — Settings (Users/Permissions/Roles full)
        # ══════════════════════════════════════════════════════════════════

        _tool('hubspot_settings_users_batch_create', 'Cria usuarios em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_settings_users_batch_update', 'Atualiza usuarios em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_settings_user_roles_list', 'Lista roles de um usuario', {
            'userId': _ID('usuario'),
        }, ['userId']),
        _tool('hubspot_settings_user_teams_list', 'Lista teams de um usuario', {
            'userId': _ID('usuario'),
        }, ['userId']),

        # ── Permission Sets ─────────────────────────────────────────────
        _tool('hubspot_permission_sets_list', 'Lista permission sets/roles do portal', {}),
        _tool('hubspot_permission_set_get', 'Obtem permission set/role por ID', {
            'roleId': _ID('role'),
        }, ['roleId']),
        _tool('hubspot_permission_set_create', 'Cria permission set/role', {
            'body': {'type': 'object', 'description': 'Definicao do role'},
        }, ['body']),
        _tool('hubspot_permission_set_delete', 'Exclui permission set/role', {
            'roleId': _ID('role'),
        }, ['roleId']),

        # ── Account Info ────────────────────────────────────────────────
        _tool('hubspot_account_info_get', 'Obtem detalhes da conta HubSpot', {}),
        _tool('hubspot_account_info_api_usage', 'Obtem uso diario da API', {}),
        _tool('hubspot_account_info_api_limits', 'Obtem limites mensais da API', {}),

        # ── Account Activity ────────────────────────────────────────────
        _tool('hubspot_account_activity_login_list', 'Lista atividade de login', {}),
        _tool('hubspot_account_activity_security_list', 'Lista atividade de seguranca', {}),

        # ── CRM Property Options extras ─────────────────────────────────
        _tool('hubspot_property_options_list', 'Lista opcoes de uma propriedade', {
            'objectType': _OBJ_TYPE,
            'propertyName': {'type': 'string', 'description': 'Nome da propriedade'},
        }, ['objectType', 'propertyName']),
        _tool('hubspot_property_options_create', 'Cria opcao em propriedade', {
            'objectType': _OBJ_TYPE,
            'propertyName': {'type': 'string', 'description': 'Nome da propriedade'},
            'body': {'type': 'object', 'description': 'Dados da opcao (label, value)'},
        }, ['objectType', 'propertyName', 'body']),
        _tool('hubspot_property_options_update', 'Atualiza opcao de propriedade', {
            'objectType': _OBJ_TYPE,
            'propertyName': {'type': 'string', 'description': 'Nome da propriedade'},
            'optionId': _ID('opcao'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['objectType', 'propertyName', 'optionId', 'body']),
        _tool('hubspot_property_options_delete', 'Exclui opcao de propriedade', {
            'objectType': _OBJ_TYPE,
            'propertyName': {'type': 'string', 'description': 'Nome da propriedade'},
            'optionId': _ID('opcao'),
        }, ['objectType', 'propertyName', 'optionId']),

        # ══════════════════════════════════════════════════════════════════
        # HUB 7 — Service Hub / Knowledge Base
        # ══════════════════════════════════════════════════════════════════

        # ── Knowledge Base Articles ─────────────────────────────────────
        _tool('hubspot_kb_articles_list', 'Lista artigos da knowledge base', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_kb_article_get', 'Obtem artigo da knowledge base', {
            'articleId': _ID('artigo'),
        }, ['articleId']),
        _tool('hubspot_kb_article_create', 'Cria artigo na knowledge base', {
            'body': {'type': 'object', 'description': 'Dados do artigo'},
        }, ['body']),
        _tool('hubspot_kb_article_update', 'Atualiza artigo da knowledge base', {
            'articleId': _ID('artigo'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['articleId', 'body']),
        _tool('hubspot_kb_article_delete', 'Exclui artigo da knowledge base', {
            'articleId': _ID('artigo'),
        }, ['articleId']),
        _tool('hubspot_kb_article_publish', 'Publica artigo da knowledge base', {
            'articleId': _ID('artigo'),
        }, ['articleId']),
        _tool('hubspot_kb_article_clone', 'Clona artigo da knowledge base', {
            'articleId': _ID('artigo'),
        }, ['articleId']),
        _tool('hubspot_kb_articles_batch_archive', 'Arquiva artigos em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── Knowledge Base Categories ───────────────────────────────────
        _tool('hubspot_kb_categories_list', 'Lista categorias da knowledge base', {}),
        _tool('hubspot_kb_category_get', 'Obtem categoria da knowledge base', {
            'categoryId': _ID('categoria'),
        }, ['categoryId']),
        _tool('hubspot_kb_category_create', 'Cria categoria na knowledge base', {
            'body': {'type': 'object', 'description': 'Dados da categoria'},
        }, ['body']),
        _tool('hubspot_kb_category_update', 'Atualiza categoria da knowledge base', {
            'categoryId': _ID('categoria'),
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['categoryId', 'body']),
        _tool('hubspot_kb_category_delete', 'Exclui categoria da knowledge base', {
            'categoryId': _ID('categoria'),
        }, ['categoryId']),

        # ── Feedback Surveys ────────────────────────────────────────────
        _tool('hubspot_feedback_surveys_list', 'Lista dashboards de feedback/NPS', {}),
        _tool('hubspot_feedback_survey_responses', 'Lista respostas de feedback survey', {
            'startDate': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'},
            'endDate': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
        }, ['startDate', 'endDate']),

        # ── Conversations Custom Channels ───────────────────────────────
        _tool('hubspot_conv_custom_channels_list', 'Lista custom channels de conversacao', {}),
        _tool('hubspot_conv_custom_channel_create', 'Cria custom channel de conversacao', {
            'body': {'type': 'object', 'description': 'Dados do channel'},
        }, ['body']),
        _tool('hubspot_conv_custom_channel_get', 'Obtem custom channel de conversacao', {
            'channelId': _ID('channel'),
        }, ['channelId']),
        _tool('hubspot_conv_custom_channel_delete', 'Exclui custom channel de conversacao', {
            'channelId': _ID('channel'),
        }, ['channelId']),
        _tool('hubspot_conv_channel_account_create', 'Cria channel account em custom channel', {
            'channelId': _ID('channel'),
            'body': {'type': 'object', 'description': 'Dados da channel account'},
        }, ['channelId', 'body']),

        # ══════════════════════════════════════════════════════════════════
        # HUB 8 — CRM extras finais
        # ══════════════════════════════════════════════════════════════════

        # ── Products extras ─────────────────────────────────────────────
        _tool('hubspot_products_search', 'Busca products no CRM', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_products_batch_create', 'Cria products em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_products_batch_update', 'Atualiza products em lote', {
            'inputs': _BATCH_INPUTS,
        }, ['inputs']),
        _tool('hubspot_products_batch_archive', 'Arquiva products em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),
        _tool('hubspot_products_batch_read', 'Le products em lote', {
            'inputs': _BATCH_INPUTS_IDS,
        }, ['inputs']),

        # ── Quotes extras ──────────────────────────────────────────────
        _tool('hubspot_quotes_search', 'Busca quotes no CRM', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_quotes_associations_list', 'Lista associacoes de um quote', {
            'quoteId': _ID('quote'),
            'toObjectType': _TO_TYPE,
        }, ['quoteId', 'toObjectType']),
        _tool('hubspot_quotes_associations_create', 'Cria associacao de quote', {
            'quoteId': _ID('quote'),
            'toObjectType': _TO_TYPE,
            'toObjectId': _ID('objeto destino'),
            'associationTypeId': {'type': 'string', 'description': 'ID do tipo de associacao'},
        }, ['quoteId', 'toObjectType', 'toObjectId', 'associationTypeId']),
        _tool('hubspot_quote_approve', 'Aprova um quote (muda status p/ APPROVED)', {
            'quoteId': _ID('quote'),
        }, ['quoteId']),

        # ── Line Items extras ──────────────────────────────────────────
        _tool('hubspot_lineitems_search', 'Busca line items no CRM', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_lineitems_associations', 'Lista associacoes de um line item', {
            'lineItemId': _ID('line item'),
            'toObjectType': _TO_TYPE,
        }, ['lineItemId', 'toObjectType']),

        # ── Postal Mail extras ─────────────────────────────────────────
        _tool('hubspot_postal_mail_create', 'Cria postal mail no CRM', {
            'properties': _PROPS_DICT,
        }, ['properties']),
        _tool('hubspot_postal_mail_update', 'Atualiza postal mail', {
            'postalMailId': _ID('postal mail'),
            'properties': _PROPS_DICT,
        }, ['postalMailId', 'properties']),
        _tool('hubspot_postal_mail_delete', 'Exclui postal mail', {
            'postalMailId': _ID('postal mail'),
        }, ['postalMailId']),

        # ── Calls extras ───────────────────────────────────────────────
        _tool('hubspot_calls_update', 'Atualiza call no CRM', {
            'callId': _ID('call'),
            'properties': _PROPS_DICT,
        }, ['callId', 'properties']),
        _tool('hubspot_calls_delete', 'Exclui call no CRM', {
            'callId': _ID('call'),
        }, ['callId']),
        _tool('hubspot_calls_search', 'Busca calls no CRM', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),

        # ── Emails extras ──────────────────────────────────────────────
        _tool('hubspot_emails_create', 'Cria email engagement no CRM', {
            'properties': _PROPS_DICT,
        }, ['properties']),
        _tool('hubspot_emails_update', 'Atualiza email engagement', {
            'emailId': _ID('email'),
            'properties': _PROPS_DICT,
        }, ['emailId', 'properties']),
        _tool('hubspot_emails_delete', 'Exclui email engagement', {
            'emailId': _ID('email'),
        }, ['emailId']),
        _tool('hubspot_emails_search', 'Busca emails engagement no CRM', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),

        # ── Meetings extras ────────────────────────────────────────────
        _tool('hubspot_meetings_create', 'Cria meeting no CRM', {
            'properties': _PROPS_DICT,
        }, ['properties']),
        _tool('hubspot_meetings_update', 'Atualiza meeting no CRM', {
            'meetingId': _ID('meeting'),
            'properties': _PROPS_DICT,
        }, ['meetingId', 'properties']),
        _tool('hubspot_meetings_delete', 'Exclui meeting no CRM', {
            'meetingId': _ID('meeting'),
        }, ['meetingId']),
        _tool('hubspot_meetings_search', 'Busca meetings no CRM', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),

        # ── Notes extras ───────────────────────────────────────────────
        _tool('hubspot_notes_update', 'Atualiza note no CRM', {
            'noteId': _ID('note'),
            'properties': _PROPS_DICT,
        }, ['noteId', 'properties']),
        _tool('hubspot_notes_delete', 'Exclui note no CRM', {
            'noteId': _ID('note'),
        }, ['noteId']),
        _tool('hubspot_notes_search', 'Busca notes no CRM', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),

        # ── Custom Objects extras ──────────────────────────────────────
        _tool('hubspot_custom_objects_update', 'Atualiza custom object', {
            'objectType': _OBJ_TYPE,
            'objectId': _ID('objeto'),
            'properties': _PROPS_DICT,
        }, ['objectType', 'objectId', 'properties']),
        _tool('hubspot_custom_objects_delete', 'Exclui custom object', {
            'objectType': _OBJ_TYPE,
            'objectId': _ID('objeto'),
        }, ['objectType', 'objectId']),
        _tool('hubspot_custom_objects_search', 'Busca custom objects', {
            'objectType': _OBJ_TYPE,
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['objectType', 'query']),
        _tool('hubspot_custom_objects_batch_create', 'Cria custom objects em lote', {
            'objectType': _OBJ_TYPE,
            'inputs': _BATCH_INPUTS,
        }, ['objectType', 'inputs']),
        _tool('hubspot_custom_objects_batch_update', 'Atualiza custom objects em lote', {
            'objectType': _OBJ_TYPE,
            'inputs': _BATCH_INPUTS,
        }, ['objectType', 'inputs']),
        _tool('hubspot_custom_objects_schema_create', 'Cria schema de custom object', {
            'body': {'type': 'object', 'description': 'Definicao do schema'},
        }, ['body']),
        _tool('hubspot_custom_objects_schema_update', 'Atualiza schema de custom object', {
            'objectType': _OBJ_TYPE,
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['objectType', 'body']),
        _tool('hubspot_custom_objects_schema_delete', 'Exclui schema de custom object', {
            'objectType': _OBJ_TYPE,
        }, ['objectType']),
        _tool('hubspot_custom_objects_schema_labels', 'Atualiza labels de schema custom object', {
            'objectType': _OBJ_TYPE,
            'body': {'type': 'object', 'description': 'Labels a atualizar'},
        }, ['objectType', 'body']),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = _dispatch(name, arguments)
        return [types.TextContent(type='text', text=json.dumps(result, ensure_ascii=False, default=str))]
    except Exception as e:
        return [types.TextContent(type='text', text=json.dumps({'error': str(e)}))]


def _search_objects(c, object_type: str, query: str, limit: int = 50) -> dict:
    """Generic CRM search via POST /crm/v3/objects/{type}/search."""
    body = {
        "query": query,
        "limit": limit,
    }
    raw = c._post_json(f"crm/v3/objects/{object_type}/search", body)
    results = raw.get("results", []) if isinstance(raw, dict) else []
    return {"items": results, "total": raw.get("total", len(results)) if isinstance(raw, dict) else len(results)}


def _dispatch(name: str, args: dict):
    c = _get_client()
    match name:
        # ── Deals ────────────────────────────────────────────────────
        case 'hubspot_deals_listar':
            return c.list_deals(
                status=args.get('status', 'open'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'hubspot_deal_obter':
            return c.get_deal(args['id'])
        case 'hubspot_deal_criar':
            return c.create_deal(
                title=args['title'],
                amount=args.get('amount'),
                pipeline=args.get('pipeline'),
            )
        case 'hubspot_deal_atualizar':
            return c.update_deal(
                args['id'],
                amount=args.get('amount'),
                close_date=args.get('close_date'),
            )
        case 'hubspot_deal_mover':
            return c.move_deal(args['id'], args['to_stage'])
        case 'hubspot_deal_nota':
            return c.add_deal_note(args['id'], args['note'])
        case 'hubspot_deal_ganho':
            return c.mark_deal_won(args['id'])
        case 'hubspot_deal_perdido':
            return c.mark_deal_lost(args['id'], reason=args.get('reason', ''))
        case 'hubspot_deal_excluir':
            return c.delete_deal(args['id'])
        case 'hubspot_deals_batch_criar':
            return c.batch_create_deals(args['inputs'])
        case 'hubspot_deals_batch_atualizar':
            return c.batch_update_deals(args['inputs'])
        case 'hubspot_deals_batch_arquivar':
            return c.batch_archive_deals(args['inputs'])

        # ── Contacts ─────────────────────────────────────────────────
        case 'hubspot_contatos_listar':
            return c.list_contacts(limit=args.get('limit', 50))
        case 'hubspot_contato_obter':
            return c.get_contact(args['id'])
        case 'hubspot_contato_criar':
            return c.create_contact(
                email=args['email'],
                firstname=args.get('firstname'),
                lastname=args.get('lastname'),
                phone=args.get('phone'),
            )
        case 'hubspot_contato_atualizar':
            return c.update_contact(args['id'], args['properties'])
        case 'hubspot_contato_excluir':
            return c.delete_contact(args['id'])
        case 'hubspot_contatos_batch_criar':
            return c.batch_create_contacts(args['inputs'])
        case 'hubspot_contatos_batch_atualizar':
            return c.batch_update_contacts(args['inputs'])
        case 'hubspot_contatos_batch_ler':
            return c.batch_read_contacts(args['inputs'], properties=args.get('properties'))
        case 'hubspot_contatos_batch_arquivar':
            return c.batch_archive_contacts(args['inputs'])

        # ── Companies ────────────────────────────────────────────────
        case 'hubspot_empresas_listar':
            return c.list_companies(limit=args.get('limit', 50))
        case 'hubspot_empresa_obter':
            return c.get_company(args['id'])
        case 'hubspot_empresa_criar':
            return c.create_company(
                name=args['name'],
                domain=args.get('domain'),
                industry=args.get('industry'),
            )
        case 'hubspot_empresa_atualizar':
            return c.update_company(args['id'], args['properties'])
        case 'hubspot_empresa_excluir':
            return c.delete_company(args['id'])
        case 'hubspot_empresas_batch_criar':
            return c.batch_create_companies(args['inputs'])
        case 'hubspot_empresas_batch_atualizar':
            return c.batch_update_companies(args['inputs'])
        case 'hubspot_empresas_batch_arquivar':
            return c.batch_archive_companies(args['inputs'])

        # ── Tickets ──────────────────────────────────────────────────
        case 'hubspot_tickets_listar':
            return c.list_tickets(limit=args.get('limit', 50))
        case 'hubspot_ticket_obter':
            return c.get_ticket(args['id'])
        case 'hubspot_ticket_criar':
            return c.create_ticket(
                subject=args['subject'],
                content=args.get('content'),
                priority=args.get('priority'),
            )
        case 'hubspot_ticket_atualizar':
            return c.update_ticket(args['id'], args['properties'])
        case 'hubspot_ticket_excluir':
            return c.delete_ticket(args['id'])
        case 'hubspot_tickets_buscar':
            return c.search_tickets(args['query'], limit=args.get('limit', 50))
        case 'hubspot_tickets_batch_criar':
            return c.batch_create_tickets(args['inputs'])
        case 'hubspot_tickets_batch_atualizar':
            return c.batch_update_tickets(args['inputs'])
        case 'hubspot_tickets_batch_ler':
            return c.batch_read_tickets(args['inputs'], properties=args.get('properties'))
        case 'hubspot_tickets_batch_arquivar':
            return c.batch_archive_tickets(args['inputs'])

        # ── Line Items ───────────────────────────────────────────────
        case 'hubspot_line_items_listar':
            return c.list_line_items(limit=args.get('limit', 50))
        case 'hubspot_lineitem_obter':
            return c.get_line_item(args['id'])
        case 'hubspot_lineitem_criar':
            return c.create_line_item(args['properties'])
        case 'hubspot_lineitem_atualizar':
            return c.update_line_item(args['id'], args['properties'])
        case 'hubspot_lineitem_excluir':
            return c.delete_line_item(args['id'])
        case 'hubspot_lineitems_batch_criar':
            return c.batch_create_line_items(args['inputs'])
        case 'hubspot_lineitems_batch_atualizar':
            return c.batch_update_line_items(args['inputs'])
        case 'hubspot_lineitems_batch_arquivar':
            return c.batch_archive_line_items(args['inputs'])

        # ── Quotes ───────────────────────────────────────────────────
        case 'hubspot_quotes_listar':
            return c.list_quotes(limit=args.get('limit', 50))
        case 'hubspot_quote_obter':
            return c.get_quote(args['id'])
        case 'hubspot_quote_criar':
            return c.create_quote(args['properties'])
        case 'hubspot_quote_atualizar':
            return c.update_quote(args['id'], args['properties'])
        case 'hubspot_quote_excluir':
            return c.delete_quote(args['id'])

        # ── Notes ────────────────────────────────────────────────────
        case 'hubspot_notas_listar':
            return c.list_notes(limit=args.get('limit', 50))
        case 'hubspot_nota_criar':
            return c.create_note(
                body=args['body'],
                contact_id=args.get('contact_id'),
                deal_id=args.get('deal_id'),
            )
        case 'hubspot_nota_obter':
            return c.get_note(args['id'])
        case 'hubspot_nota_atualizar':
            return c.update_note(args['id'], args['properties'])
        case 'hubspot_nota_excluir':
            return c.delete_note(args['id'])

        # ── Calls ────────────────────────────────────────────────────
        case 'hubspot_calls_listar':
            return c.list_calls(limit=args.get('limit', 50))
        case 'hubspot_call_criar':
            return c.create_call(
                title=args['title'],
                body=args.get('body'),
                duration_ms=args.get('duration_ms'),
                contact_id=args.get('contact_id'),
            )
        case 'hubspot_call_obter':
            return c.get_call(args['id'])
        case 'hubspot_call_atualizar':
            return c.update_call(args['id'], args['properties'])
        case 'hubspot_call_excluir':
            return c.delete_call(args['id'])

        # ── Emails ───────────────────────────────────────────────────
        case 'hubspot_emails_listar':
            return c.list_emails(limit=args.get('limit', 50))
        case 'hubspot_email_obter':
            return c.get_email(args['id'])
        case 'hubspot_email_criar':
            return c.create_email(args['properties'], associations=args.get('associations'))
        case 'hubspot_email_atualizar':
            return c.update_email(args['id'], args['properties'])
        case 'hubspot_email_excluir':
            return c.delete_email(args['id'])

        # ── Meetings ─────────────────────────────────────────────────
        case 'hubspot_meetings_listar':
            return c.list_meetings(limit=args.get('limit', 50))
        case 'hubspot_meeting_obter':
            return c.get_meeting(args['id'])
        case 'hubspot_meeting_criar':
            return c.create_meeting(args['properties'], associations=args.get('associations'))
        case 'hubspot_meeting_atualizar':
            return c.update_meeting(args['id'], args['properties'])
        case 'hubspot_meeting_excluir':
            return c.delete_meeting(args['id'])

        # ── Tasks ────────────────────────────────────────────────────
        case 'hubspot_tasks_listar':
            return c.list_tasks(limit=args.get('limit', 50))
        case 'hubspot_task_criar':
            return c.create_task(
                subject=args['subject'],
                body=args.get('body'),
                priority=args.get('priority'),
                due_date=args.get('due_date'),
            )
        case 'hubspot_task_obter':
            return c.get_task(args['id'])
        case 'hubspot_task_atualizar':
            return c.update_task(args['id'], args['properties'])
        case 'hubspot_task_excluir':
            return c.delete_task(args['id'])

        # ── Products ─────────────────────────────────────────────────
        case 'hubspot_products_listar':
            return c.list_products(limit=args.get('limit', 50))
        case 'hubspot_product_obter':
            return c.get_product(args['id'])
        case 'hubspot_product_criar':
            return c.create_product(args['properties'])
        case 'hubspot_product_atualizar':
            return c.update_product(args['id'], args['properties'])
        case 'hubspot_product_excluir':
            return c.delete_product(args['id'])

        # ── Associations ─────────────────────────────────────────────
        case 'hubspot_associations_listar':
            return c.list_associations(args['from_type'], args['from_id'], args['to_type'])
        case 'hubspot_association_criar':
            return c.create_association(args['from_type'], args['from_id'], args['to_type'], args['to_id'], args['association_type_id'])
        case 'hubspot_association_excluir':
            return c.delete_association(args['from_type'], args['from_id'], args['to_type'], args['to_id'])
        case 'hubspot_associations_batch_criar':
            return c.batch_create_associations(args['from_type'], args['to_type'], args['inputs'])
        case 'hubspot_associations_batch_excluir':
            return c.batch_delete_associations(args['from_type'], args['to_type'], args['inputs'])
        case 'hubspot_associations_batch_ler':
            return c.batch_read_associations(args['from_type'], args['to_type'], args['inputs'])
        case 'hubspot_association_labels_listar':
            return c.list_association_labels(args['from_type'], args['to_type'])
        case 'hubspot_association_label_criar':
            return c.create_association_label(args['from_type'], args['to_type'], args['label'], args['name'])
        case 'hubspot_association_label_excluir':
            return c.delete_association_label(args['from_type'], args['to_type'], args['label_id'])

        # ── Properties ───────────────────────────────────────────────
        case 'hubspot_properties_listar':
            return c.list_properties(object_type=args.get('object_type', 'deals'))
        case 'hubspot_property_obter':
            return c.get_property(args['object_type'], args['property_name'])
        case 'hubspot_property_criar':
            return c.create_property(args['object_type'], args['property_def'])
        case 'hubspot_property_atualizar':
            return c.update_property(args['object_type'], args['property_name'], args['property_def'])
        case 'hubspot_property_excluir':
            return c.delete_property(args['object_type'], args['property_name'])
        case 'hubspot_property_groups_listar':
            return c.list_property_groups(args['object_type'])
        case 'hubspot_property_group_criar':
            return c.create_property_group(args['object_type'], args['name'], args['label'])
        case 'hubspot_property_group_atualizar':
            return c.update_property_group(args['object_type'], args['group_name'], args['body'])
        case 'hubspot_property_group_excluir':
            return c.delete_property_group(args['object_type'], args['group_name'])

        # ── Pipelines ───────────────────────────────────────────────
        case 'hubspot_pipelines_listar':
            return c.list_pipelines(object_type=args.get('object_type', 'deals'))
        case 'hubspot_pipeline_stages':
            stages = c._fetch_stages()
            return {"items": [{"id": k, "label": v} for k, v in stages.items()], "total": len(stages)}
        case 'hubspot_pipeline_obter':
            return c.get_pipeline(args['object_type'], args['pipeline_id'])
        case 'hubspot_pipeline_criar':
            return c.create_pipeline(args['object_type'], args['body'])
        case 'hubspot_pipeline_atualizar':
            return c.update_pipeline(args['object_type'], args['pipeline_id'], args['body'])
        case 'hubspot_pipeline_excluir':
            return c.delete_pipeline(args['object_type'], args['pipeline_id'])
        case 'hubspot_pipeline_stage_obter':
            return c.get_pipeline_stage(args['object_type'], args['pipeline_id'], args['stage_id'])
        case 'hubspot_pipeline_stage_criar':
            return c.create_pipeline_stage(args['object_type'], args['pipeline_id'], args['body'])
        case 'hubspot_pipeline_stage_atualizar':
            return c.update_pipeline_stage(args['object_type'], args['pipeline_id'], args['stage_id'], args['body'])
        case 'hubspot_pipeline_stage_excluir':
            return c.delete_pipeline_stage(args['object_type'], args['pipeline_id'], args['stage_id'])
        case 'hubspot_deal_stages_listar':
            return c.list_deal_stages()

        # ── Owners ───────────────────────────────────────────────────
        case 'hubspot_owners_listar':
            return c.list_owners(limit=args.get('limit', 100))
        case 'hubspot_owner_obter':
            return c.get_owner(args['id'])

        # ── CRM Search ───────────────────────────────────────────────
        case 'hubspot_crm_search':
            return c.crm_search(
                object_type=args['object_type'],
                query=args.get('query', ''),
                filters=args.get('filters'),
                sorts=args.get('sorts'),
                properties=args.get('properties'),
                limit=args.get('limit', 50),
                after=args.get('after'),
            )

        # ── Account info ─────────────────────────────────────────────
        case 'hubspot_conta_info':
            return c.company_info()

        # ── Search ───────────────────────────────────────────────────
        case 'hubspot_contatos_buscar':
            return _search_objects(c, 'contacts', args['query'], limit=args.get('limit', 50))
        case 'hubspot_empresas_buscar':
            return _search_objects(c, 'companies', args['query'], limit=args.get('limit', 50))
        case 'hubspot_deals_buscar':
            return _search_objects(c, 'deals', args['query'], limit=args.get('limit', 50))

        # ── Forms ────────────────────────────────────────────────────
        case 'hubspot_forms_listar':
            return c.list_forms()
        case 'hubspot_form_obter':
            return c.get_form(args['id'])

        # ── Marketing Emails ─────────────────────────────────────────
        case 'hubspot_marketing_emails_listar':
            return c.list_marketing_emails(limit=args.get('limit', 50))
        case 'hubspot_marketing_email_obter':
            return c.get_marketing_email(args['id'])

        # ── Feedback Submissions ─────────────────────────────────────
        case 'hubspot_feedback_submissions_listar':
            return c.list_feedback_submissions(limit=args.get('limit', 50))
        case 'hubspot_feedback_submission_obter':
            return c.get_feedback_submission(args['id'])

        # ── Custom Objects ───────────────────────────────────────────
        case 'hubspot_custom_objects_schemas_listar':
            return c.list_custom_object_schemas()
        case 'hubspot_custom_objects_schema_obter':
            return c.get_custom_object_schema(args['object_type'])
        case 'hubspot_custom_objects_listar':
            return c.list_custom_objects(args['object_type'], limit=args.get('limit', 50))
        case 'hubspot_custom_objects_obter':
            return c.get_custom_object(args['object_type'], args['id'])
        case 'hubspot_custom_objects_criar':
            return c.create_custom_object(args['object_type'], args['properties'])

        # ── Communications ───────────────────────────────────────────
        case 'hubspot_communications_listar':
            return c.list_communications(limit=args.get('limit', 50))
        case 'hubspot_communication_obter':
            return c.get_communication(args['id'])

        # ── Postal Mail ──────────────────────────────────────────────
        case 'hubspot_postal_mail_listar':
            return c.list_postal_mail(limit=args.get('limit', 50))
        case 'hubspot_postal_mail_obter':
            return c.get_postal_mail(args['id'])

        # ══════════════════════════════════════════════════════════════
        # GRUPO A — CMS Hub
        # ══════════════════════════════════════════════════════════════

        # ── CMS Blog Posts ───────────────────────────────────────────
        case 'hubspot_cms_blog_posts_list':
            return c._get(f"cms/v3/blogs/posts?limit={args.get('limit', 50)}")
        case 'hubspot_cms_blog_post_get':
            return c._get(f"cms/v3/blogs/posts/{args['id']}")
        case 'hubspot_cms_blog_post_create':
            return c._post_json("cms/v3/blogs/posts", args.get('body', {}))
        case 'hubspot_cms_blog_post_update':
            return c._patch(f"cms/v3/blogs/posts/{args['id']}", args.get('body', {}))
        case 'hubspot_cms_blog_post_delete':
            return _del(c, f"cms/v3/blogs/posts/{args['id']}")
        case 'hubspot_cms_blog_post_clone':
            return c._post_json(f"cms/v3/blogs/posts/clone", {"id": args['id']})
        case 'hubspot_cms_blog_post_schedule':
            return c._post_json(f"cms/v3/blogs/posts/schedule", {"id": args['id'], "dateTime": args['dateTime']})
        case 'hubspot_cms_blog_post_push_live':
            return c._post_json(f"cms/v3/blogs/posts/push-live", {"id": args['id']})
        case 'hubspot_cms_blog_post_reset_draft':
            return c._post_json(f"cms/v3/blogs/posts/reset-draft", {"id": args['id']})
        case 'hubspot_cms_blog_post_batch_read':
            return c._post_json("cms/v3/blogs/posts/batch/read", {"inputs": args['inputs']})
        case 'hubspot_cms_blog_post_batch_create':
            return c._post_json("cms/v3/blogs/posts/batch/create", {"inputs": args['inputs']})
        case 'hubspot_cms_blog_post_batch_update':
            return c._post_json("cms/v3/blogs/posts/batch/update", {"inputs": args['inputs']})
        case 'hubspot_cms_blog_post_batch_delete':
            return c._post_json("cms/v3/blogs/posts/batch/archive", {"inputs": args['inputs']})

        # ── CMS Site Pages ───────────────────────────────────────────
        case 'hubspot_cms_pages_list':
            return c._get(f"cms/v3/pages/site-pages?limit={args.get('limit', 50)}")
        case 'hubspot_cms_page_get':
            return c._get(f"cms/v3/pages/site-pages/{args['id']}")
        case 'hubspot_cms_page_create':
            return c._post_json("cms/v3/pages/site-pages", args.get('body', {}))
        case 'hubspot_cms_page_update':
            return c._patch(f"cms/v3/pages/site-pages/{args['id']}", args.get('body', {}))
        case 'hubspot_cms_page_delete':
            return _del(c, f"cms/v3/pages/site-pages/{args['id']}")
        case 'hubspot_cms_page_clone':
            return c._post_json("cms/v3/pages/site-pages/clone", {"id": args['id']})
        case 'hubspot_cms_page_push_live':
            return c._post_json("cms/v3/pages/site-pages/push-live", {"id": args['id']})
        case 'hubspot_cms_page_schedule':
            return c._post_json("cms/v3/pages/site-pages/schedule", {"id": args['id'], "dateTime": args['dateTime']})

        # ── CMS Landing Pages ────────────────────────────────────────
        case 'hubspot_cms_landing_pages_list':
            return c._get(f"cms/v3/pages/landing-pages?limit={args.get('limit', 50)}")
        case 'hubspot_cms_landing_page_get':
            return c._get(f"cms/v3/pages/landing-pages/{args['id']}")
        case 'hubspot_cms_landing_page_create':
            return c._post_json("cms/v3/pages/landing-pages", args.get('body', {}))
        case 'hubspot_cms_landing_page_update':
            return c._patch(f"cms/v3/pages/landing-pages/{args['id']}", args.get('body', {}))
        case 'hubspot_cms_landing_page_delete':
            return _del(c, f"cms/v3/pages/landing-pages/{args['id']}")
        case 'hubspot_cms_landing_page_push_live':
            return c._post_json("cms/v3/pages/landing-pages/push-live", {"id": args['id']})

        # ── CMS URL Redirects ────────────────────────────────────────
        case 'hubspot_cms_redirects_list':
            return c._get(f"cms/v3/url-mappings?limit={args.get('limit', 50)}")
        case 'hubspot_cms_redirect_get':
            return c._get(f"cms/v3/url-mappings/{args['id']}")
        case 'hubspot_cms_redirect_create':
            return c._post_json("cms/v3/url-mappings", args.get('body', {}))
        case 'hubspot_cms_redirect_update':
            return c._patch(f"cms/v3/url-mappings/{args['id']}", args.get('body', {}))
        case 'hubspot_cms_redirect_delete':
            return _del(c, f"cms/v3/url-mappings/{args['id']}")

        # ── CMS Domains ──────────────────────────────────────────────
        case 'hubspot_cms_domains_list':
            return c._get("cms/v3/domains")
        case 'hubspot_cms_domain_get':
            return c._get(f"cms/v3/domains/{args['id']}")

        # ── CMS Performance ──────────────────────────────────────────
        case 'hubspot_cms_performance_get':
            params = []
            if args.get('domain'): params.append(f"domain={args['domain']}")
            if args.get('period'): params.append(f"period={args['period']}")
            qs = '?' + '&'.join(params) if params else ''
            return c._get(f"cms/v3/performance{qs}")

        # ── HubDB Tables ────────────────────────────────────────────
        case 'hubspot_hubdb_tables_list':
            return c._get("cms/v3/hubdb/tables")
        case 'hubspot_hubdb_table_get':
            return c._get(f"cms/v3/hubdb/tables/{args['id']}")
        case 'hubspot_hubdb_table_create':
            return c._post_json("cms/v3/hubdb/tables", args.get('body', {}))
        case 'hubspot_hubdb_table_delete':
            return _del(c, f"cms/v3/hubdb/tables/{args['id']}")
        case 'hubspot_hubdb_table_clone':
            return c._post_json(f"cms/v3/hubdb/tables/{args['id']}/clone", {"newName": args['newName']})
        case 'hubspot_hubdb_table_publish':
            return c._post_json(f"cms/v3/hubdb/tables/{args['id']}/publish", {})

        # ── HubDB Rows ──────────────────────────────────────────────
        case 'hubspot_hubdb_rows_list':
            return c._get(f"cms/v3/hubdb/tables/{args['table_id']}/rows")
        case 'hubspot_hubdb_row_get':
            return c._get(f"cms/v3/hubdb/tables/{args['table_id']}/rows/{args['row_id']}")
        case 'hubspot_hubdb_row_create':
            return c._post_json(f"cms/v3/hubdb/tables/{args['table_id']}/rows", args.get('body', {}))
        case 'hubspot_hubdb_row_update':
            return c._patch(f"cms/v3/hubdb/tables/{args['table_id']}/rows/{args['row_id']}", args.get('body', {}))
        case 'hubspot_hubdb_row_delete':
            return _del(c, f"cms/v3/hubdb/tables/{args['table_id']}/rows/{args['row_id']}")
        case 'hubspot_hubdb_rows_batch_create':
            return c._post_json(f"cms/v3/hubdb/tables/{args['table_id']}/rows/batch/create", {"inputs": args['inputs']})
        case 'hubspot_hubdb_rows_batch_update':
            return c._post_json(f"cms/v3/hubdb/tables/{args['table_id']}/rows/batch/update", {"inputs": args['inputs']})
        case 'hubspot_hubdb_rows_batch_delete':
            return c._post_json(f"cms/v3/hubdb/tables/{args['table_id']}/rows/batch/clone", {"inputs": args['inputs']})

        # ══════════════════════════════════════════════════════════════
        # GRUPO B — Files Hub
        # ══════════════════════════════════════════════════════════════

        case 'hubspot_files_list':
            return c._get(f"files/v3/files?limit={args.get('limit', 50)}")
        case 'hubspot_file_get':
            return c._get(f"files/v3/files/{args['id']}")
        case 'hubspot_file_upload':
            return c._post_json("files/v3/files", args.get('body', {}))
        case 'hubspot_file_update':
            return c._patch(f"files/v3/files/{args['id']}", args.get('body', {}))
        case 'hubspot_file_delete':
            return _del(c, f"files/v3/files/{args['id']}")
        case 'hubspot_file_signed_url':
            return c._get(f"files/v3/files/{args['id']}/signed-url")
        case 'hubspot_file_import_from_url':
            return c._post_json("files/v3/files/import-from-url/async", args.get('body', {}))
        case 'hubspot_file_folders_list':
            return c._get("files/v3/files/search?type=FOLDER")
        case 'hubspot_file_folders_create':
            return c._post_json("files/v3/folders", args.get('body', {}))
        case 'hubspot_file_folders_update':
            return c._patch(f"files/v3/folders/{args['id']}", args.get('body', {}))
        case 'hubspot_file_folders_delete':
            return _del(c, f"files/v3/folders/{args['id']}")
        case 'hubspot_file_folders_get_by_path':
            return c._get(f"files/v3/folders/by-path/{args['path']}")

        # ══════════════════════════════════════════════════════════════
        # GRUPO C — Conversations Hub
        # ══════════════════════════════════════════════════════════════

        case 'hubspot_conv_threads_list':
            return c._get(f"conversations/v3/conversations/threads?limit={args.get('limit', 50)}")
        case 'hubspot_conv_thread_get':
            return c._get(f"conversations/v3/conversations/threads/{args['id']}")
        case 'hubspot_conv_thread_update':
            return c._patch(f"conversations/v3/conversations/threads/{args['id']}", args.get('body', {}))
        case 'hubspot_conv_thread_archive':
            return c._patch(f"conversations/v3/conversations/threads/{args['id']}", {"status": "ARCHIVED"})
        case 'hubspot_conv_thread_restore':
            return c._patch(f"conversations/v3/conversations/threads/{args['id']}", {"status": "OPEN"})
        case 'hubspot_conv_thread_delete':
            return _del(c, f"conversations/v3/conversations/threads/{args['id']}")
        case 'hubspot_conv_messages_list':
            return c._get(f"conversations/v3/conversations/threads/{args['thread_id']}/messages?limit={args.get('limit', 50)}")
        case 'hubspot_conv_message_get':
            return c._get(f"conversations/v3/conversations/threads/{args['thread_id']}/messages/{args['message_id']}")
        case 'hubspot_conv_message_create':
            return c._post_json(f"conversations/v3/conversations/threads/{args['thread_id']}/messages", args.get('body', {}))
        case 'hubspot_conv_message_original_content':
            return c._get(f"conversations/v3/conversations/threads/{args['thread_id']}/messages/{args['message_id']}/original-content")
        case 'hubspot_conv_inboxes_list':
            return c._get("conversations/v3/conversations/inboxes")
        case 'hubspot_conv_inbox_get':
            return c._get(f"conversations/v3/conversations/inboxes/{args['id']}")
        case 'hubspot_conv_channels_list':
            return c._get(f"conversations/v3/conversations/inboxes/{args['inbox_id']}/channels")

        # ══════════════════════════════════════════════════════════════
        # GRUPO D — Marketing Hub extra
        # ══════════════════════════════════════════════════════════════

        # ── Marketing Events ─────────────────────────────────────────
        case 'hubspot_marketing_events_list':
            return c._get(f"marketing/v3/marketing-events?limit={args.get('limit', 50)}")
        case 'hubspot_marketing_event_create':
            return c._post_json("marketing/v3/marketing-events", args.get('body', {}))
        case 'hubspot_marketing_event_get':
            return c._get(f"marketing/v3/marketing-events/{args['id']}")
        case 'hubspot_marketing_event_update':
            return c._patch(f"marketing/v3/marketing-events/{args['id']}", args.get('body', {}))
        case 'hubspot_marketing_event_delete':
            return _del(c, f"marketing/v3/marketing-events/{args['id']}")
        case 'hubspot_marketing_event_attendances_list':
            return c._get(f"marketing/v3/marketing-events/{args['id']}/attendances")
        case 'hubspot_marketing_event_attendances_create':
            return c._post_json(f"marketing/v3/marketing-events/{args['id']}/attendances", args.get('body', {}))
        case 'hubspot_marketing_event_cancel':
            return c._post_json(f"marketing/v3/marketing-events/{args['id']}/cancel", {})
        case 'hubspot_marketing_event_complete':
            return c._post_json(f"marketing/v3/marketing-events/{args['id']}/complete", {})

        # ── Campaigns ────────────────────────────────────────────────
        case 'hubspot_marketing_campaigns_list':
            return c._get(f"marketing/v3/campaigns?limit={args.get('limit', 50)}")
        case 'hubspot_marketing_campaign_get':
            return c._get(f"marketing/v3/campaigns/{args['id']}")
        case 'hubspot_marketing_campaign_create':
            return c._post_json("marketing/v3/campaigns", args.get('body', {}))
        case 'hubspot_marketing_campaign_update':
            return c._patch(f"marketing/v3/campaigns/{args['id']}", args.get('body', {}))
        case 'hubspot_marketing_campaign_delete':
            return _del(c, f"marketing/v3/campaigns/{args['id']}")
        case 'hubspot_marketing_campaign_assets_list':
            return c._get(f"marketing/v3/campaigns/{args['id']}/assets")

        # ── Subscription Preferences ─────────────────────────────────
        case 'hubspot_subscriptions_definitions_list':
            return c._get("communication-preferences/v3/definitions")
        case 'hubspot_subscriptions_status_get':
            return c._get(f"communication-preferences/v3/status/email/{args['email']}")
        case 'hubspot_subscriptions_status_update':
            return c._post_json(f"communication-preferences/v3/subscribe", {"emailAddress": args['email'], **args.get('body', {})})
        case 'hubspot_subscriptions_unsubscribe':
            return c._post_json("communication-preferences/v3/unsubscribe", {"emailAddress": args['email']})

        # ── Transactional Email ──────────────────────────────────────
        case 'hubspot_transactional_email_send':
            return c._post_json("marketing/v3/transactional/single-email/send", args.get('body', {}))

        # ══════════════════════════════════════════════════════════════
        # GRUPO E — Settings Hub
        # ══════════════════════════════════════════════════════════════

        case 'hubspot_settings_users_list':
            return c._get(f"settings/v3/users?limit={args.get('limit', 50)}")
        case 'hubspot_settings_user_get':
            return c._get(f"settings/v3/users/{args['id']}")
        case 'hubspot_settings_user_create':
            return c._post_json("settings/v3/users", args.get('body', {}))
        case 'hubspot_settings_user_update':
            return c._patch(f"settings/v3/users/{args['id']}", args.get('body', {}))
        case 'hubspot_settings_user_delete':
            return _del(c, f"settings/v3/users/{args['id']}")
        case 'hubspot_settings_teams_list':
            return c._get("settings/v3/users/teams")
        case 'hubspot_settings_team_get':
            return c._get(f"settings/v3/users/teams/{args['id']}")
        case 'hubspot_settings_team_create':
            return c._post_json("settings/v3/users/teams", args.get('body', {}))
        case 'hubspot_settings_team_update':
            return c._patch(f"settings/v3/users/teams/{args['id']}", args.get('body', {}))
        case 'hubspot_settings_team_delete':
            return _del(c, f"settings/v3/users/teams/{args['id']}")
        case 'hubspot_business_units_list':
            return c._get(f"business-units/v3/business-units/user/{args['userId']}")
        case 'hubspot_currencies_list':
            return c._get("settings/v3/account-info/currency")
        case 'hubspot_currencies_update':
            return c._patch("settings/v3/account-info/currency", args.get('body', {}))

        # ══════════════════════════════════════════════════════════════
        # GRUPO F — Automation + Workflows
        # ══════════════════════════════════════════════════════════════

        case 'hubspot_workflows_list':
            return c._get(f"automation/v4/flows?limit={args.get('limit', 50)}")
        case 'hubspot_workflow_get':
            return c._get(f"automation/v4/flows/{args['id']}")
        case 'hubspot_workflow_create':
            return c._post_json("automation/v4/flows", args.get('body', {}))
        case 'hubspot_workflow_update':
            return c._patch(f"automation/v4/flows/{args['id']}", args.get('body', {}))
        case 'hubspot_workflow_delete':
            return _del(c, f"automation/v4/flows/{args['id']}")
        case 'hubspot_workflow_enroll':
            return c._post_json(f"automation/v4/flows/{args['id']}/enrollments", args.get('body', {}))
        case 'hubspot_sequences_list':
            return c._get(f"automation/v4/sequences?limit={args.get('limit', 50)}")
        case 'hubspot_sequence_get':
            return c._get(f"automation/v4/sequences/{args['id']}")
        case 'hubspot_sequence_enroll':
            return c._post_json(f"automation/v4/sequences/{args['id']}/enrollments", args.get('body', {}))

        # ══════════════════════════════════════════════════════════════
        # GRUPO G — CRM Extras
        # ══════════════════════════════════════════════════════════════

        case 'hubspot_imports_list':
            return c._get(f"crm/v3/imports?limit={args.get('limit', 50)}")
        case 'hubspot_import_get':
            return c._get(f"crm/v3/imports/{args['id']}")
        case 'hubspot_import_create':
            return c._post_json("crm/v3/imports", args.get('body', {}))
        case 'hubspot_import_cancel':
            return c._post_json(f"crm/v3/imports/{args['id']}/cancel", {})
        case 'hubspot_import_errors':
            return c._get(f"crm/v3/imports/{args['id']}/errors")
        case 'hubspot_exports_create':
            return c._post_json("crm/v3/exports/export/async", args.get('body', {}))
        case 'hubspot_exports_status':
            return c._get(f"crm/v3/exports/export/async/tasks/{args['id']}/status")
        case 'hubspot_lists_list':
            return c._get(f"crm/v3/lists?limit={args.get('limit', 50)}")
        case 'hubspot_list_get':
            return c._get(f"crm/v3/lists/{args['id']}")
        case 'hubspot_list_create':
            return c._post_json("crm/v3/lists", args.get('body', {}))
        case 'hubspot_list_update':
            return c._patch(f"crm/v3/lists/{args['id']}", args.get('body', {}))
        case 'hubspot_list_delete':
            return _del(c, f"crm/v3/lists/{args['id']}")
        case 'hubspot_list_memberships_get':
            return c._get(f"crm/v3/lists/{args['id']}/memberships?limit={args.get('limit', 50)}")
        case 'hubspot_list_memberships_add':
            return c._post_json(f"crm/v3/lists/{args['id']}/memberships/add", args.get('body', []))
        case 'hubspot_list_memberships_remove':
            return c._post_json(f"crm/v3/lists/{args['id']}/memberships/remove", args.get('body', []))
        case 'hubspot_audit_log_list':
            return c._get(f"account-info/v3/activity/audit-logs?limit={args.get('limit', 50)}")
        case 'hubspot_behavioral_events_list':
            return c._get("events/v3/event-definitions")
        case 'hubspot_behavioral_event_send':
            return c._post_json("events/v3/send", args.get('body', {}))

        # ══════════════════════════════════════════════════════════════
        # HUB 1 — Marketing Workflows & Forms v3
        # ══════════════════════════════════════════════════════════════

        # ── Workflows Legacy v1 ──────────────────────────────────────
        case 'hubspot_workflows_v1_list':
            return c._get("automation/v1/workflows")
        case 'hubspot_workflows_v1_get':
            return c._get(f"automation/v1/workflows/{args['workflowId']}")
        case 'hubspot_workflows_v1_create':
            return c._post_json("automation/v1/workflows", args.get('body', {}))
        case 'hubspot_workflows_v1_update':
            return c._put(f"automation/v1/workflows/{args['workflowId']}", args.get('body', {}))
        case 'hubspot_workflows_v1_delete':
            return _del(c, f"automation/v1/workflows/{args['workflowId']}")
        case 'hubspot_workflows_v1_enroll':
            return c._post_json(f"automation/v1/workflows/{args['workflowId']}/enrollments/contacts/{args['email']}", {})
        case 'hubspot_workflows_v1_unenroll':
            return _del(c, f"automation/v1/workflows/{args['workflowId']}/enrollments/contacts/{args['email']}")
        case 'hubspot_workflows_v1_enrollments_list':
            return c._get(f"automation/v1/workflows/enrollments/contacts/{args['email']}")

        # ── Forms v3 ────────────────────────────────────────────────
        case 'hubspot_forms_v3_list':
            return c._get(f"marketing/v3/forms?limit={args.get('limit', 50)}")
        case 'hubspot_forms_v3_get':
            return c._get(f"marketing/v3/forms/{args['formId']}")
        case 'hubspot_forms_v3_create':
            return c._post_json("marketing/v3/forms", args.get('body', {}))
        case 'hubspot_forms_v3_update':
            return c._patch(f"marketing/v3/forms/{args['formId']}", args.get('body', {}))
        case 'hubspot_forms_v3_archive':
            return c._post_json(f"marketing/v3/forms/{args['formId']}/archive", {})
        case 'hubspot_forms_v3_submissions_list':
            return c._get(f"marketing/v3/forms/{args['formId']}/submissions?limit={args.get('limit', 50)}")
        case 'hubspot_forms_v3_submissions_get':
            return c._get(f"marketing/v3/forms/{args['formId']}/submissions/{args['submissionId']}")
        case 'hubspot_forms_v3_fields_list':
            return c._get(f"marketing/v3/forms/{args['formId']}/fields")
        case 'hubspot_forms_v3_field_create':
            return c._post_json(f"marketing/v3/forms/{args['formId']}/fields", args.get('body', {}))
        case 'hubspot_forms_v3_field_update':
            return c._patch(f"marketing/v3/forms/{args['formId']}/fields/{args['fieldId']}", args.get('body', {}))
        case 'hubspot_forms_v3_field_delete':
            return _del(c, f"marketing/v3/forms/{args['formId']}/fields/{args['fieldId']}")

        # ── Email Marketing Stats ───────────────────────────────────
        case 'hubspot_email_stats_summary':
            return c._get("marketing/v3/emails/statistics/summary")
        case 'hubspot_email_stats_list':
            return c._get(f"marketing/v3/emails/statistics/list?limit={args.get('limit', 50)}")
        case 'hubspot_email_stats_histogram':
            return c._get(f"marketing/v3/emails/{args['emailId']}/statistics/histogram")
        case 'hubspot_email_preview':
            return c._get(f"marketing/v3/emails/{args['emailId']}/preview")

        # ── Marketing Emails extras ─────────────────────────────────
        case 'hubspot_marketing_email_create':
            return c._post_json("marketing/v3/emails", args.get('body', {}))
        case 'hubspot_marketing_email_update':
            return c._patch(f"marketing/v3/emails/{args['emailId']}", args.get('body', {}))
        case 'hubspot_marketing_email_archive':
            return _del(c, f"marketing/v3/emails/{args['emailId']}")
        case 'hubspot_marketing_email_clone':
            return c._post_json("marketing/v3/emails/clone", {"id": args['emailId']})
        case 'hubspot_marketing_email_send_test':
            return c._post_json(f"marketing/v3/emails/{args['emailId']}/send-test", args.get('body', {}))
        case 'hubspot_marketing_email_schedule':
            return c._post_json(f"marketing/v3/emails/{args['emailId']}/schedule", args.get('body', {}))
        case 'hubspot_marketing_email_unschedule':
            return _del(c, f"marketing/v3/emails/{args['emailId']}/schedule")

        # ── Lists v3 extras ─────────────────────────────────────────
        case 'hubspot_lists_search':
            return c._post_json("crm/v3/lists/search", args.get('body', {}))
        case 'hubspot_list_memberships_count':
            return c._get(f"crm/v3/lists/{args['id']}/memberships/count")
        case 'hubspot_lists_batch_read':
            return c._post_json("crm/v3/lists/batch/read", {"inputs": args['inputs']})
        case 'hubspot_lists_batch_archive':
            return c._post_json("crm/v3/lists/batch/archive", {"inputs": args['inputs']})
        case 'hubspot_lists_folders_list':
            return c._get("crm/v3/lists/folders")
        case 'hubspot_lists_folders_create':
            return c._post_json("crm/v3/lists/folders", args.get('body', {}))

        # ══════════════════════════════════════════════════════════════
        # HUB 2 — Automation Sequences full
        # ══════════════════════════════════════════════════════════════

        # ── Sequences v4 extras ─────────────────────────────────────
        case 'hubspot_sequences_create':
            return c._post_json("automation/v4/sequences", args.get('body', {}))
        case 'hubspot_sequences_update':
            return c._patch(f"automation/v4/sequences/{args['sequenceId']}", args.get('body', {}))
        case 'hubspot_sequences_delete':
            return _del(c, f"automation/v4/sequences/{args['sequenceId']}")
        case 'hubspot_sequences_steps_list':
            return c._get(f"automation/v4/sequences/{args['sequenceId']}/steps")
        case 'hubspot_sequences_steps_create':
            return c._post_json(f"automation/v4/sequences/{args['sequenceId']}/steps", args.get('body', {}))
        case 'hubspot_sequences_steps_update':
            return c._patch(f"automation/v4/sequences/{args['sequenceId']}/steps/{args['stepId']}", args.get('body', {}))
        case 'hubspot_sequences_steps_delete':
            return _del(c, f"automation/v4/sequences/{args['sequenceId']}/steps/{args['stepId']}")

        # ── Sequence Enrollments v4 ─────────────────────────────────
        case 'hubspot_sequence_enrollments_list':
            return c._get(f"automation/v4/sequences/enrollments?limit={args.get('limit', 50)}")
        case 'hubspot_sequence_enrollment_get':
            return c._get(f"automation/v4/sequences/enrollments/{args['enrollmentId']}")
        case 'hubspot_sequence_enroll_contact':
            return c._post_json(f"automation/v4/sequences/{args['sequenceId']}/enrollments", args.get('body', {}))
        case 'hubspot_sequence_unenroll':
            return _del(c, f"automation/v4/sequences/enrollments/{args['enrollmentId']}")
        case 'hubspot_sequence_enrollment_pause':
            return c._post_json(f"automation/v4/sequences/enrollments/{args['enrollmentId']}/pause", {})
        case 'hubspot_sequence_enrollment_resume':
            return c._post_json(f"automation/v4/sequences/enrollments/{args['enrollmentId']}/resume", {})

        # ── Custom Workflow Actions ─────────────────────────────────
        case 'hubspot_workflow_actions_list':
            return c._get(f"automation/v4/actions/{args['appId']}")
        case 'hubspot_workflow_actions_get':
            return c._get(f"automation/v4/actions/{args['appId']}/{args['definitionId']}")
        case 'hubspot_workflow_actions_create':
            return c._post_json(f"automation/v4/actions/{args['appId']}", args.get('body', {}))
        case 'hubspot_workflow_actions_update':
            return c._patch(f"automation/v4/actions/{args['appId']}/{args['definitionId']}", args.get('body', {}))
        case 'hubspot_workflow_actions_delete':
            return _del(c, f"automation/v4/actions/{args['appId']}/{args['definitionId']}")
        case 'hubspot_workflow_actions_revisions_list':
            return c._get(f"automation/v4/actions/{args['appId']}/{args['definitionId']}/revisions")
        case 'hubspot_workflow_actions_functions_list':
            return c._get(f"automation/v4/actions/{args['appId']}/{args['definitionId']}/functions")
        case 'hubspot_workflow_actions_function_get':
            return c._get(f"automation/v4/actions/{args['appId']}/{args['definitionId']}/functions/{args['functionType']}")
        case 'hubspot_workflow_actions_function_upsert':
            return c._put(f"automation/v4/actions/{args['appId']}/{args['definitionId']}/functions/{args['functionType']}", args.get('body', {}))
        case 'hubspot_workflow_actions_function_delete':
            return _del(c, f"automation/v4/actions/{args['appId']}/{args['definitionId']}/functions/{args['functionType']}")

        # ══════════════════════════════════════════════════════════════
        # HUB 3 — CMS Source Code + Templates
        # ══════════════════════════════════════════════════════════════

        # ── Source Code Files ───────────────────────────────────────
        case 'hubspot_cms_source_list':
            env = args.get('environment', 'draft')
            path = args.get('path', '/')
            return c._get(f"cms/v3/source-code/{env}/children?path={path}")
        case 'hubspot_cms_source_get':
            env = args.get('environment', 'draft')
            return c._get(f"cms/v3/source-code/{env}/content/{args['path']}")
        case 'hubspot_cms_source_create':
            env = args.get('environment', 'draft')
            return c._post_json(f"cms/v3/source-code/{env}/content/{args['path']}", {"source": args.get('body', '')})
        case 'hubspot_cms_source_update':
            env = args.get('environment', 'draft')
            return c._put(f"cms/v3/source-code/{env}/content/{args['path']}", {"source": args.get('body', '')})
        case 'hubspot_cms_source_delete':
            env = args.get('environment', 'draft')
            return _del(c, f"cms/v3/source-code/{env}/content/{args['path']}")
        case 'hubspot_cms_source_metadata':
            env = args.get('environment', 'draft')
            return c._get(f"cms/v3/source-code/{env}/metadata/{args['path']}")
        case 'hubspot_cms_source_validate':
            env = args.get('environment', 'draft')
            return c._post_json(f"cms/v3/source-code/{env}/validate/{args['path']}", {})

        # ── Templates (Design Manager) ──────────────────────────────
        case 'hubspot_cms_templates_list':
            return c._get(f"cms/v2/templates?limit={args.get('limit', 50)}")
        case 'hubspot_cms_template_get':
            return c._get(f"cms/v2/templates/{args['template_id']}")
        case 'hubspot_cms_template_create':
            return c._post_json("cms/v2/templates", args.get('body', {}))
        case 'hubspot_cms_template_update':
            return c._put(f"cms/v2/templates/{args['template_id']}", args.get('body', {}))
        case 'hubspot_cms_template_delete':
            return _del(c, f"cms/v2/templates/{args['template_id']}")

        # ── Themes ──────────────────────────────────────────────────
        case 'hubspot_cms_themes_list':
            return c._get("cms/v3/themes")
        case 'hubspot_cms_theme_get':
            return c._get(f"cms/v3/themes/{args['themeId']}")
        case 'hubspot_cms_theme_settings_get':
            return c._get(f"cms/v3/themes/{args['themeId']}/settings")
        case 'hubspot_cms_theme_settings_update':
            return c._patch(f"cms/v3/themes/{args['themeId']}/settings", args.get('body', {}))
        case 'hubspot_cms_theme_fields_list':
            return c._get(f"cms/v3/themes/{args['themeId']}/fields")

        # ── Site Search ─────────────────────────────────────────────
        case 'hubspot_cms_site_search':
            qs = f"q={args['q']}&limit={args.get('limit', 50)}"
            if args.get('type'):
                qs += f"&type={args['type']}"
            return c._get(f"cms/v3/site-search/search?{qs}")
        case 'hubspot_cms_site_search_index_status':
            return c._get(f"cms/v3/site-search/indexed-data/{args['contentId']}")

        # ── Blog Authors ────────────────────────────────────────────
        case 'hubspot_cms_blog_authors_list':
            return c._get(f"cms/v3/blogs/authors?limit={args.get('limit', 50)}")
        case 'hubspot_cms_blog_author_get':
            return c._get(f"cms/v3/blogs/authors/{args['authorId']}")
        case 'hubspot_cms_blog_author_create':
            return c._post_json("cms/v3/blogs/authors", args.get('body', {}))
        case 'hubspot_cms_blog_author_update':
            return c._patch(f"cms/v3/blogs/authors/{args['authorId']}", args.get('body', {}))
        case 'hubspot_cms_blog_author_delete':
            return _del(c, f"cms/v3/blogs/authors/{args['authorId']}")

        # ── Blog Tags ───────────────────────────────────────────────
        case 'hubspot_cms_blog_tags_list':
            return c._get(f"cms/v3/blogs/tags?limit={args.get('limit', 50)}")
        case 'hubspot_cms_blog_tag_get':
            return c._get(f"cms/v3/blogs/tags/{args['tagId']}")
        case 'hubspot_cms_blog_tag_create':
            return c._post_json("cms/v3/blogs/tags", args.get('body', {}))
        case 'hubspot_cms_blog_tag_update':
            return c._patch(f"cms/v3/blogs/tags/{args['tagId']}", args.get('body', {}))
        case 'hubspot_cms_blog_tag_delete':
            return _del(c, f"cms/v3/blogs/tags/{args['tagId']}")

        # ── CMS Audit ───────────────────────────────────────────────
        case 'hubspot_cms_audit_logs_list':
            qs = f"limit={args.get('limit', 50)}"
            if args.get('objectType'):
                qs += f"&objectType={args['objectType']}"
            return c._get(f"cms/v3/audit-logs?{qs}")
        case 'hubspot_cms_content_audit':
            return c._get("cms/v3/content/audit")

        # ══════════════════════════════════════════════════════════════
        # HUB 4 — Analytics & Custom Behavioral Events
        # ══════════════════════════════════════════════════════════════

        # ── Event Definitions ───────────────────────────────────────
        case 'hubspot_events_definitions_list':
            return c._get("analytics/v2/event-definitions")
        case 'hubspot_events_definition_get':
            return c._get(f"analytics/v2/event-definitions/{args['eventName']}")
        case 'hubspot_events_definition_create':
            return c._post_json("analytics/v2/event-definitions", args.get('body', {}))
        case 'hubspot_events_definition_update':
            return c._put(f"analytics/v2/event-definitions/{args['eventName']}", args.get('body', {}))
        case 'hubspot_events_definition_delete':
            return _del(c, f"analytics/v2/event-definitions/{args['eventName']}")
        case 'hubspot_events_definition_properties_list':
            return c._get(f"analytics/v2/event-definitions/{args['eventName']}/properties")
        case 'hubspot_events_definition_property_create':
            return c._post_json(f"analytics/v2/event-definitions/{args['eventName']}/properties", args.get('body', {}))
        case 'hubspot_events_definition_property_update':
            return c._put(f"analytics/v2/event-definitions/{args['eventName']}/properties/{args['propertyName']}", args.get('body', {}))
        case 'hubspot_events_definition_property_delete':
            return _del(c, f"analytics/v2/event-definitions/{args['eventName']}/properties/{args['propertyName']}")

        # ── Fire behavioral events ──────────────────────────────────
        case 'hubspot_events_send_v3':
            return c._post_json("events/v3/send", args.get('body', {}))

        # ── Analytics Reporting ─────────────────────────────────────
        case 'hubspot_analytics_reports_list':
            return c._get("analytics/v2/reports")
        case 'hubspot_analytics_events_list':
            return c._get(f"analytics/v2/events?objectType={args['objectType']}&objectId={args['objectId']}")
        case 'hubspot_analytics_web_analytics':
            return c._get(f"analytics/v1/analytics/by-event?start={args['start']}&end={args['end']}")
        case 'hubspot_analytics_contact_events':
            return c._get(f"analytics/v2/events?objectType=contacts&objectId={args['contactId']}")

        # ── Goals ───────────────────────────────────────────────────
        case 'hubspot_goals_list':
            return c._get("crm/v3/goals/goal-targets")
        case 'hubspot_goal_get':
            return c._get(f"crm/v3/goals/goal-targets/{args['goalTargetId']}")
        case 'hubspot_goal_create':
            return c._post_json("crm/v3/goals/goal-targets", args.get('body', {}))
        case 'hubspot_goal_update':
            return c._patch(f"crm/v3/goals/goal-targets/{args['goalTargetId']}", args.get('body', {}))
        case 'hubspot_goal_delete':
            return _del(c, f"crm/v3/goals/goal-targets/{args['goalTargetId']}")

        # ══════════════════════════════════════════════════════════════
        # HUB 5 — OAuth & App Info
        # ══════════════════════════════════════════════════════════════

        case 'hubspot_oauth_token_info':
            return c._get(f"oauth/v1/access-tokens/{args['token']}")
        case 'hubspot_oauth_refresh':
            body = {
                "grant_type": "refresh_token",
                "refresh_token": args['refresh_token'],
                "client_id": args['client_id'],
                "client_secret": args['client_secret'],
            }
            return c._post_json("oauth/v1/token", body)
        case 'hubspot_oauth_revoke':
            return _del(c, f"oauth/v1/refresh-tokens/{args['token']}")
        case 'hubspot_app_info_get':
            return c._get("integrations/v1/me")
        case 'hubspot_integrations_installed_apps':
            return c._get("integrations/v1/connected-apps")

        # ── Webhooks Subscriptions v3 ───────────────────────────────
        case 'hubspot_webhooks_app_settings_get':
            return c._get(f"webhooks/v3/{args['appId']}/settings")
        case 'hubspot_webhooks_app_settings_update':
            return c._put(f"webhooks/v3/{args['appId']}/settings", args.get('body', {}))
        case 'hubspot_webhooks_subscriptions_list':
            return c._get(f"webhooks/v3/{args['appId']}/subscriptions")
        case 'hubspot_webhooks_subscription_get':
            return c._get(f"webhooks/v3/{args['appId']}/subscriptions/{args['subscriptionId']}")
        case 'hubspot_webhooks_subscription_create':
            return c._post_json(f"webhooks/v3/{args['appId']}/subscriptions", args.get('body', {}))
        case 'hubspot_webhooks_subscription_update':
            return c._patch(f"webhooks/v3/{args['appId']}/subscriptions/{args['subscriptionId']}", args.get('body', {}))
        case 'hubspot_webhooks_subscription_delete':
            return _del(c, f"webhooks/v3/{args['appId']}/subscriptions/{args['subscriptionId']}")
        case 'hubspot_webhooks_subscriptions_batch_update':
            return c._post_json(f"webhooks/v3/{args['appId']}/subscriptions/batch/update", {"inputs": args['inputs']})

        # ══════════════════════════════════════════════════════════════
        # HUB 6 — Settings (Users/Permissions/Roles full)
        # ══════════════════════════════════════════════════════════════

        case 'hubspot_settings_users_batch_create':
            return c._post_json("settings/v3/users/batch/create", {"inputs": args['inputs']})
        case 'hubspot_settings_users_batch_update':
            return c._post_json("settings/v3/users/batch/update", {"inputs": args['inputs']})
        case 'hubspot_settings_user_roles_list':
            return c._get(f"settings/v3/users/{args['userId']}/roles")
        case 'hubspot_settings_user_teams_list':
            return c._get(f"settings/v3/users/{args['userId']}/teams")

        # ── Permission Sets ─────────────────────────────────────────
        case 'hubspot_permission_sets_list':
            return c._get("settings/v3/users/roles")
        case 'hubspot_permission_set_get':
            return c._get(f"settings/v3/users/roles/{args['roleId']}")
        case 'hubspot_permission_set_create':
            return c._post_json("settings/v3/users/roles", args.get('body', {}))
        case 'hubspot_permission_set_delete':
            return _del(c, f"settings/v3/users/roles/{args['roleId']}")

        # ── Account Info ────────────────────────────────────────────
        case 'hubspot_account_info_get':
            return c._get("account-info/v3/details")
        case 'hubspot_account_info_api_usage':
            return c._get("account-info/v3/api-usage/daily")
        case 'hubspot_account_info_api_limits':
            return c._get("account-info/v3/api-usage/monthly")

        # ── Account Activity ────────────────────────────────────────
        case 'hubspot_account_activity_login_list':
            return c._get("settings/v3/activity/login")
        case 'hubspot_account_activity_security_list':
            return c._get("settings/v3/activity/security")

        # ── CRM Property Options extras ─────────────────────────────
        case 'hubspot_property_options_list':
            return c._get(f"crm/v3/properties/{args['objectType']}/{args['propertyName']}/options")
        case 'hubspot_property_options_create':
            return c._post_json(f"crm/v3/properties/{args['objectType']}/{args['propertyName']}/options", args.get('body', {}))
        case 'hubspot_property_options_update':
            return c._patch(f"crm/v3/properties/{args['objectType']}/{args['propertyName']}/options/{args['optionId']}", args.get('body', {}))
        case 'hubspot_property_options_delete':
            return _del(c, f"crm/v3/properties/{args['objectType']}/{args['propertyName']}/options/{args['optionId']}")

        # ══════════════════════════════════════════════════════════════
        # HUB 7 — Service Hub / Knowledge Base
        # ══════════════════════════════════════════════════════════════

        # ── Knowledge Base Articles ─────────────────────────────────
        case 'hubspot_kb_articles_list':
            return c._get(f"content/api/v2/articles?limit={args.get('limit', 50)}")
        case 'hubspot_kb_article_get':
            return c._get(f"content/api/v2/articles/{args['articleId']}")
        case 'hubspot_kb_article_create':
            return c._post_json("content/api/v2/articles", args.get('body', {}))
        case 'hubspot_kb_article_update':
            return c._patch(f"content/api/v2/articles/{args['articleId']}", args.get('body', {}))
        case 'hubspot_kb_article_delete':
            return _del(c, f"content/api/v2/articles/{args['articleId']}")
        case 'hubspot_kb_article_publish':
            return c._post_json(f"content/api/v2/articles/{args['articleId']}/push-live", {})
        case 'hubspot_kb_article_clone':
            return c._post_json("content/api/v2/articles/clone", {"id": args['articleId']})
        case 'hubspot_kb_articles_batch_archive':
            return c._post_json("content/api/v2/articles/batch/destroy", {"inputs": args['inputs']})

        # ── Knowledge Base Categories ───────────────────────────────
        case 'hubspot_kb_categories_list':
            return c._get("content/api/v2/article-categories")
        case 'hubspot_kb_category_get':
            return c._get(f"content/api/v2/article-categories/{args['categoryId']}")
        case 'hubspot_kb_category_create':
            return c._post_json("content/api/v2/article-categories", args.get('body', {}))
        case 'hubspot_kb_category_update':
            return c._patch(f"content/api/v2/article-categories/{args['categoryId']}", args.get('body', {}))
        case 'hubspot_kb_category_delete':
            return _del(c, f"content/api/v2/article-categories/{args['categoryId']}")

        # ── Feedback Surveys ────────────────────────────────────────
        case 'hubspot_feedback_surveys_list':
            return c._get("feedback/v1/dashboards")
        case 'hubspot_feedback_survey_responses':
            return c._get(f"feedback/v1/submissions?startDate={args['startDate']}&endDate={args['endDate']}")

        # ── Conversations Custom Channels ───────────────────────────
        case 'hubspot_conv_custom_channels_list':
            return c._get("conversations/v3/conversations/custom-channels")
        case 'hubspot_conv_custom_channel_create':
            return c._post_json("conversations/v3/conversations/custom-channels", args.get('body', {}))
        case 'hubspot_conv_custom_channel_get':
            return c._get(f"conversations/v3/conversations/custom-channels/{args['channelId']}")
        case 'hubspot_conv_custom_channel_delete':
            return _del(c, f"conversations/v3/conversations/custom-channels/{args['channelId']}")
        case 'hubspot_conv_channel_account_create':
            return c._post_json(f"conversations/v3/conversations/custom-channels/{args['channelId']}/channel-accounts", args.get('body', {}))

        # ══════════════════════════════════════════════════════════════
        # HUB 8 — CRM extras finais
        # ══════════════════════════════════════════════════════════════

        # ── Products extras ─────────────────────────────────────────
        case 'hubspot_products_search':
            return _search_objects(c, 'products', args['query'], limit=args.get('limit', 50))
        case 'hubspot_products_batch_create':
            return c._post_json("crm/v3/objects/products/batch/create", {"inputs": args['inputs']})
        case 'hubspot_products_batch_update':
            return c._post_json("crm/v3/objects/products/batch/update", {"inputs": args['inputs']})
        case 'hubspot_products_batch_archive':
            return c._post_json("crm/v3/objects/products/batch/archive", {"inputs": args['inputs']})
        case 'hubspot_products_batch_read':
            return c._post_json("crm/v3/objects/products/batch/read", {"inputs": args['inputs']})

        # ── Quotes extras ──────────────────────────────────────────
        case 'hubspot_quotes_search':
            return _search_objects(c, 'quotes', args['query'], limit=args.get('limit', 50))
        case 'hubspot_quotes_associations_list':
            return c._get(f"crm/v4/objects/quotes/{args['quoteId']}/associations/{args['toObjectType']}")
        case 'hubspot_quotes_associations_create':
            return c._put(f"crm/v4/objects/quotes/{args['quoteId']}/associations/{args['toObjectType']}/{args['toObjectId']}/{args['associationTypeId']}", {})
        case 'hubspot_quote_approve':
            return c._patch(f"crm/v3/objects/quotes/{args['quoteId']}", {"properties": {"hs_status": "APPROVED"}})

        # ── Line Items extras ──────────────────────────────────────
        case 'hubspot_lineitems_search':
            return _search_objects(c, 'line_items', args['query'], limit=args.get('limit', 50))
        case 'hubspot_lineitems_associations':
            return c._get(f"crm/v4/objects/line_items/{args['lineItemId']}/associations/{args['toObjectType']}")

        # ── Postal Mail extras ─────────────────────────────────────
        case 'hubspot_postal_mail_create':
            return c._post_json("crm/v3/objects/postal_mail", {"properties": args['properties']})
        case 'hubspot_postal_mail_update':
            return c._patch(f"crm/v3/objects/postal_mail/{args['postalMailId']}", {"properties": args['properties']})
        case 'hubspot_postal_mail_delete':
            return _del(c, f"crm/v3/objects/postal_mail/{args['postalMailId']}")

        # ── Calls extras ───────────────────────────────────────────
        case 'hubspot_calls_update':
            return c._patch(f"crm/v3/objects/calls/{args['callId']}", {"properties": args['properties']})
        case 'hubspot_calls_delete':
            return _del(c, f"crm/v3/objects/calls/{args['callId']}")
        case 'hubspot_calls_search':
            return _search_objects(c, 'calls', args['query'], limit=args.get('limit', 50))

        # ── Emails extras ──────────────────────────────────────────
        case 'hubspot_emails_create':
            return c._post_json("crm/v3/objects/emails", {"properties": args['properties']})
        case 'hubspot_emails_update':
            return c._patch(f"crm/v3/objects/emails/{args['emailId']}", {"properties": args['properties']})
        case 'hubspot_emails_delete':
            return _del(c, f"crm/v3/objects/emails/{args['emailId']}")
        case 'hubspot_emails_search':
            return _search_objects(c, 'emails', args['query'], limit=args.get('limit', 50))

        # ── Meetings extras ────────────────────────────────────────
        case 'hubspot_meetings_create':
            return c._post_json("crm/v3/objects/meetings", {"properties": args['properties']})
        case 'hubspot_meetings_update':
            return c._patch(f"crm/v3/objects/meetings/{args['meetingId']}", {"properties": args['properties']})
        case 'hubspot_meetings_delete':
            return _del(c, f"crm/v3/objects/meetings/{args['meetingId']}")
        case 'hubspot_meetings_search':
            return _search_objects(c, 'meetings', args['query'], limit=args.get('limit', 50))

        # ── Notes extras ───────────────────────────────────────────
        case 'hubspot_notes_update':
            return c._patch(f"crm/v3/objects/notes/{args['noteId']}", {"properties": args['properties']})
        case 'hubspot_notes_delete':
            return _del(c, f"crm/v3/objects/notes/{args['noteId']}")
        case 'hubspot_notes_search':
            return _search_objects(c, 'notes', args['query'], limit=args.get('limit', 50))

        # ── Custom Objects extras ──────────────────────────────────
        case 'hubspot_custom_objects_update':
            return c._patch(f"crm/v3/objects/{args['objectType']}/{args['objectId']}", {"properties": args['properties']})
        case 'hubspot_custom_objects_delete':
            return _del(c, f"crm/v3/objects/{args['objectType']}/{args['objectId']}")
        case 'hubspot_custom_objects_search':
            return _search_objects(c, args['objectType'], args['query'], limit=args.get('limit', 50))
        case 'hubspot_custom_objects_batch_create':
            return c._post_json(f"crm/v3/objects/{args['objectType']}/batch/create", {"inputs": args['inputs']})
        case 'hubspot_custom_objects_batch_update':
            return c._post_json(f"crm/v3/objects/{args['objectType']}/batch/update", {"inputs": args['inputs']})
        case 'hubspot_custom_objects_schema_create':
            return c._post_json("crm/v3/schemas", args.get('body', {}))
        case 'hubspot_custom_objects_schema_update':
            return c._patch(f"crm/v3/schemas/{args['objectType']}", args.get('body', {}))
        case 'hubspot_custom_objects_schema_delete':
            return _del(c, f"crm/v3/schemas/{args['objectType']}")
        case 'hubspot_custom_objects_schema_labels':
            return c._post_json(f"crm/v3/schemas/{args['objectType']}/labels", args.get('body', {}))

        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
