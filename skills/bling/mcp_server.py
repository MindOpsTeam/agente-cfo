#!/usr/bin/env python3
"""
MCP server para Bling — 35 tools.
Endpoints cobertos: saldo, contas a pagar/receber, produtos, pedidos de venda,
NF-e, NFC-e, contatos, estoque, categorias, formas de pagamento, contas correntes.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from bling_client import BlingClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('bling')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = BlingClient()
    return _client

# ── Pagination schema fragment ──────────────────────────────────────────────
_PAGINATED = {
    'limit': {'type': 'integer', 'description': 'Limite por pagina (default 100)', 'default': 100},
    'page': {'type': 'integer', 'description': 'Pagina (default 1)', 'default': 1},
}
_DATE_RANGE = {
    'from_date': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'},
    'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
}

def _schema(props: dict, required: list | None = None):
    return {'type': 'object', 'properties': props, 'required': required or []}

def _empty():
    return _schema({})


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Financeiro ──────────────────────────────────────────────────
        types.Tool(name='bling_saldo', description='Saldo financeiro atual da empresa no Bling', inputSchema=_empty()),
        types.Tool(name='bling_contas_correntes', description='Lista contas correntes/bancarias cadastradas no Bling', inputSchema=_empty()),
        types.Tool(name='bling_titulos_pagar', description='Lista contas a pagar do Bling (paginado)',
            inputSchema=_schema({**_DATE_RANGE, **_PAGINATED})),
        types.Tool(name='bling_titulos_receber', description='Lista contas a receber do Bling (paginado)',
            inputSchema=_schema({**_DATE_RANGE, **_PAGINATED})),
        types.Tool(name='bling_get_pagar', description='Detalha uma conta a pagar pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo'}}, ['id'])),
        types.Tool(name='bling_get_receber', description='Detalha uma conta a receber pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo'}}, ['id'])),
        types.Tool(name='bling_pagar_titulo', description='Marca titulo a pagar como pago (baixa) no Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo a pagar'}}, ['id'])),
        types.Tool(name='bling_receber_titulo', description='Marca titulo a receber como recebido (baixa) no Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo a receber'}}, ['id'])),
        types.Tool(name='bling_criar_pagar', description='Cria novo titulo a pagar no Bling',
            inputSchema=_schema({
                'amount': {'type': 'number', 'description': 'Valor em BRL'},
                'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                'category': {'type': 'string', 'description': 'Categoria'},
                'description': {'type': 'string', 'description': 'Descricao'},
            }, ['amount', 'due_date', 'supplier'])),
        types.Tool(name='bling_criar_receber', description='Cria novo titulo a receber no Bling',
            inputSchema=_schema({
                'amount': {'type': 'number', 'description': 'Valor em BRL'},
                'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                'customer': {'type': 'string', 'description': 'Nome do cliente'},
                'category': {'type': 'string', 'description': 'Categoria'},
                'description': {'type': 'string', 'description': 'Descricao'},
            }, ['amount', 'due_date', 'customer'])),
        types.Tool(name='bling_deletar_pagar', description='Exclui titulo a pagar do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo'}}, ['id'])),
        types.Tool(name='bling_deletar_receber', description='Exclui titulo a receber do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo'}}, ['id'])),
        types.Tool(name='bling_formas_pagamento', description='Lista formas de pagamento cadastradas no Bling',
            inputSchema=_schema({**_PAGINATED})),
        # ── Produtos ────────────────────────────────────────────────────
        types.Tool(name='bling_listar_produtos', description='Lista produtos cadastrados no Bling',
            inputSchema=_schema({
                'nome': {'type': 'string', 'description': 'Filtrar por nome do produto'},
                **_PAGINATED,
            })),
        types.Tool(name='bling_get_produto', description='Detalha um produto pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do produto'}}, ['id'])),
        types.Tool(name='bling_criar_produto', description='Cria um novo produto no Bling',
            inputSchema=_schema({
                'nome': {'type': 'string', 'description': 'Nome do produto'},
                'preco': {'type': 'number', 'description': 'Preco de venda'},
                'codigo': {'type': 'string', 'description': 'Codigo/SKU do produto'},
                'unidade': {'type': 'string', 'description': 'Unidade (UN, KG, etc)', 'default': 'UN'},
                'tipo': {'type': 'string', 'description': 'Tipo: S=servico, P=produto', 'default': 'P'},
            }, ['nome', 'preco'])),
        types.Tool(name='bling_atualizar_produto', description='Atualiza um produto existente no Bling',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do produto'},
                'nome': {'type': 'string', 'description': 'Nome do produto'},
                'preco': {'type': 'number', 'description': 'Preco de venda'},
                'codigo': {'type': 'string', 'description': 'Codigo/SKU'},
            }, ['id'])),
        types.Tool(name='bling_deletar_produto', description='Exclui um produto do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do produto'}}, ['id'])),
        # ── Pedidos de Venda ────────────────────────────────────────────
        types.Tool(name='bling_listar_pedidos', description='Lista pedidos de venda do Bling',
            inputSchema=_schema({**_DATE_RANGE, **_PAGINATED})),
        types.Tool(name='bling_get_pedido', description='Detalha um pedido de venda pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do pedido'}}, ['id'])),
        types.Tool(name='bling_criar_pedido', description='Cria um novo pedido de venda no Bling (corpo livre)',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo do pedido conforme API Bling v3'},
            }, ['body'])),
        # ── NF-e ────────────────────────────────────────────────────────
        types.Tool(name='bling_listar_nfe', description='Lista notas fiscais eletronicas (NF-e) do Bling',
            inputSchema=_schema({**_DATE_RANGE, **_PAGINATED})),
        types.Tool(name='bling_get_nfe', description='Detalha uma NF-e pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NF-e'}}, ['id'])),
        types.Tool(name='bling_criar_nfe', description='Cria uma NF-e no Bling (corpo livre)',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo da NF-e conforme API Bling v3'},
            }, ['body'])),
        types.Tool(name='bling_transmitir_nfe', description='Transmite (envia para SEFAZ) uma NF-e ja criada',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NF-e'}}, ['id'])),
        # ── NFC-e ───────────────────────────────────────────────────────
        types.Tool(name='bling_listar_nfce', description='Lista notas fiscais de consumidor (NFC-e) do Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_get_nfce', description='Detalha uma NFC-e pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NFC-e'}}, ['id'])),
        # ── Contatos ────────────────────────────────────────────────────
        types.Tool(name='bling_listar_contatos', description='Lista contatos (clientes/fornecedores) do Bling',
            inputSchema=_schema({
                'nome': {'type': 'string', 'description': 'Filtrar por nome'},
                'tipo': {'type': 'string', 'description': 'Filtrar por tipo (F=fornecedor, J=juridica, etc)'},
                **_PAGINATED,
            })),
        types.Tool(name='bling_get_contato', description='Detalha um contato pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do contato'}}, ['id'])),
        types.Tool(name='bling_criar_contato', description='Cria um novo contato no Bling',
            inputSchema=_schema({
                'nome': {'type': 'string', 'description': 'Nome do contato'},
                'tipoPessoa': {'type': 'string', 'description': 'F=fisica, J=juridica', 'default': 'J'},
                'numeroDocumento': {'type': 'string', 'description': 'CPF ou CNPJ'},
                'email': {'type': 'string', 'description': 'Email'},
                'telefone': {'type': 'string', 'description': 'Telefone'},
            }, ['nome'])),
        types.Tool(name='bling_atualizar_contato', description='Atualiza um contato existente no Bling',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do contato'},
                'nome': {'type': 'string', 'description': 'Nome'},
                'email': {'type': 'string', 'description': 'Email'},
                'telefone': {'type': 'string', 'description': 'Telefone'},
            }, ['id'])),
        # ── Estoque ─────────────────────────────────────────────────────
        types.Tool(name='bling_estoque', description='Consulta saldo de estoque de um produto',
            inputSchema=_schema({'product_id': {'type': 'string', 'description': 'ID do produto'}}, ['product_id'])),
        types.Tool(name='bling_ajustar_estoque', description='Ajusta estoque de um produto no Bling',
            inputSchema=_schema({
                'product_id': {'type': 'string', 'description': 'ID do produto'},
                'quantity': {'type': 'number', 'description': 'Quantidade'},
                'operation': {'type': 'string', 'description': 'B=Balanco, E=Entrada, S=Saida', 'default': 'B'},
                'notes': {'type': 'string', 'description': 'Observacoes'},
            }, ['product_id', 'quantity'])),
        # ── Categorias ──────────────────────────────────────────────────
        types.Tool(name='bling_categorias', description='Lista categorias de produtos do Bling',
            inputSchema=_schema({**_PAGINATED})),
        # ── Empresa ─────────────────────────────────────────────────────
        types.Tool(name='bling_empresa', description='Informacoes da empresa conectada ao Bling', inputSchema=_empty()),
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
        # ── Financeiro ──────────────────────────────────────────────
        case 'bling_saldo':
            return c.get_balance()
        case 'bling_contas_correntes':
            return c.list_bank_accounts()
        case 'bling_titulos_pagar':
            return c.list_payables(
                from_date=args.get('from_date'), to_date=args.get('to_date'),
                limit=args.get('limit', 100), page=args.get('page', 1))
        case 'bling_titulos_receber':
            return c.list_receivables(
                from_date=args.get('from_date'), to_date=args.get('to_date'),
                limit=args.get('limit', 100), page=args.get('page', 1))
        case 'bling_get_pagar':
            return c.get_payable(args['id'])
        case 'bling_get_receber':
            return c.get_receivable(args['id'])
        case 'bling_pagar_titulo':
            return c.pay_payable(args['id'])
        case 'bling_receber_titulo':
            return c.mark_received(args['id'])
        case 'bling_criar_pagar':
            return c.create_payable(
                amount=args['amount'], due_date=args['due_date'], supplier=args['supplier'],
                category=args.get('category', ''), description=args.get('description', ''))
        case 'bling_criar_receber':
            return c.create_receivable(
                amount=args['amount'], due_date=args['due_date'], customer=args['customer'],
                category=args.get('category', ''), description=args.get('description', ''))
        case 'bling_deletar_pagar':
            return c.delete_payable(args['id'])
        case 'bling_deletar_receber':
            return c.delete_receivable(args['id'])
        case 'bling_formas_pagamento':
            return c.list_payment_methods(page=args.get('page', 1), limit=args.get('limit', 100))
        # ── Produtos ────────────────────────────────────────────────
        case 'bling_listar_produtos':
            return c.list_products(page=args.get('page', 1), limit=args.get('limit', 100), nome=args.get('nome'))
        case 'bling_get_produto':
            return c.get_product(args['id'])
        case 'bling_criar_produto':
            body = {'nome': args['nome'], 'preco': args['preco']}
            if args.get('codigo'): body['codigo'] = args['codigo']
            if args.get('unidade'): body['unidade'] = args['unidade']
            if args.get('tipo'): body['tipo'] = args['tipo']
            return c.create_product(body)
        case 'bling_atualizar_produto':
            body = {}
            if args.get('nome'): body['nome'] = args['nome']
            if args.get('preco'): body['preco'] = args['preco']
            if args.get('codigo'): body['codigo'] = args['codigo']
            return c.update_product(args['id'], body)
        case 'bling_deletar_produto':
            return c.delete_product(args['id'])
        # ── Pedidos de Venda ────────────────────────────────────────
        case 'bling_listar_pedidos':
            return c.list_sales_orders(
                page=args.get('page', 1), limit=args.get('limit', 100),
                from_date=args.get('from_date'), to_date=args.get('to_date'))
        case 'bling_get_pedido':
            return c.get_sales_order(args['id'])
        case 'bling_criar_pedido':
            return c.create_sales_order(args['body'])
        # ── NF-e ────────────────────────────────────────────────────
        case 'bling_listar_nfe':
            return c.list_nfe(
                page=args.get('page', 1), limit=args.get('limit', 100),
                from_date=args.get('from_date'), to_date=args.get('to_date'))
        case 'bling_get_nfe':
            return c.get_nfe(args['id'])
        case 'bling_criar_nfe':
            return c.create_nfe(args['body'])
        case 'bling_transmitir_nfe':
            return c.transmit_nfe(args['id'])
        # ── NFC-e ───────────────────────────────────────────────────
        case 'bling_listar_nfce':
            return c.list_nfce(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_get_nfce':
            return c.get_nfce(args['id'])
        # ── Contatos ────────────────────────────────────────────────
        case 'bling_listar_contatos':
            return c.list_contacts(
                page=args.get('page', 1), limit=args.get('limit', 100),
                nome=args.get('nome'), tipo=args.get('tipo'))
        case 'bling_get_contato':
            return c.get_contact(args['id'])
        case 'bling_criar_contato':
            body = {'nome': args['nome']}
            for k in ('tipoPessoa', 'numeroDocumento', 'email', 'telefone'):
                if args.get(k): body[k] = args[k]
            return c.create_contact(body)
        case 'bling_atualizar_contato':
            body = {}
            for k in ('nome', 'email', 'telefone'):
                if args.get(k): body[k] = args[k]
            return c.update_contact(args['id'], body)
        # ── Estoque ─────────────────────────────────────────────────
        case 'bling_estoque':
            return c.get_stock(args['product_id'])
        case 'bling_ajustar_estoque':
            return c.adjust_stock(
                product_id=args['product_id'], quantity=args['quantity'],
                operation=args.get('operation', 'B'), notes=args.get('notes', ''))
        # ── Categorias ──────────────────────────────────────────────
        case 'bling_categorias':
            return c.list_categories(page=args.get('page', 1), limit=args.get('limit', 100))
        # ── Empresa ─────────────────────────────────────────────────
        case 'bling_empresa':
            return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
