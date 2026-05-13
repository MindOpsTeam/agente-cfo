#!/usr/bin/env python3
"""
MCP server para Mercado Livre — 9 tools.
Endpoints cobertos: pedidos, detalhe, produtos, estoque, preco, enviar, cancelar, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from mercado_livre_client import MercadoLivreClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('mercado_livre')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = MercadoLivreClient()
    return _client


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name='mercado_livre_pedidos_listar',
            description='Lista pedidos/orders do Mercado Livre (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'description': 'Filtro de status (paid, shipped, etc)', 'default': 'paid'},
                    'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
                    'since': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'},
                },
                'required': []
            }
        ),
        types.Tool(
            name='mercado_livre_pedido_detalhar',
            description='Retorna detalhes de um pedido do Mercado Livre',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do pedido'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='mercado_livre_produtos_listar',
            description='Lista produtos do Mercado Livre (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
                    'in_stock_only': {'type': 'boolean', 'description': 'Apenas com estoque', 'default': False},
                },
                'required': []
            }
        ),
        types.Tool(
            name='mercado_livre_produto_detalhar',
            description='Retorna detalhes de um produto do Mercado Livre',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do produto'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='mercado_livre_estoque_atualizar',
            description='Atualiza quantidade em estoque de um produto no Mercado Livre',
            inputSchema={
                'type': 'object',
                'properties': {
                    'product_id': {'type': 'string', 'description': 'ID do produto'},
                    'new_qty': {'type': 'integer', 'description': 'Nova quantidade em estoque'},
                },
                'required': ['product_id', 'new_qty']
            }
        ),
        types.Tool(
            name='mercado_livre_preco_atualizar',
            description='Atualiza preco de um produto no Mercado Livre',
            inputSchema={
                'type': 'object',
                'properties': {
                    'product_id': {'type': 'string', 'description': 'ID do produto'},
                    'new_price': {'type': 'number', 'description': 'Novo preco'},
                },
                'required': ['product_id', 'new_price']
            }
        ),
        types.Tool(
            name='mercado_livre_pedido_enviar',
            description='Marca pedido como enviado/shipped no Mercado Livre',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do pedido'},
                    'tracking_code': {'type': 'string', 'description': 'Codigo de rastreio'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='mercado_livre_pedido_cancelar',
            description='Cancela um pedido no Mercado Livre',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do pedido'},
                    'reason': {'type': 'string', 'description': 'Motivo do cancelamento'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='mercado_livre_empresa',
            description='Informacoes da loja conectada ao Mercado Livre',
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
        case 'mercado_livre_pedidos_listar':
            return c.list_orders(
                status=args.get('status', 'paid'),
                limit=args.get('limit', 50),
                since=args.get('since'),
            )
        case 'mercado_livre_pedido_detalhar':
            return c.get_order(args['id'])
        case 'mercado_livre_produtos_listar':
            return c.list_products(
                limit=args.get('limit', 50),
                in_stock_only=args.get('in_stock_only', False),
            )
        case 'mercado_livre_produto_detalhar':
            return c.get_product(args['id'])
        case 'mercado_livre_estoque_atualizar':
            return c.update_stock(args['product_id'], args['new_qty'])
        case 'mercado_livre_preco_atualizar':
            return c.update_price(args['product_id'], args['new_price'])
        case 'mercado_livre_pedido_enviar':
            return c.mark_order_shipped(args['id'], tracking_code=args.get('tracking_code', ''))
        case 'mercado_livre_pedido_cancelar':
            return c.cancel_order(args['id'], reason=args.get('reason', ''))
        case 'mercado_livre_empresa':
            return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
