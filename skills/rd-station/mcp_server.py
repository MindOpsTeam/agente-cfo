#!/usr/bin/env python3
"""
MCP server para RD Station — 30 tools.
Endpoints cobertos: deals CRUD, contatos CRUD, organizações CRUD, pipelines,
stages, atividades, campos customizados, usuários, produtos, origens.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from rd_station_client import RDStationClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('rd_station')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = RDStationClient()
    return _client

_PAGINATION = {
    'limit': {'type': 'integer', 'description': 'Limite por página (default 50)', 'default': 50},
    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
}
_ID_REQUIRED = {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'ID do registro'}}, 'required': ['id']}
_EMPTY = {'type': 'object', 'properties': {}, 'required': []}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Deals ────────────────────────────────────────────────────────
        types.Tool(name='rd_station_deals_listar', description='Lista deals/oportunidades do RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'status': {'type': 'string', 'description': 'Filtro (open, won, lost)', 'default': 'open'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='rd_station_deal_obter', description='Obtém detalhes de um deal pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='rd_station_deal_criar', description='Cria novo deal no RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'title': {'type': 'string', 'description': 'Título do deal'},
                       'amount': {'type': 'number', 'description': 'Valor do deal'},
                       'pipeline': {'type': 'string', 'description': 'ID do pipeline/funil'},
                   }, 'required': ['title']}),
        types.Tool(name='rd_station_deal_atualizar', description='Atualiza valor/data de fechamento do deal',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do deal'},
                       'amount': {'type': 'number', 'description': 'Novo valor'},
                       'close_date': {'type': 'string', 'description': 'Nova data de fechamento (YYYY-MM-DD)'},
                   }, 'required': ['id']}),
        types.Tool(name='rd_station_deal_mover', description='Move deal para outra etapa/stage',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do deal'},
                       'to_stage': {'type': 'string', 'description': 'ID da etapa destino'},
                   }, 'required': ['id', 'to_stage']}),
        types.Tool(name='rd_station_deal_nota', description='Adiciona nota a um deal',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do deal'},
                       'note': {'type': 'string', 'description': 'Texto da nota'},
                   }, 'required': ['id', 'note']}),
        types.Tool(name='rd_station_deal_ganho', description='Marca deal como ganho/won', inputSchema=_ID_REQUIRED),
        types.Tool(name='rd_station_deal_perdido', description='Marca deal como perdido/lost',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do deal'},
                       'reason': {'type': 'string', 'description': 'Motivo da perda'},
                   }, 'required': ['id']}),

        # ── Contatos ─────────────────────────────────────────────────────
        types.Tool(name='rd_station_contatos_listar', description='Lista contatos do RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por nome'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='rd_station_contato_obter', description='Obtém contato pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='rd_station_contato_criar', description='Cria novo contato no RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'phone': {'type': 'string', 'description': 'Telefone'},
                       'title': {'type': 'string', 'description': 'Cargo'},
                   }, 'required': ['name']}),
        types.Tool(name='rd_station_contato_atualizar', description='Atualiza contato no RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do contato'},
                       'name': {'type': 'string'}, 'email': {'type': 'string'},
                   }, 'required': ['id']}),
        types.Tool(name='rd_station_contato_excluir', description='Exclui contato pelo ID', inputSchema=_ID_REQUIRED),

        # ── Organizações ─────────────────────────────────────────────────
        types.Tool(name='rd_station_organizacoes_listar', description='Lista organizações/empresas do RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por nome'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='rd_station_organizacao_obter', description='Obtém organização pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='rd_station_organizacao_criar', description='Cria nova organização no RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome da organização'},
                       'segment': {'type': 'string', 'description': 'Segmento'},
                   }, 'required': ['name']}),
        types.Tool(name='rd_station_organizacao_atualizar', description='Atualiza organização no RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID'}, 'name': {'type': 'string'},
                   }, 'required': ['id']}),
        types.Tool(name='rd_station_organizacao_excluir', description='Exclui organização pelo ID', inputSchema=_ID_REQUIRED),

        # ── Pipelines/Funis ──────────────────────────────────────────────
        types.Tool(name='rd_station_pipelines_listar', description='Lista pipelines/funis do RD Station', inputSchema=_EMPTY),

        # ── Stages/Etapas ────────────────────────────────────────────────
        types.Tool(name='rd_station_stages_listar', description='Lista etapas do funil do RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'pipeline_id': {'type': 'string', 'description': 'ID do pipeline (opcional)'},
                   }, 'required': []}),

        # ── Atividades ───────────────────────────────────────────────────
        types.Tool(name='rd_station_atividades_listar', description='Lista atividades/tarefas do RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'deal_id': {'type': 'string', 'description': 'Filtrar por deal'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='rd_station_atividade_criar', description='Cria nova atividade no RD Station',
                   inputSchema={'type': 'object', 'properties': {
                       'deal_id': {'type': 'string', 'description': 'ID do deal'},
                       'subject': {'type': 'string', 'description': 'Assunto'},
                       'type': {'type': 'string', 'description': 'Tipo (call, email, meeting, task)'},
                       'date': {'type': 'string', 'description': 'Data (YYYY-MM-DD)'},
                   }, 'required': ['deal_id', 'subject']}),

        # ── Campos customizados ──────────────────────────────────────────
        types.Tool(name='rd_station_campos_custom_listar', description='Lista campos customizados do RD Station', inputSchema=_EMPTY),

        # ── Usuários ─────────────────────────────────────────────────────
        types.Tool(name='rd_station_usuarios_listar', description='Lista usuários do RD Station', inputSchema=_EMPTY),

        # ── Produtos ─────────────────────────────────────────────────────
        types.Tool(name='rd_station_produtos_listar', description='Lista produtos do RD Station',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),

        # ── Origens ──────────────────────────────────────────────────────
        types.Tool(name='rd_station_origens_listar', description='Lista origens de lead do RD Station', inputSchema=_EMPTY),

        # ── Empresa ──────────────────────────────────────────────────────
        types.Tool(name='rd_station_empresa', description='Informações da conta RD Station', inputSchema=_EMPTY),
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
        case 'rd_station_deals_listar':
            return c.list_deals(status=args.get('status', 'open'), limit=args.get('limit', 50), page=args.get('page', 1))
        case 'rd_station_deal_obter': return c.get_deal(args['id'])
        case 'rd_station_deal_criar':
            return c.create_deal(title=args['title'], amount=args.get('amount'), pipeline=args.get('pipeline'))
        case 'rd_station_deal_atualizar':
            return c.update_deal(args['id'], amount=args.get('amount'), close_date=args.get('close_date'))
        case 'rd_station_deal_mover': return c.move_deal(args['id'], args['to_stage'])
        case 'rd_station_deal_nota': return c.add_deal_note(args['id'], args['note'])
        case 'rd_station_deal_ganho': return c.mark_deal_won(args['id'])
        case 'rd_station_deal_perdido': return c.mark_deal_lost(args['id'], reason=args.get('reason', ''))
        # Contatos
        case 'rd_station_contatos_listar':
            return c.list_contacts(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search'))
        case 'rd_station_contato_obter': return c.get_contact(args['id'])
        case 'rd_station_contato_criar': return c.create_contact(args)
        case 'rd_station_contato_atualizar':
            id = args.pop('id'); return c.update_contact(id, args)
        case 'rd_station_contato_excluir': return c.delete_contact(args['id'])
        # Organizações
        case 'rd_station_organizacoes_listar':
            return c.list_organizations(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search'))
        case 'rd_station_organizacao_obter': return c.get_organization(args['id'])
        case 'rd_station_organizacao_criar': return c.create_organization(args)
        case 'rd_station_organizacao_atualizar':
            id = args.pop('id'); return c.update_organization(id, args)
        case 'rd_station_organizacao_excluir': return c.delete_organization(args['id'])
        # Pipelines, Stages, etc
        case 'rd_station_pipelines_listar': return c.list_pipelines()
        case 'rd_station_stages_listar': return c.list_stages(pipeline_id=args.get('pipeline_id'))
        case 'rd_station_atividades_listar':
            return c.list_activities(deal_id=args.get('deal_id'), limit=args.get('limit', 50), page=args.get('page', 1))
        case 'rd_station_atividade_criar': return c.create_activity(args)
        case 'rd_station_campos_custom_listar': return c.list_custom_fields()
        case 'rd_station_usuarios_listar': return c.list_users()
        case 'rd_station_produtos_listar': return c.list_products(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'rd_station_origens_listar': return c.list_sources()
        case 'rd_station_empresa': return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
