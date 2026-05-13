#!/usr/bin/env python3
"""
MCP server para Pipedrive — 35 tools.
Endpoints cobertos: deals, persons, organizations, activities, products,
pipelines, stages, notes, users, webhooks, goals, filters, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from pipedrive_client import PipedriveClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('pipedrive')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = PipedriveClient()
    return _client


def _t(name, desc, props, req=None):
    return types.Tool(name=name, description=desc, inputSchema={
        'type': 'object', 'properties': props, 'required': req or []})


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Deals ────────────────────────────────────────────────────────
        _t('pipedrive_deals_listar', 'Lista deals/oportunidades do Pipedrive (paginado)', {
            'status': {'type': 'string', 'description': 'Filtro: open, won, lost, all', 'default': 'open'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),
        _t('pipedrive_deal_detalhar', 'Retorna detalhes de um deal do Pipedrive', {
            'id': {'type': 'string', 'description': 'ID do deal'},
        }, ['id']),
        _t('pipedrive_deal_criar', 'Cria novo deal/oportunidade no Pipedrive', {
            'title': {'type': 'string'}, 'amount': {'type': 'number'},
            'pipeline': {'type': 'string', 'description': 'Pipeline ID ou nome'},
        }, ['title']),
        _t('pipedrive_deal_atualizar', 'Atualiza valor e/ou data de fechamento do deal', {
            'id': {'type': 'string'}, 'amount': {'type': 'number'},
            'close_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
        }, ['id']),
        _t('pipedrive_deal_mover', 'Move deal para outra etapa/stage', {
            'id': {'type': 'string'}, 'to_stage': {'type': 'string', 'description': 'Nome ou ID da etapa'},
        }, ['id', 'to_stage']),
        _t('pipedrive_deal_nota', 'Adiciona nota a um deal', {
            'id': {'type': 'string'}, 'note': {'type': 'string'},
        }, ['id', 'note']),
        _t('pipedrive_deal_ganho', 'Marca deal como ganho/won', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_deal_perdido', 'Marca deal como perdido/lost', {
            'id': {'type': 'string'}, 'reason': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_deal_excluir', 'Exclui um deal do Pipedrive', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Persons (Contacts) ───────────────────────────────────────────
        _t('pipedrive_contatos_listar', 'Lista contatos/persons do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_contato_detalhar', 'Detalhes de um contato/person', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_contato_criar', 'Cria contato/person no Pipedrive', {
            'name': {'type': 'string'}, 'email': {'type': 'string'},
            'phone': {'type': 'string'}, 'org_id': {'type': 'integer'},
        }, ['name']),
        _t('pipedrive_contato_atualizar', 'Atualiza contato/person', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
            'email': {'type': 'string'}, 'phone': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_contato_excluir', 'Exclui contato/person', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Organizations ────────────────────────────────────────────────
        _t('pipedrive_organizacoes_listar', 'Lista organizacoes do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_organizacao_detalhar', 'Detalhes de uma organizacao', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_organizacao_criar', 'Cria organizacao no Pipedrive', {
            'name': {'type': 'string'}, 'address': {'type': 'string'},
        }, ['name']),
        _t('pipedrive_organizacao_atualizar', 'Atualiza organizacao', {
            'id': {'type': 'string'}, 'name': {'type': 'string'}, 'address': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_organizacao_excluir', 'Exclui organizacao', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Activities ───────────────────────────────────────────────────
        _t('pipedrive_atividades_listar', 'Lista atividades do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_atividade_criar', 'Cria atividade (call, task, meeting, etc)', {
            'subject': {'type': 'string'}, 'type': {'type': 'string', 'default': 'task'},
            'due_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
            'deal_id': {'type': 'integer'}, 'person_id': {'type': 'integer'},
        }, ['subject']),

        # ── Products ────────────────────────────────────────────────────
        _t('pipedrive_produtos_listar', 'Lista produtos do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_produto_detalhar', 'Detalhes de um produto', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_produto_criar', 'Cria produto no Pipedrive', {
            'name': {'type': 'string'}, 'code': {'type': 'string'},
            'unit': {'type': 'string'}, 'price': {'type': 'number'},
        }, ['name']),

        # ── Pipelines ───────────────────────────────────────────────────
        _t('pipedrive_pipelines_listar', 'Lista pipelines/funis do Pipedrive', {}),

        # ── Stages ──────────────────────────────────────────────────────
        _t('pipedrive_stages_listar', 'Lista etapas/stages (opcao: filtrar por pipeline)', {
            'pipeline_id': {'type': 'integer', 'description': 'ID do pipeline (opcional)'},
        }),

        # ── Notes ───────────────────────────────────────────────────────
        _t('pipedrive_notas_listar', 'Lista notas do Pipedrive', {
            'deal_id': {'type': 'integer'}, 'person_id': {'type': 'integer'},
            'limit': {'type': 'integer', 'default': 50}, 'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_nota_criar', 'Cria nota associada a deal/person/org', {
            'content': {'type': 'string'}, 'deal_id': {'type': 'integer'},
            'person_id': {'type': 'integer'}, 'org_id': {'type': 'integer'},
        }, ['content']),

        # ── Users ───────────────────────────────────────────────────────
        _t('pipedrive_usuarios_listar', 'Lista usuarios do Pipedrive', {}),

        # ── Webhooks ────────────────────────────────────────────────────
        _t('pipedrive_webhooks_listar', 'Lista webhooks configurados', {}),
        _t('pipedrive_webhook_criar', 'Cria webhook no Pipedrive', {
            'subscription_url': {'type': 'string'}, 'event_action': {'type': 'string', 'description': 'added, updated, merged, deleted, *'},
            'event_object': {'type': 'string', 'description': 'deal, person, organization, etc'},
        }, ['subscription_url', 'event_action', 'event_object']),
        _t('pipedrive_webhook_excluir', 'Exclui webhook', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Goals ───────────────────────────────────────────────────────
        _t('pipedrive_goals_listar', 'Lista goals/metas do Pipedrive', {}),

        # ── Filters ─────────────────────────────────────────────────────
        _t('pipedrive_filtros_listar', 'Lista filtros salvos do Pipedrive', {
            'type': {'type': 'string', 'description': 'Tipo: deals, persons, orgs, etc'},
        }),

        # ── Empresa ─────────────────────────────────────────────────────
        _t('pipedrive_empresa', 'Informacoes da empresa conectada ao Pipedrive', {}),
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
        # Deals
        case 'pipedrive_deals_listar':
            return c.list_deals(status=args.get('status', 'open'), limit=args.get('limit', 50), page=args.get('page', 1))
        case 'pipedrive_deal_detalhar':
            return c.get_deal(args['id'])
        case 'pipedrive_deal_criar':
            return c.create_deal(title=args['title'], amount=args.get('amount'), pipeline=args.get('pipeline'))
        case 'pipedrive_deal_atualizar':
            return c.update_deal(args['id'], amount=args.get('amount'), close_date=args.get('close_date'))
        case 'pipedrive_deal_mover':
            return c.move_deal(args['id'], args['to_stage'])
        case 'pipedrive_deal_nota':
            return c.add_deal_note(args['id'], args['note'])
        case 'pipedrive_deal_ganho':
            return c.mark_deal_won(args['id'])
        case 'pipedrive_deal_perdido':
            return c.mark_deal_lost(args['id'], reason=args.get('reason', ''))
        case 'pipedrive_deal_excluir':
            return c.delete_deal(args['id'])
        # Persons
        case 'pipedrive_contatos_listar':
            return c.list_persons(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_contato_detalhar':
            return c.get_person(args['id'])
        case 'pipedrive_contato_criar':
            return c.create_person(name=args['name'], email=args.get('email'), phone=args.get('phone'), org_id=args.get('org_id'))
        case 'pipedrive_contato_atualizar':
            return c.update_person(args['id'], name=args.get('name'), email=args.get('email'), phone=args.get('phone'))
        case 'pipedrive_contato_excluir':
            return c.delete_person(args['id'])
        # Organizations
        case 'pipedrive_organizacoes_listar':
            return c.list_organizations(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_organizacao_detalhar':
            return c.get_organization(args['id'])
        case 'pipedrive_organizacao_criar':
            return c.create_organization(name=args['name'], address=args.get('address'))
        case 'pipedrive_organizacao_atualizar':
            return c.update_organization(args['id'], name=args.get('name'), address=args.get('address'))
        case 'pipedrive_organizacao_excluir':
            return c.delete_organization(args['id'])
        # Activities
        case 'pipedrive_atividades_listar':
            return c.list_activities(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_atividade_criar':
            return c.create_activity(subject=args['subject'], type=args.get('type', 'task'),
                                     due_date=args.get('due_date'), deal_id=args.get('deal_id'), person_id=args.get('person_id'))
        # Products
        case 'pipedrive_produtos_listar':
            return c.list_products(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_produto_detalhar':
            return c.get_product(args['id'])
        case 'pipedrive_produto_criar':
            return c.create_product(name=args['name'], code=args.get('code'), unit=args.get('unit'), price=args.get('price'))
        # Pipelines
        case 'pipedrive_pipelines_listar':
            return c.list_pipelines()
        # Stages
        case 'pipedrive_stages_listar':
            return c.list_stages(pipeline_id=args.get('pipeline_id'))
        # Notes
        case 'pipedrive_notas_listar':
            return c.list_notes(deal_id=args.get('deal_id'), person_id=args.get('person_id'),
                                limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_nota_criar':
            return c.create_note(content=args['content'], deal_id=args.get('deal_id'),
                                 person_id=args.get('person_id'), org_id=args.get('org_id'))
        # Users
        case 'pipedrive_usuarios_listar':
            return c.list_users()
        # Webhooks
        case 'pipedrive_webhooks_listar':
            return c.list_webhooks()
        case 'pipedrive_webhook_criar':
            return c.create_webhook(args['subscription_url'], args['event_action'], args['event_object'])
        case 'pipedrive_webhook_excluir':
            return c.delete_webhook(args['id'])
        # Goals
        case 'pipedrive_goals_listar':
            return c.list_goals()
        # Filters
        case 'pipedrive_filtros_listar':
            return c.list_filters(type=args.get('type'))
        # Empresa
        case 'pipedrive_empresa':
            return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
