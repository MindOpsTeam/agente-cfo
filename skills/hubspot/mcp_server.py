#!/usr/bin/env python3
"""
MCP server para HubSpot — 133 tools.
CRM completo: deals, contacts, companies, tickets, line_items, notes, calls,
emails, meetings, tasks, pipelines, owners, properties, quotes, associations,
products, forms, marketing emails, feedback, custom objects, communications,
postal mail. Batch operations para todos os objetos principais.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from hubspot_client import HubSpotClient

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

        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
