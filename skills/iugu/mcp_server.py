#!/usr/bin/env python3
"""
MCP server para Iugu — 9 tools.
Endpoints cobertos: cobrancas, detalhe, cliente, criar, cancelar, baixa manual, link pagamento, meios, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from iugu_client import IuguClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('iugu')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = IuguClient()
    return _client


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name='iugu_cobrancas_listar',
            description='Lista cobrancas/faturas do Iugu (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'status': {'type': 'string', 'description': 'Filtro de status (open, paid, overdue)', 'default': 'open'},
                    'customer_id': {'type': 'string', 'description': 'ID do cliente para filtrar'},
                    'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
                    'page': {'type': 'integer', 'description': 'Pagina (default 1)', 'default': 1},
                },
                'required': []
            }
        ),
        types.Tool(
            name='iugu_cobranca_detalhar',
            description='Retorna detalhes de uma cobranca/fatura do Iugu',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID da cobranca/fatura'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='iugu_cliente_detalhar',
            description='Retorna dados de um cliente do Iugu',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do cliente'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='iugu_cobranca_criar',
            description='Cria nova cobranca/fatura no Iugu',
            inputSchema={
                'type': 'object',
                'properties': {
                    'customer_id': {'type': 'string', 'description': 'ID do cliente'},
                    'amount': {'type': 'number', 'description': 'Valor em BRL'},
                    'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                    'description': {'type': 'string', 'description': 'Descricao da cobranca'},
                },
                'required': ['customer_id', 'amount', 'due_date']
            }
        ),
        types.Tool(
            name='iugu_cobranca_cancelar',
            description='Cancela uma cobranca/fatura no Iugu',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID da cobranca/fatura'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='iugu_cobranca_baixa_manual',
            description='Marca cobranca como paga manualmente no Iugu',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID da cobranca/fatura'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='iugu_enviar_link',
            description='Envia link de pagamento da cobranca via WhatsApp/email no Iugu',
            inputSchema={
                'type': 'object',
                'properties': {
                    'invoice_id': {'type': 'string', 'description': 'ID da cobranca/fatura'},
                    'channel': {'type': 'string', 'description': 'Canal de envio (whatsapp, email)', 'default': 'whatsapp'},
                    'custom_message': {'type': 'string', 'description': 'Mensagem personalizada'},
                },
                'required': ['invoice_id']
            }
        ),
        types.Tool(
            name='iugu_meios_pagamento',
            description='Lista meios de pagamento disponiveis no Iugu',
            inputSchema={'type': 'object', 'properties': {}, 'required': []}
        ),
        types.Tool(
            name='iugu_empresa',
            description='Informacoes da empresa conectada ao Iugu',
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
        case 'iugu_cobrancas_listar':
            return c.list_invoices(
                status=args.get('status', 'open'),
                customer_id=args.get('customer_id'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'iugu_cobranca_detalhar':
            return c.get_invoice(args['id'])
        case 'iugu_cliente_detalhar':
            return c.get_customer(args['id'])
        case 'iugu_cobranca_criar':
            return c.create_invoice(
                customer_id=args['customer_id'],
                amount=args['amount'],
                due_date=args['due_date'],
                description=args.get('description', ''),
            )
        case 'iugu_cobranca_cancelar':
            return c.cancel_invoice(args['id'])
        case 'iugu_cobranca_baixa_manual':
            return c.mark_invoice_paid_manually(args['id'])
        case 'iugu_enviar_link':
            return c.send_payment_link(
                invoice_id=args['invoice_id'],
                channel=args.get('channel', 'whatsapp'),
                custom_message=args.get('custom_message'),
            )
        case 'iugu_meios_pagamento':
            return c.get_payment_methods()
        case 'iugu_empresa':
            return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
