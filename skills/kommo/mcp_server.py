#!/usr/bin/env python3
"""
MCP server para Kommo CRM (formerly amoCRM) — 55 tools.
Endpoints cobertos: leads, contacts, companies, customers, tasks,
pipelines, users, account, custom_fields, catalogs, events, calls,
tags, webhooks, notes, links, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from kommo_client import KommoClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('kommo')
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = KommoClient()
    return _client


def _t(name, desc, props, req=None):
    return types.Tool(name=name, description=desc, inputSchema={
        'type': 'object', 'properties': props, 'required': req or []})


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Leads ────────────────────────────────────────────────────────
        _t('kommo_leads_list', 'Lista leads/oportunidades do Kommo (paginado)', {
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
            'status': {'type': 'string', 'description': 'Filtro: open, won, lost, all', 'default': 'open'},
        }),
        _t('kommo_leads_get', 'Detalhes de um lead do Kommo', {
            'id': {'type': 'string', 'description': 'ID do lead'},
        }, ['id']),
        _t('kommo_leads_create', 'Cria novo lead no Kommo', {
            'name': {'type': 'string', 'description': 'Nome do lead'},
            'price': {'type': 'number', 'description': 'Valor do lead'},
            'pipeline_id': {'type': 'integer', 'description': 'ID do pipeline'},
            'status_id': {'type': 'integer', 'description': 'ID do status'},
            'responsible_user_id': {'type': 'integer', 'description': 'ID do responsavel'},
        }, ['name']),
        _t('kommo_leads_update', 'Atualiza lead no Kommo', {
            'id': {'type': 'string', 'description': 'ID do lead'},
            'name': {'type': 'string'}, 'price': {'type': 'number'},
            'status_id': {'type': 'integer'}, 'pipeline_id': {'type': 'integer'},
            'responsible_user_id': {'type': 'integer'},
        }, ['id']),
        _t('kommo_leads_delete', 'Exclui um lead do Kommo', {
            'id': {'type': 'string', 'description': 'ID do lead'},
        }, ['id']),
        _t('kommo_leads_notes_list', 'Lista notas de um lead', {
            'id': {'type': 'string', 'description': 'ID do lead'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }, ['id']),
        _t('kommo_leads_notes_create', 'Cria nota em um lead', {
            'id': {'type': 'string', 'description': 'ID do lead'},
            'text': {'type': 'string', 'description': 'Texto da nota'},
        }, ['id', 'text']),
        _t('kommo_leads_tags_list', 'Lista tags de leads', {}),
        _t('kommo_leads_links_list', 'Lista links/associacoes de um lead', {
            'id': {'type': 'string', 'description': 'ID do lead'},
        }, ['id']),
        _t('kommo_leads_links_add', 'Adiciona link/associacao a um lead', {
            'id': {'type': 'string', 'description': 'ID do lead'},
            'to_entity_type': {'type': 'string', 'description': 'Tipo da entidade destino (contacts, companies, etc)'},
            'to_entity_id': {'type': 'integer', 'description': 'ID da entidade destino'},
        }, ['id', 'to_entity_type', 'to_entity_id']),

        # ── Contacts ─────────────────────────────────────────────────────
        _t('kommo_contacts_list', 'Lista contatos do Kommo', {
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),
        _t('kommo_contacts_get', 'Detalhes de um contato', {
            'id': {'type': 'string', 'description': 'ID do contato'},
        }, ['id']),
        _t('kommo_contacts_create', 'Cria contato no Kommo', {
            'name': {'type': 'string'}, 'email': {'type': 'string'},
            'phone': {'type': 'string'},
        }, ['name']),
        _t('kommo_contacts_update', 'Atualiza contato no Kommo', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
            'email': {'type': 'string'}, 'phone': {'type': 'string'},
        }, ['id']),
        _t('kommo_contacts_notes_list', 'Lista notas de um contato', {
            'id': {'type': 'string', 'description': 'ID do contato'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }, ['id']),
        _t('kommo_contacts_notes_create', 'Cria nota em um contato', {
            'id': {'type': 'string', 'description': 'ID do contato'},
            'text': {'type': 'string', 'description': 'Texto da nota'},
        }, ['id', 'text']),
        _t('kommo_contacts_links_list', 'Lista links de um contato', {
            'id': {'type': 'string', 'description': 'ID do contato'},
        }, ['id']),

        # ── Companies ────────────────────────────────────────────────────
        _t('kommo_companies_list', 'Lista empresas do Kommo', {
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),
        _t('kommo_companies_get', 'Detalhes de uma empresa', {
            'id': {'type': 'string', 'description': 'ID da empresa'},
        }, ['id']),
        _t('kommo_companies_create', 'Cria empresa no Kommo', {
            'name': {'type': 'string'},
        }, ['name']),
        _t('kommo_companies_update', 'Atualiza empresa no Kommo', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
        }, ['id']),
        _t('kommo_companies_notes_list', 'Lista notas de empresa', {
            'id': {'type': 'string', 'description': 'ID da empresa'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }, ['id']),
        _t('kommo_companies_notes_create', 'Cria nota em empresa', {
            'id': {'type': 'string', 'description': 'ID da empresa'},
            'text': {'type': 'string', 'description': 'Texto da nota'},
        }, ['id', 'text']),
        _t('kommo_companies_links_list', 'Lista links de empresa', {
            'id': {'type': 'string', 'description': 'ID da empresa'},
        }, ['id']),

        # ── Customers (segments) ─────────────────────────────────────────
        _t('kommo_customers_list', 'Lista customers/segmentos do Kommo', {
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),
        _t('kommo_customers_get', 'Detalhes de um customer', {
            'id': {'type': 'string', 'description': 'ID do customer'},
        }, ['id']),
        _t('kommo_customers_create', 'Cria customer no Kommo', {
            'name': {'type': 'string'},
        }, ['name']),
        _t('kommo_customers_update', 'Atualiza customer no Kommo', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
        }, ['id']),
        _t('kommo_customers_notes_list', 'Notas de customer', {
            'id': {'type': 'string', 'description': 'ID do customer'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }, ['id']),
        _t('kommo_customers_notes_create', 'Cria nota em customer', {
            'id': {'type': 'string', 'description': 'ID do customer'},
            'text': {'type': 'string', 'description': 'Texto da nota'},
        }, ['id', 'text']),

        # ── Tasks ────────────────────────────────────────────────────────
        _t('kommo_tasks_list', 'Lista tarefas do Kommo', {
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),
        _t('kommo_tasks_create', 'Cria tarefa no Kommo', {
            'text': {'type': 'string', 'description': 'Texto da tarefa'},
            'entity_id': {'type': 'integer', 'description': 'ID da entidade associada'},
            'entity_type': {'type': 'string', 'description': 'Tipo da entidade (leads, contacts, companies, customers)'},
            'complete_till': {'type': 'integer', 'description': 'Timestamp UNIX para conclusao'},
            'task_type_id': {'type': 'integer', 'description': 'ID do tipo de tarefa'},
        }, ['text']),
        _t('kommo_tasks_update', 'Atualiza tarefa no Kommo', {
            'id': {'type': 'string', 'description': 'ID da tarefa'},
            'text': {'type': 'string'}, 'complete_till': {'type': 'integer'},
        }, ['id']),
        _t('kommo_tasks_complete', 'Marca tarefa como completa', {
            'id': {'type': 'string', 'description': 'ID da tarefa'},
        }, ['id']),

        # ── Pipelines ───────────────────────────────────────────────────
        _t('kommo_pipelines_list', 'Lista pipelines/funis do Kommo', {}),
        _t('kommo_pipelines_get', 'Detalhes de um pipeline', {
            'id': {'type': 'string', 'description': 'ID do pipeline'},
        }, ['id']),
        _t('kommo_pipelines_statuses_list', 'Lista statuses de um pipeline', {
            'pipeline_id': {'type': 'string', 'description': 'ID do pipeline'},
        }, ['pipeline_id']),

        # ── Users ───────────────────────────────────────────────────────
        _t('kommo_users_list', 'Lista usuarios do Kommo', {}),
        _t('kommo_users_get', 'Detalhes de um usuario', {
            'id': {'type': 'string', 'description': 'ID do usuario'},
        }, ['id']),

        # ── Account ─────────────────────────────────────────────────────
        _t('kommo_account_get', 'Info da conta Kommo', {}),

        # ── Custom Fields ───────────────────────────────────────────────
        _t('kommo_custom_fields_list', 'Lista campos customizados por entidade', {
            'entity_type': {'type': 'string', 'description': 'Tipo: leads, contacts, companies, customers'},
        }, ['entity_type']),

        # ── Catalogs ────────────────────────────────────────────────────
        _t('kommo_catalogs_list', 'Lista catalogos do Kommo', {}),
        _t('kommo_catalogs_get', 'Detalhes de um catalogo', {
            'id': {'type': 'string', 'description': 'ID do catalogo'},
        }, ['id']),
        _t('kommo_catalogs_elements_list', 'Lista elementos de um catalogo', {
            'catalog_id': {'type': 'string', 'description': 'ID do catalogo'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }, ['catalog_id']),

        # ── Events ──────────────────────────────────────────────────────
        _t('kommo_events_list', 'Lista eventos/log de atividades do Kommo', {
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),

        # ── Calls ───────────────────────────────────────────────────────
        _t('kommo_calls_log', 'Registra chamada no Kommo', {
            'direction': {'type': 'string', 'description': 'inbound ou outbound'},
            'uniq': {'type': 'string', 'description': 'ID unico da chamada'},
            'duration': {'type': 'integer', 'description': 'Duracao em segundos'},
            'source': {'type': 'string', 'description': 'Fonte da chamada'},
            'phone': {'type': 'string', 'description': 'Numero de telefone'},
            'entity_id': {'type': 'integer', 'description': 'ID da entidade associada'},
            'entity_type': {'type': 'string', 'description': 'Tipo da entidade'},
        }, ['direction', 'uniq', 'duration', 'source', 'phone']),

        # ── Tags ────────────────────────────────────────────────────────
        _t('kommo_tags_list', 'Lista tags por entidade', {
            'entity_type': {'type': 'string', 'description': 'Tipo: leads, contacts, companies, customers'},
        }, ['entity_type']),

        # ── Webhooks ────────────────────────────────────────────────────
        _t('kommo_webhooks_list', 'Lista webhooks configurados', {}),
        _t('kommo_webhooks_create', 'Cria webhook no Kommo', {
            'destination': {'type': 'string', 'description': 'URL de destino'},
            'settings': {'type': 'array', 'description': 'Lista de eventos para assinar', 'items': {'type': 'string'}},
        }, ['destination']),
        _t('kommo_webhooks_delete', 'Exclui webhook', {
            'id': {'type': 'string', 'description': 'ID do webhook'},
        }, ['id']),

        # ── Deals unified (BaseCRMClient) ────────────────────────────────
        _t('kommo_deals_listar', 'Lista deals/oportunidades (interface unificada)', {
            'status': {'type': 'string', 'description': 'Filtro: open, won, lost, all', 'default': 'open'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),
        _t('kommo_deal_mover', 'Move deal para outra etapa/status', {
            'id': {'type': 'string'}, 'to_stage': {'type': 'string', 'description': 'ID do status destino'},
        }, ['id', 'to_stage']),
        _t('kommo_deal_ganho', 'Marca deal como ganho/won', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('kommo_deal_perdido', 'Marca deal como perdido/lost', {
            'id': {'type': 'string'}, 'reason': {'type': 'string'},
        }, ['id']),
        _t('kommo_empresa', 'Informacoes da empresa conectada ao Kommo', {}),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = _dispatch(name, arguments)
        return [types.TextContent(type='text', text=json.dumps(result, ensure_ascii=False, default=str))]
    except Exception as e:
        return [types.TextContent(type='text', text=json.dumps({'error': str(e)}))]


def _dispatch(name: str, args: dict):
    c = _get_client()
    match name:
        # ── Leads ────────────────────────────────────────────────────
        case 'kommo_leads_list':
            return c.list_deals(status=args.get('status', 'open'), limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_leads_get':
            return c.get_lead(args['id'])
        case 'kommo_leads_create':
            body = {"name": args['name']}
            if args.get('price') is not None:
                body["price"] = args['price']
            if args.get('pipeline_id'):
                body["pipeline_id"] = args['pipeline_id']
            if args.get('status_id'):
                body["status_id"] = args['status_id']
            if args.get('responsible_user_id'):
                body["responsible_user_id"] = args['responsible_user_id']
            raw = c._post("leads", [body])
            embedded = c._extract_embedded(raw, "leads")
            new_id = str(embedded[0].get("id", "")) if embedded else ""
            return {"success": True, "action": "create_lead", "id": new_id, "raw": raw}
        case 'kommo_leads_update':
            return c.update_lead(args['id'], name=args.get('name'), price=args.get('price'),
                                 status_id=args.get('status_id'), pipeline_id=args.get('pipeline_id'),
                                 responsible_user_id=args.get('responsible_user_id'))
        case 'kommo_leads_delete':
            return c.delete_lead(args['id'])
        case 'kommo_leads_notes_list':
            return c.list_notes("leads", args['id'], limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_leads_notes_create':
            return c.create_note("leads", args['id'], args['text'])
        case 'kommo_leads_tags_list':
            return c.list_tags("leads")
        case 'kommo_leads_links_list':
            return c.list_links("leads", args['id'])
        case 'kommo_leads_links_add':
            return c.add_link("leads", args['id'], args['to_entity_type'], args['to_entity_id'])

        # ── Contacts ─────────────────────────────────────────────────
        case 'kommo_contacts_list':
            return c.list_contacts(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_contacts_get':
            return c.get_contact(args['id'])
        case 'kommo_contacts_create':
            return c.create_contact(name=args['name'], email=args.get('email'), phone=args.get('phone'))
        case 'kommo_contacts_update':
            return c.update_contact(args['id'], name=args.get('name'), email=args.get('email'), phone=args.get('phone'))
        case 'kommo_contacts_notes_list':
            return c.list_notes("contacts", args['id'], limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_contacts_notes_create':
            return c.create_note("contacts", args['id'], args['text'])
        case 'kommo_contacts_links_list':
            return c.list_links("contacts", args['id'])

        # ── Companies ────────────────────────────────────────────────
        case 'kommo_companies_list':
            return c.list_companies(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_companies_get':
            return c.get_company(args['id'])
        case 'kommo_companies_create':
            return c.create_company(name=args['name'])
        case 'kommo_companies_update':
            return c.update_company(args['id'], name=args.get('name'))
        case 'kommo_companies_notes_list':
            return c.list_notes("companies", args['id'], limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_companies_notes_create':
            return c.create_note("companies", args['id'], args['text'])
        case 'kommo_companies_links_list':
            return c.list_links("companies", args['id'])

        # ── Customers ────────────────────────────────────────────────
        case 'kommo_customers_list':
            return c.list_customers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_customers_get':
            return c.get_customer(args['id'])
        case 'kommo_customers_create':
            return c.create_customer(name=args['name'])
        case 'kommo_customers_update':
            return c.update_customer(args['id'], name=args.get('name'))
        case 'kommo_customers_notes_list':
            return c.list_notes("customers", args['id'], limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_customers_notes_create':
            return c.create_note("customers", args['id'], args['text'])

        # ── Tasks ────────────────────────────────────────────────────
        case 'kommo_tasks_list':
            return c.list_tasks(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_tasks_create':
            return c.create_task(text=args['text'], entity_id=args.get('entity_id'),
                                 entity_type=args.get('entity_type'), complete_till=args.get('complete_till'),
                                 task_type_id=args.get('task_type_id'))
        case 'kommo_tasks_update':
            return c.update_task(args['id'], text=args.get('text'), complete_till=args.get('complete_till'))
        case 'kommo_tasks_complete':
            return c.complete_task(args['id'])

        # ── Pipelines ────────────────────────────────────────────────
        case 'kommo_pipelines_list':
            return c.list_pipelines()
        case 'kommo_pipelines_get':
            return c.get_pipeline(args['id'])
        case 'kommo_pipelines_statuses_list':
            return c.list_pipeline_statuses(args['pipeline_id'])

        # ── Users ────────────────────────────────────────────────────
        case 'kommo_users_list':
            return c.list_users()
        case 'kommo_users_get':
            return c.get_user(args['id'])

        # ── Account ──────────────────────────────────────────────────
        case 'kommo_account_get':
            return c.get_account()

        # ── Custom Fields ────────────────────────────────────────────
        case 'kommo_custom_fields_list':
            return c.list_custom_fields(args['entity_type'])

        # ── Catalogs ─────────────────────────────────────────────────
        case 'kommo_catalogs_list':
            return c.list_catalogs()
        case 'kommo_catalogs_get':
            return c.get_catalog(args['id'])
        case 'kommo_catalogs_elements_list':
            return c.list_catalog_elements(args['catalog_id'], limit=args.get('limit', 50), page=args.get('page', 1))

        # ── Events ───────────────────────────────────────────────────
        case 'kommo_events_list':
            return c.list_events(limit=args.get('limit', 50), page=args.get('page', 1))

        # ── Calls ────────────────────────────────────────────────────
        case 'kommo_calls_log':
            return c.log_call(direction=args['direction'], uniq=args['uniq'],
                              duration=args['duration'], source=args['source'],
                              phone=args['phone'], entity_id=args.get('entity_id'),
                              entity_type=args.get('entity_type'))

        # ── Tags ─────────────────────────────────────────────────────
        case 'kommo_tags_list':
            return c.list_tags(args['entity_type'])

        # ── Webhooks ─────────────────────────────────────────────────
        case 'kommo_webhooks_list':
            return c.list_webhooks()
        case 'kommo_webhooks_create':
            return c.create_webhook(destination=args['destination'], settings=args.get('settings'))
        case 'kommo_webhooks_delete':
            return c.delete_webhook(args['id'])

        # ── Deals unified (BaseCRMClient) ────────────────────────────
        case 'kommo_deals_listar':
            return c.list_deals(status=args.get('status', 'open'), limit=args.get('limit', 50), page=args.get('page', 1))
        case 'kommo_deal_mover':
            return c.move_deal(args['id'], args['to_stage'])
        case 'kommo_deal_ganho':
            return c.mark_deal_won(args['id'])
        case 'kommo_deal_perdido':
            return c.mark_deal_lost(args['id'], reason=args.get('reason', ''))
        case 'kommo_empresa':
            return c.company_info()

        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
