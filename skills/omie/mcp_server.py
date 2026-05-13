#!/usr/bin/env python3
"""
MCP server para Omie ERP — 25 tools.
Endpoints cobertos: clientes, produtos, pedidos, financeiro (pagar/receber),
NF-e, estoque, empresa, saldo, vencidos.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
from omie_client import (
    clientes_listar, clientes_buscar, clientes_detalhar,
    produtos_listar, produtos_detalhar,
    pedidos_listar, pedidos_detalhar, pedidos_status,
    contas_receber, contas_pagar, resumo_financeiro,
    nfe_listar, nfe_detalhar,
    estoque_posicao, estoque_produto,
    unified_get_balance, unified_list_payables, unified_list_receivables,
    unified_list_overdue, unified_company_info,
    unified_pay_payable, unified_mark_received,
    unified_create_payable, unified_create_receivable, unified_cancel_payable,
)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('omie')


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Clientes ──
        types.Tool(
            name='omie_clientes_listar',
            description='Lista clientes cadastrados no Omie (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'pagina': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                    'por_pagina': {'type': 'integer', 'description': 'Registros por página (default 20)', 'default': 20},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_clientes_buscar',
            description='Busca clientes por CNPJ/CPF, código ou nome fantasia',
            inputSchema={
                'type': 'object',
                'properties': {
                    'cnpj_cpf': {'type': 'string', 'description': 'CNPJ ou CPF do cliente'},
                    'codigo': {'type': 'string', 'description': 'Código do cliente no Omie'},
                    'nome': {'type': 'string', 'description': 'Nome fantasia (busca parcial)'},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_clientes_detalhar',
            description='Retorna dados completos de um cliente pelo código Omie',
            inputSchema={
                'type': 'object',
                'properties': {
                    'codigo': {'type': 'integer', 'description': 'Código do cliente no Omie'},
                },
                'required': ['codigo']
            }
        ),
        # ── Produtos ──
        types.Tool(
            name='omie_produtos_listar',
            description='Lista produtos cadastrados no Omie (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'pagina': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                    'por_pagina': {'type': 'integer', 'description': 'Registros por página (default 20)', 'default': 20},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_produtos_detalhar',
            description='Retorna dados completos de um produto pelo código',
            inputSchema={
                'type': 'object',
                'properties': {
                    'codigo': {'type': 'integer', 'description': 'Código do produto no Omie'},
                },
                'required': ['codigo']
            }
        ),
        # ── Pedidos ──
        types.Tool(
            name='omie_pedidos_listar',
            description='Lista pedidos de venda do Omie (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'pagina': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                    'por_pagina': {'type': 'integer', 'description': 'Registros por página (default 20)', 'default': 20},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_pedidos_detalhar',
            description='Retorna dados completos de um pedido de venda',
            inputSchema={
                'type': 'object',
                'properties': {
                    'numero': {'type': 'integer', 'description': 'Número do pedido'},
                },
                'required': ['numero']
            }
        ),
        types.Tool(
            name='omie_pedidos_status',
            description='Consulta status de um pedido de venda',
            inputSchema={
                'type': 'object',
                'properties': {
                    'numero': {'type': 'integer', 'description': 'Número do pedido'},
                },
                'required': ['numero']
            }
        ),
        # ── Financeiro nativo ──
        types.Tool(
            name='omie_contas_receber',
            description='Lista contas a receber do Omie (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'pagina': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                    'por_pagina': {'type': 'integer', 'description': 'Registros por página (default 20)', 'default': 20},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_contas_pagar',
            description='Lista contas a pagar do Omie (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'pagina': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                    'por_pagina': {'type': 'integer', 'description': 'Registros por página (default 20)', 'default': 20},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_resumo_financeiro',
            description='Resumo financeiro do dia (saldo caixa)',
            inputSchema={'type': 'object', 'properties': {}, 'required': []}
        ),
        # ── NF-e ──
        types.Tool(
            name='omie_nfe_listar',
            description='Lista notas fiscais eletrônicas (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'pagina': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                    'por_pagina': {'type': 'integer', 'description': 'Registros por página (default 20)', 'default': 20},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_nfe_detalhar',
            description='Retorna dados completos de uma NF-e pelo número',
            inputSchema={
                'type': 'object',
                'properties': {
                    'numero': {'type': 'integer', 'description': 'Número da NF-e'},
                },
                'required': ['numero']
            }
        ),
        # ── Estoque ──
        types.Tool(
            name='omie_estoque_posicao',
            description='Consulta posição de estoque geral (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'pagina': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                    'por_pagina': {'type': 'integer', 'description': 'Registros por página (default 20)', 'default': 20},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_estoque_produto',
            description='Consulta estoque de um produto específico',
            inputSchema={
                'type': 'object',
                'properties': {
                    'codigo': {'type': 'integer', 'description': 'Código do produto'},
                },
                'required': ['codigo']
            }
        ),
        # ── Unified CFO ──
        types.Tool(
            name='omie_saldo',
            description='Saldo financeiro atual da empresa (interface unificada CFO)',
            inputSchema={'type': 'object', 'properties': {}, 'required': []}
        ),
        types.Tool(
            name='omie_titulos_pagar',
            description='Lista títulos a pagar (interface unificada CFO, paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'from_date': {'type': 'string', 'description': 'Data início (YYYY-MM-DD)'},
                    'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
                    'limit': {'type': 'integer', 'description': 'Limite por página (default 50)', 'default': 50},
                    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_titulos_receber',
            description='Lista títulos a receber (interface unificada CFO, paginado)',
            inputSchema={
                'type': 'object',
                'properties': {
                    'from_date': {'type': 'string', 'description': 'Data início (YYYY-MM-DD)'},
                    'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
                    'limit': {'type': 'integer', 'description': 'Limite por página (default 50)', 'default': 50},
                    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
                },
                'required': []
            }
        ),
        types.Tool(
            name='omie_vencidos',
            description='Lista todos os títulos vencidos (a pagar e a receber)',
            inputSchema={'type': 'object', 'properties': {}, 'required': []}
        ),
        types.Tool(
            name='omie_pagar_titulo',
            description='Marca um título a pagar como pago',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID (nCodTitulo) do título a pagar'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='omie_receber_titulo',
            description='Marca um título a receber como recebido',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID (nCodTitulo) do título a receber'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='omie_criar_pagar',
            description='Cria um novo título a pagar',
            inputSchema={
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'description': 'Valor em BRL'},
                    'due_date': {'type': 'string', 'description': 'Data de vencimento (DD/MM/YYYY)'},
                    'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                    'category': {'type': 'string', 'description': 'Categoria'},
                    'description': {'type': 'string', 'description': 'Observação'},
                },
                'required': ['amount', 'due_date', 'supplier']
            }
        ),
        types.Tool(
            name='omie_criar_receber',
            description='Cria um novo título a receber',
            inputSchema={
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'description': 'Valor em BRL'},
                    'due_date': {'type': 'string', 'description': 'Data de vencimento (DD/MM/YYYY)'},
                    'customer': {'type': 'string', 'description': 'Nome do cliente'},
                    'category': {'type': 'string', 'description': 'Categoria'},
                    'description': {'type': 'string', 'description': 'Observação'},
                },
                'required': ['amount', 'due_date', 'customer']
            }
        ),
        types.Tool(
            name='omie_cancelar_pagar',
            description='Cancela/exclui um título a pagar',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID (nCodTitulo) do título'},
                },
                'required': ['id']
            }
        ),
        types.Tool(
            name='omie_empresa',
            description='Informações da empresa conectada ao Omie',
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
    match name:
        # Clientes
        case 'omie_clientes_listar':
            return clientes_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_clientes_buscar':
            filtro = {k: v for k, v in args.items() if v}
            return clientes_buscar(filtro)
        case 'omie_clientes_detalhar':
            return clientes_detalhar(args['codigo'])
        # Produtos
        case 'omie_produtos_listar':
            return produtos_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_produtos_detalhar':
            return produtos_detalhar(args['codigo'])
        # Pedidos
        case 'omie_pedidos_listar':
            return pedidos_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_pedidos_detalhar':
            return pedidos_detalhar(args['numero'])
        case 'omie_pedidos_status':
            return pedidos_status(args['numero'])
        # Financeiro nativo
        case 'omie_contas_receber':
            return contas_receber(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_contas_pagar':
            return contas_pagar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_resumo_financeiro':
            return resumo_financeiro()
        # NF-e
        case 'omie_nfe_listar':
            return nfe_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_nfe_detalhar':
            return nfe_detalhar(args['numero'])
        # Estoque
        case 'omie_estoque_posicao':
            return estoque_posicao(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_estoque_produto':
            return estoque_produto(args['codigo'])
        # Unified CFO
        case 'omie_saldo':
            return unified_get_balance()
        case 'omie_titulos_pagar':
            return unified_list_payables(
                from_date=args.get('from_date'),
                to_date=args.get('to_date'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'omie_titulos_receber':
            return unified_list_receivables(
                from_date=args.get('from_date'),
                to_date=args.get('to_date'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'omie_vencidos':
            return unified_list_overdue()
        case 'omie_pagar_titulo':
            return unified_pay_payable(args['id'])
        case 'omie_receber_titulo':
            return unified_mark_received(args['id'])
        case 'omie_criar_pagar':
            return unified_create_payable(
                amount=args['amount'],
                due_date=args['due_date'],
                supplier=args['supplier'],
                category=args.get('category', ''),
                description=args.get('description', ''),
            )
        case 'omie_criar_receber':
            return unified_create_receivable(
                amount=args['amount'],
                due_date=args['due_date'],
                customer=args['customer'],
                category=args.get('category', ''),
                description=args.get('description', ''),
            )
        case 'omie_cancelar_pagar':
            return unified_cancel_payable(args['id'])
        case 'omie_empresa':
            return unified_company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
