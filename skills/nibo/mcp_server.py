#!/usr/bin/env python3
"""
MCP server para Nibo — 8 tools.
Endpoints cobertos: saldo, contas a pagar, contas a receber, baixa, criacao, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from nibo_client import NiboClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('nibo')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = NiboClient()
    return _client


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name='nibo_saldo',
            description='Saldo financeiro atual da empresa no Nibo',
            inputSchema={'type': 'object', 'properties': {}, 'required': []}
        ),
        types.Tool(
            name='nibo_titulos_pagar',
            description='Lista contas a pagar do Nibo (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'from_date': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'},
                    'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
                    'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
                    'page': {'type': 'integer', 'description': 'Pagina (default 1)', 'default': 1},
                },
                'required': []
            }
        ),
        types.Tool(
            name='nibo_titulos_receber',
            description='Lista contas a receber do Nibo (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'from_date': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'},
                    'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
                    'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
                    'page': {'type': 'integer', 'description': 'Pagina (default 1)', 'default': 1},
                },
                'required': []
            }
        ),
        types.Tool(
            name='nibo_pagar_titulo',
            description='Marca titulo a pagar como pago no Nibo',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do titulo a pagar'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='nibo_receber_titulo',
            description='Marca titulo a receber como recebido no Nibo',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do titulo a receber'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='nibo_criar_pagar',
            description='Cria novo titulo a pagar no Nibo',
            inputSchema={
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'description': 'Valor em BRL'},
                    'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                    'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                    'category': {'type': 'string', 'description': 'Categoria'},
                    'description': {'type': 'string', 'description': 'Descricao'},
                },
                'required': ['amount', 'due_date', 'supplier']
            }
        ),
        types.Tool(
            name='nibo_criar_receber',
            description='Cria novo titulo a receber no Nibo',
            inputSchema={
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'description': 'Valor em BRL'},
                    'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                    'customer': {'type': 'string', 'description': 'Nome do cliente'},
                    'category': {'type': 'string', 'description': 'Categoria'},
                    'description': {'type': 'string', 'description': 'Descricao'},
                },
                'required': ['amount', 'due_date', 'customer']
            }
        ),
        types.Tool(
            name='nibo_empresa',
            description='Informacoes da empresa conectada ao Nibo',
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
        case 'nibo_saldo':
            return c.get_balance()
        case 'nibo_titulos_pagar':
            return c.list_payables(
                from_date=args.get('from_date'),
                to_date=args.get('to_date'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'nibo_titulos_receber':
            return c.list_receivables(
                from_date=args.get('from_date'),
                to_date=args.get('to_date'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'nibo_pagar_titulo':
            return c.pay_payable(args['id'])
        case 'nibo_receber_titulo':
            return c.mark_received(args['id'])
        case 'nibo_criar_pagar':
            return c.create_payable(
                amount=args['amount'],
                due_date=args['due_date'],
                supplier=args['supplier'],
                category=args.get('category', ''),
                description=args.get('description', ''),
            )
        case 'nibo_criar_receber':
            return c.create_receivable(
                amount=args['amount'],
                due_date=args['due_date'],
                customer=args['customer'],
                category=args.get('category', ''),
                description=args.get('description', ''),
            )
        case 'nibo_empresa':
            return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
