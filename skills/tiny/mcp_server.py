#!/usr/bin/env python3
"""
MCP server para Tiny ERP — 34 tools.
Endpoints cobertos: saldo, contas a pagar/receber, contatos, produtos, pedidos,
notas fiscais, estoque, formas de pagamento, listas de preço, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from tiny_client import TinyClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('tiny')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = TinyClient()
    return _client

_PAGINATION = {'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1}}
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
        types.Tool(name='tiny_saldo', description='Saldo financeiro atual da empresa no Tiny ERP', inputSchema=_EMPTY),
        types.Tool(name='tiny_titulos_pagar', description='Lista contas a pagar do Tiny ERP (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, 'limit': {'type': 'integer', 'default': 50}, **_PAGINATION}, 'required': []}),
        types.Tool(name='tiny_titulos_receber', description='Lista contas a receber do Tiny ERP (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, 'limit': {'type': 'integer', 'default': 50}, **_PAGINATION}, 'required': []}),
        types.Tool(name='tiny_pagar_titulo', description='Marca título a pagar como pago no Tiny ERP', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_receber_titulo', description='Marca título a receber como recebido no Tiny ERP', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_criar_pagar', description='Cria novo título a pagar no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'supplier']}),
        types.Tool(name='tiny_criar_receber', description='Cria novo título a receber no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'customer': {'type': 'string', 'description': 'Nome do cliente'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'customer']}),
        types.Tool(name='tiny_cancelar_pagar', description='Cancela/exclui título a pagar no Tiny ERP', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_empresa', description='Informações da empresa conectada ao Tiny ERP', inputSchema=_EMPTY),

        # ── Contatos (Clientes/Fornecedores) ─────────────────────────────
        types.Tool(name='tiny_contatos_listar', description='Lista contatos (clientes/fornecedores) do Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por nome/razão social'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='tiny_contatos_obter', description='Obtém detalhes de um contato pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_contatos_criar', description='Cria novo contato no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'nome': {'type': 'string', 'description': 'Nome/Razão social'},
                       'tipo_pessoa': {'type': 'string', 'description': 'F (física) ou J (jurídica)'},
                       'cpf_cnpj': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'fone': {'type': 'string', 'description': 'Telefone'},
                       'endereco': {'type': 'string', 'description': 'Endereço'},
                       'cidade': {'type': 'string', 'description': 'Cidade'},
                       'uf': {'type': 'string', 'description': 'UF'},
                       'cep': {'type': 'string', 'description': 'CEP'},
                   }, 'required': ['nome']}),
        types.Tool(name='tiny_contatos_atualizar', description='Atualiza contato no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do contato'},
                       'nome': {'type': 'string', 'description': 'Nome/Razão social'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'fone': {'type': 'string', 'description': 'Telefone'},
                   }, 'required': ['id']}),

        # ── Produtos ─────────────────────────────────────────────────────
        types.Tool(name='tiny_produtos_listar', description='Lista produtos cadastrados no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por descrição/nome'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='tiny_produtos_obter', description='Obtém detalhes de um produto pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_produtos_criar', description='Cria novo produto no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'nome': {'type': 'string', 'description': 'Nome do produto'},
                       'preco': {'type': 'number', 'description': 'Preço de venda'},
                       'preco_custo': {'type': 'number', 'description': 'Preço de custo'},
                       'unidade': {'type': 'string', 'description': 'Unidade (UN, KG, etc)'},
                       'ncm': {'type': 'string', 'description': 'Código NCM'},
                       'codigo': {'type': 'string', 'description': 'Código/SKU'},
                   }, 'required': ['nome']}),
        types.Tool(name='tiny_produtos_atualizar', description='Atualiza produto no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do produto'},
                       'nome': {'type': 'string', 'description': 'Nome'},
                       'preco': {'type': 'number', 'description': 'Preço de venda'},
                       'preco_custo': {'type': 'number', 'description': 'Preço de custo'},
                   }, 'required': ['id']}),

        # ── Estoque ──────────────────────────────────────────────────────
        types.Tool(name='tiny_estoque_obter', description='Obtém saldo de estoque de um produto pelo ID', inputSchema=_ID_REQUIRED),

        # ── Pedidos ──────────────────────────────────────────────────────
        types.Tool(name='tiny_pedidos_listar', description='Lista pedidos do Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por número/cliente'},
                       'situacao': {'type': 'string', 'description': 'Filtrar por situação (aberto, faturado, etc)'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='tiny_pedidos_obter', description='Obtém detalhes de um pedido pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_pedidos_criar', description='Cria novo pedido no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'cliente': {'type': 'object', 'description': 'Dados do cliente {nome, cpf_cnpj}'},
                       'itens': {'type': 'array', 'description': 'Lista de itens [{descricao, unidade, quantidade, valor_unitario}]'},
                       'observacao': {'type': 'string', 'description': 'Observação'},
                   }, 'required': ['cliente', 'itens']}),
        types.Tool(name='tiny_pedidos_alterar_situacao', description='Altera situação de um pedido no Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do pedido'},
                       'situacao': {'type': 'string', 'description': 'Nova situação (aberto, faturado, cancelado, etc)'},
                   }, 'required': ['id', 'situacao']}),

        # ── Notas Fiscais ────────────────────────────────────────────────
        types.Tool(name='tiny_notas_fiscais_listar', description='Lista notas fiscais do Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por número/cliente'},
                       'situacao': {'type': 'string', 'description': 'Filtrar por situação'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='tiny_notas_fiscais_obter', description='Obtém detalhes de uma nota fiscal pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_notas_fiscais_xml', description='Obtém XML de uma nota fiscal pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='tiny_notas_fiscais_emitir', description='Emite/transmite uma nota fiscal já cadastrada no Tiny ERP', inputSchema=_ID_REQUIRED),

        # ── Formas de Pagamento ──────────────────────────────────────────
        types.Tool(name='tiny_formas_pagamento_listar', description='Lista formas de pagamento do Tiny ERP', inputSchema=_EMPTY),

        # ── Listas de Preço ──────────────────────────────────────────────
        types.Tool(name='tiny_listas_preco_listar', description='Lista listas de preço do Tiny ERP',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
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
        # Financeiro base
        case 'tiny_saldo': return c.get_balance()
        case 'tiny_titulos_pagar':
            return c.list_payables(from_date=args.get('from_date'), to_date=args.get('to_date'),
                                   limit=args.get('limit', 50), page=args.get('page', 1))
        case 'tiny_titulos_receber':
            return c.list_receivables(from_date=args.get('from_date'), to_date=args.get('to_date'),
                                      limit=args.get('limit', 50), page=args.get('page', 1))
        case 'tiny_pagar_titulo': return c.pay_payable(args['id'])
        case 'tiny_receber_titulo': return c.mark_received(args['id'])
        case 'tiny_criar_pagar':
            return c.create_payable(amount=args['amount'], due_date=args['due_date'],
                                    supplier=args['supplier'], category=args.get('category', ''),
                                    description=args.get('description', ''))
        case 'tiny_criar_receber':
            return c.create_receivable(amount=args['amount'], due_date=args['due_date'],
                                       customer=args['customer'], category=args.get('category', ''),
                                       description=args.get('description', ''))
        case 'tiny_cancelar_pagar': return c.cancel_payable(args['id'])
        case 'tiny_empresa': return c.company_info()
        # Contatos
        case 'tiny_contatos_listar': return c.list_contacts(search=args.get('search'), page=args.get('page', 1))
        case 'tiny_contatos_obter': return c.get_contact(args['id'])
        case 'tiny_contatos_criar': return c.create_contact(args)
        case 'tiny_contatos_atualizar': return c.update_contact(args)
        # Produtos
        case 'tiny_produtos_listar': return c.list_products(search=args.get('search'), page=args.get('page', 1))
        case 'tiny_produtos_obter': return c.get_product(args['id'])
        case 'tiny_produtos_criar': return c.create_product(args)
        case 'tiny_produtos_atualizar': return c.update_product(args)
        # Estoque
        case 'tiny_estoque_obter': return c.get_stock(args['id'])
        # Pedidos
        case 'tiny_pedidos_listar':
            return c.list_orders(search=args.get('search'), page=args.get('page', 1), situacao=args.get('situacao'))
        case 'tiny_pedidos_obter': return c.get_order(args['id'])
        case 'tiny_pedidos_criar': return c.create_order(args)
        case 'tiny_pedidos_alterar_situacao': return c.update_order_status(args['id'], args['situacao'])
        # Notas Fiscais
        case 'tiny_notas_fiscais_listar':
            return c.list_invoices(search=args.get('search'), page=args.get('page', 1), situacao=args.get('situacao'))
        case 'tiny_notas_fiscais_obter': return c.get_invoice(args['id'])
        case 'tiny_notas_fiscais_xml': return c.get_invoice_xml(args['id'])
        case 'tiny_notas_fiscais_emitir': return c.emit_invoice(args['id'])
        # Formas de Pagamento
        case 'tiny_formas_pagamento_listar': return c.list_payment_methods()
        # Listas de Preço
        case 'tiny_listas_preco_listar': return c.list_price_lists(page=args.get('page', 1))
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
