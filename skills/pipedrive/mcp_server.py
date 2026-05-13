#!/usr/bin/env python3
"""
MCP server para Pipedrive — 8 tools.
Endpoints cobertos: deals, mover, atualizar, criar, nota, ganho, perdido, empresa.
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


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name='pipedrive_deals_listar',
            description='Lista deals/oportunidades do Pipedrive (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'description': 'Filtro de status (open, won, lost)', 'default': 'open'},
                    'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
                    'page': {'type': 'integer', 'description': 'Pagina (default 1)', 'default': 1},
                },
                'required': []
            }
        ),
        types.Tool(
            name='pipedrive_deal_mover',
            description='Move deal para outra etapa/stage no Pipedrive',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do deal'},
                    'to_stage': {'type': 'string', 'description': 'Nome ou ID da etapa destino'},
                },
                'required': ['id', 'to_stage']
            }
        ),
        types.Tool(
            name='pipedrive_deal_atualizar',
            description='Atualiza valor e/ou data de fechamento do deal no Pipedrive',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do deal'},
                    'amount': {'type': 'number', 'description': 'Novo valor do deal'},
                    'close_date': {'type': 'string', 'description': 'Nova data de fechamento (YYYY-MM-DD)'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='pipedrive_deal_criar',
            description='Cria novo deal/oportunidade no Pipedrive',
            inputSchema={
                'type': 'object',
                'properties': {
                    'title': {'type': 'string', 'description': 'Titulo do deal'},
                    'amount': {'type': 'number', 'description': 'Valor do deal'},
                    'pipeline': {'type': 'string', 'description': 'Pipeline/funil'},
                },
                'required': ['title']
            }
        ),
        types.Tool(
            name='pipedrive_deal_nota',
            description='Adiciona nota/comentario a um deal no Pipedrive',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do deal'},
                    'note': {'type': 'string', 'description': 'Texto da nota'},
                },
                'required': ['id', 'note']
            }
        ),
        types.Tool(
            name='pipedrive_deal_ganho',
            description='Marca deal como ganho/won no Pipedrive',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do deal'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='pipedrive_deal_perdido',
            description='Marca deal como perdido/lost no Pipedrive',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do deal'},
                    'reason': {'type': 'string', 'description': 'Motivo da perda'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='pipedrive_empresa',
            description='Informacoes da empresa conectada ao Pipedrive',
            inputSchema={'type': 'object', 'properties': {}, 'required': []}
        ),
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
        case 'pipedrive_deals_listar':
            return c.list_deals(
                status=args.get('status', 'open'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'pipedrive_deal_mover':
            return c.move_deal(args['id'], args['to_stage'])
        case 'pipedrive_deal_atualizar':
            return c.update_deal(
                args['id'],
                amount=args.get('amount'),
                close_date=args.get('close_date'),
            )
        case 'pipedrive_deal_criar':
            return c.create_deal(
                title=args['title'],
                amount=args.get('amount'),
                pipeline=args.get('pipeline'),
            )
        case 'pipedrive_deal_nota':
            return c.add_deal_note(args['id'], args['note'])
        case 'pipedrive_deal_ganho':
            return c.mark_deal_won(args['id'])
        case 'pipedrive_deal_perdido':
            return c.mark_deal_lost(args['id'], reason=args.get('reason', ''))
        case 'pipedrive_empresa':
            return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
