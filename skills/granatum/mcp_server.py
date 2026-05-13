#!/usr/bin/env python3
"""
MCP server para Granatum — 40 tools.
Endpoints cobertos: saldo, contas a pagar/receber, contas bancárias, categorias,
centros de custo, clientes, fornecedores, formas de pagamento, tipos de documento.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from granatum_client import GranatumClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('granatum')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = GranatumClient()
    return _client

_PAGINATION = {
    'limit': {'type': 'integer', 'description': 'Limite por página (default 50)', 'default': 50},
    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
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
        types.Tool(name='granatum_saldo', description='Saldo financeiro atual da empresa no Granatum', inputSchema=_EMPTY),
        types.Tool(name='granatum_titulos_pagar', description='Lista contas a pagar do Granatum (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, **_PAGINATION}, 'required': []}),
        types.Tool(name='granatum_titulos_receber', description='Lista contas a receber do Granatum (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, **_PAGINATION}, 'required': []}),
        types.Tool(name='granatum_lancamento_obter', description='Obtém detalhes de um lançamento pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_pagar_titulo', description='Marca título a pagar como pago no Granatum', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_receber_titulo', description='Marca título a receber como recebido no Granatum', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_criar_pagar', description='Cria novo título a pagar no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'supplier']}),
        types.Tool(name='granatum_criar_receber', description='Cria novo título a receber no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'customer': {'type': 'string', 'description': 'Nome do cliente'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'customer']}),
        types.Tool(name='granatum_lancamento_atualizar', description='Atualiza lançamento no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do lançamento'},
                       'descricao': {'type': 'string', 'description': 'Descrição'},
                       'valor': {'type': 'number', 'description': 'Valor'},
                       'data_vencimento': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                   }, 'required': ['id']}),
        types.Tool(name='granatum_cancelar_pagar', description='Cancela/exclui título a pagar no Granatum', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_cancelar_receber', description='Cancela/exclui título a receber no Granatum', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_empresa', description='Informações da empresa conectada ao Granatum', inputSchema=_EMPTY),

        # ── Contas Bancárias ─────────────────────────────────────────────
        types.Tool(name='granatum_contas_bancarias_listar', description='Lista contas bancárias do Granatum', inputSchema=_EMPTY),
        types.Tool(name='granatum_contas_bancarias_obter', description='Obtém conta bancária pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_contas_bancarias_criar', description='Cria nova conta bancária no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'descricao': {'type': 'string', 'description': 'Descrição da conta'},
                       'banco': {'type': 'string', 'description': 'Nome do banco'},
                       'saldo_inicial': {'type': 'number', 'description': 'Saldo inicial'},
                   }, 'required': ['descricao']}),
        types.Tool(name='granatum_contas_bancarias_atualizar', description='Atualiza conta bancária no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID da conta'},
                       'descricao': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['id']}),
        types.Tool(name='granatum_contas_bancarias_excluir', description='Exclui conta bancária pelo ID', inputSchema=_ID_REQUIRED),

        # ── Categorias ───────────────────────────────────────────────────
        types.Tool(name='granatum_categorias_listar', description='Lista categorias financeiras do Granatum', inputSchema=_EMPTY),
        types.Tool(name='granatum_categorias_obter', description='Obtém categoria pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_categorias_criar', description='Cria nova categoria financeira no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'descricao': {'type': 'string', 'description': 'Descrição da categoria'},
                       'tipo': {'type': 'string', 'description': 'Tipo: receita ou despesa'},
                   }, 'required': ['descricao']}),
        types.Tool(name='granatum_categorias_atualizar', description='Atualiza categoria no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID da categoria'},
                       'descricao': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['id']}),
        types.Tool(name='granatum_categorias_excluir', description='Exclui categoria pelo ID', inputSchema=_ID_REQUIRED),

        # ── Centros de Custo ─────────────────────────────────────────────
        types.Tool(name='granatum_centros_custo_listar', description='Lista centros de custo do Granatum', inputSchema=_EMPTY),
        types.Tool(name='granatum_centros_custo_obter', description='Obtém centro de custo pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_centros_custo_criar', description='Cria novo centro de custo no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'descricao': {'type': 'string', 'description': 'Descrição do centro de custo'},
                   }, 'required': ['descricao']}),
        types.Tool(name='granatum_centros_custo_atualizar', description='Atualiza centro de custo no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do centro de custo'},
                       'descricao': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['id']}),
        types.Tool(name='granatum_centros_custo_excluir', description='Exclui centro de custo pelo ID', inputSchema=_ID_REQUIRED),

        # ── Clientes ─────────────────────────────────────────────────────
        types.Tool(name='granatum_clientes_listar', description='Lista clientes cadastrados no Granatum',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='granatum_clientes_obter', description='Obtém cliente pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_clientes_criar', description='Cria novo cliente no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'nome': {'type': 'string', 'description': 'Nome do cliente'},
                       'documento': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'telefone': {'type': 'string', 'description': 'Telefone'},
                   }, 'required': ['nome']}),
        types.Tool(name='granatum_clientes_atualizar', description='Atualiza cliente no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do cliente'},
                       'nome': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                   }, 'required': ['id']}),
        types.Tool(name='granatum_clientes_excluir', description='Exclui cliente pelo ID', inputSchema=_ID_REQUIRED),

        # ── Fornecedores ─────────────────────────────────────────────────
        types.Tool(name='granatum_fornecedores_listar', description='Lista fornecedores cadastrados no Granatum',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='granatum_fornecedores_obter', description='Obtém fornecedor pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='granatum_fornecedores_criar', description='Cria novo fornecedor no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'nome': {'type': 'string', 'description': 'Nome do fornecedor'},
                       'documento': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                   }, 'required': ['nome']}),
        types.Tool(name='granatum_fornecedores_atualizar', description='Atualiza fornecedor no Granatum',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do fornecedor'},
                       'nome': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                   }, 'required': ['id']}),
        types.Tool(name='granatum_fornecedores_excluir', description='Exclui fornecedor pelo ID', inputSchema=_ID_REQUIRED),

        # ── Auxiliares ───────────────────────────────────────────────────
        types.Tool(name='granatum_formas_pagamento_listar', description='Lista formas de pagamento do Granatum', inputSchema=_EMPTY),
        types.Tool(name='granatum_tipos_documento_listar', description='Lista tipos de documento do Granatum', inputSchema=_EMPTY),
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
        case 'granatum_saldo': return c.get_balance()
        case 'granatum_titulos_pagar':
            return c.list_payables(from_date=args.get('from_date'), to_date=args.get('to_date'),
                                   limit=args.get('limit', 50), page=args.get('page', 1))
        case 'granatum_titulos_receber':
            return c.list_receivables(from_date=args.get('from_date'), to_date=args.get('to_date'),
                                      limit=args.get('limit', 50), page=args.get('page', 1))
        case 'granatum_lancamento_obter': return c.get_entry(args['id'])
        case 'granatum_pagar_titulo': return c.pay_payable(args['id'])
        case 'granatum_receber_titulo': return c.mark_received(args['id'])
        case 'granatum_criar_pagar':
            return c.create_payable(amount=args['amount'], due_date=args['due_date'],
                                    supplier=args['supplier'], category=args.get('category', ''),
                                    description=args.get('description', ''))
        case 'granatum_criar_receber':
            return c.create_receivable(amount=args['amount'], due_date=args['due_date'],
                                       customer=args['customer'], category=args.get('category', ''),
                                       description=args.get('description', ''))
        case 'granatum_lancamento_atualizar':
            id = args.pop('id'); return c.update_entry(id, args)
        case 'granatum_cancelar_pagar': return c.delete_entry(args['id'])
        case 'granatum_cancelar_receber': return c.delete_entry(args['id'])
        case 'granatum_empresa': return c.company_info()
        # Contas Bancárias
        case 'granatum_contas_bancarias_listar': return c.list_bank_accounts()
        case 'granatum_contas_bancarias_obter': return c.get_bank_account(args['id'])
        case 'granatum_contas_bancarias_criar': return c.create_bank_account(args)
        case 'granatum_contas_bancarias_atualizar':
            id = args.pop('id'); return c.update_bank_account(id, args)
        case 'granatum_contas_bancarias_excluir': return c.delete_bank_account(args['id'])
        # Categorias
        case 'granatum_categorias_listar': return c.list_categories()
        case 'granatum_categorias_obter': return c.get_category(args['id'])
        case 'granatum_categorias_criar': return c.create_category(args)
        case 'granatum_categorias_atualizar':
            id = args.pop('id'); return c.update_category(id, args)
        case 'granatum_categorias_excluir': return c.delete_category(args['id'])
        # Centros de Custo
        case 'granatum_centros_custo_listar': return c.list_cost_centers()
        case 'granatum_centros_custo_obter': return c.get_cost_center(args['id'])
        case 'granatum_centros_custo_criar': return c.create_cost_center(args)
        case 'granatum_centros_custo_atualizar':
            id = args.pop('id'); return c.update_cost_center(id, args)
        case 'granatum_centros_custo_excluir': return c.delete_cost_center(args['id'])
        # Clientes
        case 'granatum_clientes_listar':
            return c.list_customers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'granatum_clientes_obter': return c.get_customer(args['id'])
        case 'granatum_clientes_criar': return c.create_customer(args)
        case 'granatum_clientes_atualizar':
            id = args.pop('id'); return c.update_customer(id, args)
        case 'granatum_clientes_excluir': return c.delete_customer(args['id'])
        # Fornecedores
        case 'granatum_fornecedores_listar':
            return c.list_suppliers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'granatum_fornecedores_obter': return c.get_supplier(args['id'])
        case 'granatum_fornecedores_criar': return c.create_supplier(args)
        case 'granatum_fornecedores_atualizar':
            id = args.pop('id'); return c.update_supplier(id, args)
        case 'granatum_fornecedores_excluir': return c.delete_supplier(args['id'])
        # Auxiliares
        case 'granatum_formas_pagamento_listar': return c.list_payment_methods()
        case 'granatum_tipos_documento_listar': return c.list_document_types()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
