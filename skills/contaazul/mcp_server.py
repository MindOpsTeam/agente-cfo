#!/usr/bin/env python3
"""
MCP server para Conta Azul — 32 tools.
Endpoints cobertos: saldo, contas a pagar/receber, clientes, produtos, pedidos de venda,
NF-e, contas bancárias, categorias, serviços, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from contaazul_client import ContaAzulClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('contaazul')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = ContaAzulClient()
    return _client

_PAGINATION = {
    'limit': {'type': 'integer', 'description': 'Limite por página (default 50)', 'default': 50},
    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
}
_SEARCH_PAGINATION = {
    **_PAGINATION,
    'search': {'type': 'string', 'description': 'Busca por nome/texto'},
}
_DATE_RANGE = {
    'from_date': {'type': 'string', 'description': 'Data início (YYYY-MM-DD)'},
    'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
}
_ID_REQUIRED = {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'ID do registro'}}, 'required': ['id']}
_EMPTY = {'type': 'object', 'properties': {}, 'required': []}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Financeiro base ──────────────────────────────────────────────
        types.Tool(name='contaazul_saldo', description='Saldo financeiro atual da empresa no Conta Azul', inputSchema=_EMPTY),
        types.Tool(name='contaazul_titulos_pagar', description='Lista contas a pagar do Conta Azul (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, **_PAGINATION}, 'required': []}),
        types.Tool(name='contaazul_titulos_receber', description='Lista contas a receber do Conta Azul (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, **_PAGINATION}, 'required': []}),
        types.Tool(name='contaazul_pagar_titulo', description='Marca titulo a pagar como pago no Conta Azul', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_receber_titulo', description='Marca titulo a receber como recebido no Conta Azul', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_criar_pagar', description='Cria novo titulo a pagar no Conta Azul',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'supplier']}),
        types.Tool(name='contaazul_criar_receber', description='Cria novo titulo a receber no Conta Azul',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'customer': {'type': 'string', 'description': 'Nome do cliente'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'customer']}),
        types.Tool(name='contaazul_cancelar_pagar', description='Cancela/exclui titulo a pagar no Conta Azul', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_empresa', description='Informações da empresa conectada ao Conta Azul', inputSchema=_EMPTY),

        # ── Contas a pagar/receber — get e delete individuais ────────────
        types.Tool(name='contaazul_get_pagar', description='Detalhes de uma conta a pagar pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_delete_pagar', description='Exclui conta a pagar pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_get_receber', description='Detalhes de uma conta a receber pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_delete_receber', description='Exclui conta a receber pelo ID', inputSchema=_ID_REQUIRED),

        # ── Clientes ─────────────────────────────────────────────────────
        types.Tool(name='contaazul_listar_clientes', description='Lista clientes do Conta Azul (paginado, com busca)',
                   inputSchema={'type': 'object', 'properties': _SEARCH_PAGINATION, 'required': []}),
        types.Tool(name='contaazul_get_cliente', description='Detalhes de um cliente pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_criar_cliente', description='Cria novo cliente no Conta Azul',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do cliente'},
                       'email': {'type': 'string', 'description': 'Email'},
                       'document': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'phone': {'type': 'string', 'description': 'Telefone'},
                       'company_name': {'type': 'string', 'description': 'Razão social'},
                       'notes': {'type': 'string', 'description': 'Observações'},
                   }, 'required': ['name']}),
        types.Tool(name='contaazul_atualizar_cliente', description='Atualiza dados de um cliente existente',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do cliente'},
                       'name': {'type': 'string', 'description': 'Nome do cliente'},
                       'email': {'type': 'string', 'description': 'Email'},
                       'document': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'phone': {'type': 'string', 'description': 'Telefone'},
                       'company_name': {'type': 'string', 'description': 'Razão social'},
                       'notes': {'type': 'string', 'description': 'Observações'},
                   }, 'required': ['id']}),
        types.Tool(name='contaazul_deletar_cliente', description='Exclui cliente pelo ID', inputSchema=_ID_REQUIRED),

        # ── Produtos ─────────────────────────────────────────────────────
        types.Tool(name='contaazul_listar_produtos', description='Lista produtos do Conta Azul (paginado, com busca)',
                   inputSchema={'type': 'object', 'properties': _SEARCH_PAGINATION, 'required': []}),
        types.Tool(name='contaazul_get_produto', description='Detalhes de um produto pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_criar_produto', description='Cria novo produto no Conta Azul',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do produto'},
                       'value': {'type': 'number', 'description': 'Valor de venda (BRL)'},
                       'cost': {'type': 'number', 'description': 'Custo do produto (BRL)'},
                       'code': {'type': 'string', 'description': 'Código interno'},
                       'barcode': {'type': 'string', 'description': 'Código de barras'},
                   }, 'required': ['name', 'value']}),
        types.Tool(name='contaazul_atualizar_produto', description='Atualiza dados de um produto existente',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do produto'},
                       'name': {'type': 'string', 'description': 'Nome do produto'},
                       'value': {'type': 'number', 'description': 'Valor de venda (BRL)'},
                       'cost': {'type': 'number', 'description': 'Custo do produto (BRL)'},
                       'code': {'type': 'string', 'description': 'Código interno'},
                   }, 'required': ['id']}),

        # ── Pedidos de venda ─────────────────────────────────────────────
        types.Tool(name='contaazul_listar_vendas', description='Lista pedidos de venda do Conta Azul (paginado)',
                   inputSchema={'type': 'object', 'properties': _PAGINATION, 'required': []}),
        types.Tool(name='contaazul_get_venda', description='Detalhes de um pedido de venda pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_criar_venda', description='Cria novo pedido de venda no Conta Azul',
                   inputSchema={'type': 'object', 'properties': {
                       'customer_id': {'type': 'string', 'description': 'ID do cliente'},
                       'products': {'type': 'array', 'description': 'Lista de produtos [{product_id, quantity, value}]',
                                    'items': {'type': 'object'}},
                       'emission': {'type': 'string', 'description': 'Data de emissão (YYYY-MM-DD)'},
                       'discount': {'type': 'number', 'description': 'Desconto total (BRL)'},
                       'notes': {'type': 'string', 'description': 'Observações'},
                   }, 'required': ['customer_id', 'products']}),

        # ── NF-e ─────────────────────────────────────────────────────────
        types.Tool(name='contaazul_listar_nfes', description='Lista notas fiscais eletrônicas (NF-e) do Conta Azul',
                   inputSchema={'type': 'object', 'properties': _PAGINATION, 'required': []}),
        types.Tool(name='contaazul_get_nfe', description='Detalhes de uma NF-e pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='contaazul_criar_nfe', description='Cria/emite NF-e a partir de um pedido de venda',
                   inputSchema={'type': 'object', 'properties': {
                       'sale_id': {'type': 'string', 'description': 'ID do pedido de venda'},
                       'nature_of_operation': {'type': 'string', 'description': 'Natureza da operação'},
                       'notes': {'type': 'string', 'description': 'Observações'},
                   }, 'required': ['sale_id']}),

        # ── Contas bancárias ─────────────────────────────────────────────
        types.Tool(name='contaazul_listar_contas_bancarias', description='Lista contas bancárias cadastradas no Conta Azul', inputSchema=_EMPTY),

        # ── Categorias ───────────────────────────────────────────────────
        types.Tool(name='contaazul_listar_categorias', description='Lista categorias financeiras do Conta Azul', inputSchema=_EMPTY),

        # ── Serviços ─────────────────────────────────────────────────────
        types.Tool(name='contaazul_listar_servicos', description='Lista serviços cadastrados no Conta Azul (paginado, com busca)',
                   inputSchema={'type': 'object', 'properties': _SEARCH_PAGINATION, 'required': []}),
        types.Tool(name='contaazul_get_servico', description='Detalhes de um serviço pelo ID', inputSchema=_ID_REQUIRED),
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
        # ── Financeiro base ──────────────────────────────────────────────
        case 'contaazul_saldo':
            return c.get_balance()
        case 'contaazul_titulos_pagar':
            return c.list_payables(
                from_date=args.get('from_date'), to_date=args.get('to_date'),
                limit=args.get('limit', 50), page=args.get('page', 1))
        case 'contaazul_titulos_receber':
            return c.list_receivables(
                from_date=args.get('from_date'), to_date=args.get('to_date'),
                limit=args.get('limit', 50), page=args.get('page', 1))
        case 'contaazul_pagar_titulo':
            return c.pay_payable(args['id'])
        case 'contaazul_receber_titulo':
            return c.mark_received(args['id'])
        case 'contaazul_criar_pagar':
            return c.create_payable(
                amount=args['amount'], due_date=args['due_date'], supplier=args['supplier'],
                category=args.get('category', ''), description=args.get('description', ''))
        case 'contaazul_criar_receber':
            return c.create_receivable(
                amount=args['amount'], due_date=args['due_date'], customer=args['customer'],
                category=args.get('category', ''), description=args.get('description', ''))
        case 'contaazul_cancelar_pagar':
            return c.cancel_payable(args['id'])
        case 'contaazul_empresa':
            return c.company_info()

        # ── Contas a pagar/receber — get e delete ────────────────────────
        case 'contaazul_get_pagar':
            return c.get_payable(args['id'])
        case 'contaazul_delete_pagar':
            return c.delete_payable(args['id'])
        case 'contaazul_get_receber':
            return c.get_receivable(args['id'])
        case 'contaazul_delete_receber':
            return c.delete_receivable(args['id'])

        # ── Clientes ─────────────────────────────────────────────────────
        case 'contaazul_listar_clientes':
            return c.list_customers(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search', ''))
        case 'contaazul_get_cliente':
            return c.get_customer(args['id'])
        case 'contaazul_criar_cliente':
            return c.create_customer(name=args['name'], email=args.get('email'), document=args.get('document'),
                                     phone=args.get('phone'), company_name=args.get('company_name'), notes=args.get('notes'))
        case 'contaazul_atualizar_cliente':
            kw = {k: args[k] for k in ('name', 'email', 'document', 'phone', 'company_name', 'notes') if k in args}
            return c.update_customer(args['id'], **kw)
        case 'contaazul_deletar_cliente':
            return c.delete_customer(args['id'])

        # ── Produtos ─────────────────────────────────────────────────────
        case 'contaazul_listar_produtos':
            return c.list_products(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search', ''))
        case 'contaazul_get_produto':
            return c.get_product(args['id'])
        case 'contaazul_criar_produto':
            return c.create_product(name=args['name'], value=args['value'],
                                    cost=args.get('cost'), code=args.get('code'), barcode=args.get('barcode'))
        case 'contaazul_atualizar_produto':
            kw = {k: args[k] for k in ('name', 'value', 'cost', 'code') if k in args}
            return c.update_product(args['id'], **kw)

        # ── Pedidos de venda ─────────────────────────────────────────────
        case 'contaazul_listar_vendas':
            return c.list_sales(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'contaazul_get_venda':
            return c.get_sale(args['id'])
        case 'contaazul_criar_venda':
            return c.create_sale(customer_id=args['customer_id'], products=args['products'],
                                 emission=args.get('emission'), discount=args.get('discount'), notes=args.get('notes'))

        # ── NF-e ─────────────────────────────────────────────────────────
        case 'contaazul_listar_nfes':
            return c.list_nfes(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'contaazul_get_nfe':
            return c.get_nfe(args['id'])
        case 'contaazul_criar_nfe':
            return c.create_nfe(sale_id=args['sale_id'], nature_of_operation=args.get('nature_of_operation'),
                                notes=args.get('notes'))

        # ── Contas bancárias ─────────────────────────────────────────────
        case 'contaazul_listar_contas_bancarias':
            return c.list_bank_accounts()

        # ── Categorias ───────────────────────────────────────────────────
        case 'contaazul_listar_categorias':
            return c.list_categories()

        # ── Serviços ─────────────────────────────────────────────────────
        case 'contaazul_listar_servicos':
            return c.list_services(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search', ''))
        case 'contaazul_get_servico':
            return c.get_service(args['id'])

        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
