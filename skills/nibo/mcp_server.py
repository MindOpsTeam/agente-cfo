#!/usr/bin/env python3
"""
MCP server para Nibo — 42 tools.
Endpoints cobertos: saldo, contas a pagar/receber, contas bancárias, categorias,
centros de custo, clientes, fornecedores, transferências, conciliação, lançamentos,
relatórios (DRE, fluxo de caixa).
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
        types.Tool(name='nibo_saldo', description='Saldo financeiro atual da empresa no Nibo', inputSchema=_EMPTY),
        types.Tool(name='nibo_titulos_pagar', description='Lista contas a pagar do Nibo (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, **_PAGINATION}, 'required': []}),
        types.Tool(name='nibo_titulos_receber', description='Lista contas a receber do Nibo (paginado)',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, **_PAGINATION}, 'required': []}),
        types.Tool(name='nibo_pagar_obter', description='Obtém detalhes de um título a pagar pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_receber_obter', description='Obtém detalhes de um título a receber pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_pagar_titulo', description='Marca título a pagar como pago no Nibo', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_receber_titulo', description='Marca título a receber como recebido no Nibo', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_criar_pagar', description='Cria novo título a pagar no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'supplier']}),
        types.Tool(name='nibo_criar_receber', description='Cria novo título a receber no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'customer': {'type': 'string', 'description': 'Nome do cliente'},
                       'category': {'type': 'string', 'description': 'Categoria'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['amount', 'due_date', 'customer']}),
        types.Tool(name='nibo_excluir_pagar', description='Exclui título a pagar pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_excluir_receber', description='Exclui título a receber pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_empresa', description='Informações da empresa conectada ao Nibo', inputSchema=_EMPTY),

        # ── Contas Bancárias ─────────────────────────────────────────────
        types.Tool(name='nibo_contas_bancarias_listar', description='Lista contas bancárias cadastradas no Nibo', inputSchema=_EMPTY),
        types.Tool(name='nibo_contas_bancarias_obter', description='Obtém detalhes de uma conta bancária pelo ID', inputSchema=_ID_REQUIRED),

        # ── Categorias ───────────────────────────────────────────────────
        types.Tool(name='nibo_categorias_listar', description='Lista categorias financeiras do Nibo', inputSchema=_EMPTY),
        types.Tool(name='nibo_categorias_obter', description='Obtém detalhes de uma categoria pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_categorias_criar', description='Cria nova categoria financeira no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome da categoria'},
                       'type': {'type': 'string', 'description': 'Tipo: debit ou credit'},
                   }, 'required': ['name']}),
        types.Tool(name='nibo_categorias_atualizar', description='Atualiza categoria financeira no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID da categoria'},
                       'name': {'type': 'string', 'description': 'Novo nome'},
                   }, 'required': ['id']}),
        types.Tool(name='nibo_categorias_excluir', description='Exclui categoria financeira pelo ID', inputSchema=_ID_REQUIRED),

        # ── Centros de Custo ─────────────────────────────────────────────
        types.Tool(name='nibo_centros_custo_listar', description='Lista centros de custo do Nibo', inputSchema=_EMPTY),
        types.Tool(name='nibo_centros_custo_obter', description='Obtém detalhes de um centro de custo pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_centros_custo_criar', description='Cria novo centro de custo no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do centro de custo'},
                   }, 'required': ['name']}),
        types.Tool(name='nibo_centros_custo_atualizar', description='Atualiza centro de custo no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do centro de custo'},
                       'name': {'type': 'string', 'description': 'Novo nome'},
                   }, 'required': ['id']}),
        types.Tool(name='nibo_centros_custo_excluir', description='Exclui centro de custo pelo ID', inputSchema=_ID_REQUIRED),

        # ── Clientes ─────────────────────────────────────────────────────
        types.Tool(name='nibo_clientes_listar', description='Lista clientes cadastrados no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por nome'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='nibo_clientes_obter', description='Obtém detalhes de um cliente pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_clientes_criar', description='Cria novo cliente no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do cliente'},
                       'document': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'phone': {'type': 'string', 'description': 'Telefone'},
                   }, 'required': ['name']}),
        types.Tool(name='nibo_clientes_atualizar', description='Atualiza dados de um cliente no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do cliente'},
                       'name': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                   }, 'required': ['id']}),
        types.Tool(name='nibo_clientes_excluir', description='Exclui cliente pelo ID', inputSchema=_ID_REQUIRED),

        # ── Fornecedores ─────────────────────────────────────────────────
        types.Tool(name='nibo_fornecedores_listar', description='Lista fornecedores cadastrados no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por nome'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='nibo_fornecedores_obter', description='Obtém detalhes de um fornecedor pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='nibo_fornecedores_criar', description='Cria novo fornecedor no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do fornecedor'},
                       'document': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'phone': {'type': 'string', 'description': 'Telefone'},
                   }, 'required': ['name']}),
        types.Tool(name='nibo_fornecedores_atualizar', description='Atualiza dados de um fornecedor no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do fornecedor'},
                       'name': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                   }, 'required': ['id']}),
        types.Tool(name='nibo_fornecedores_excluir', description='Exclui fornecedor pelo ID', inputSchema=_ID_REQUIRED),

        # ── Transferências ───────────────────────────────────────────────
        types.Tool(name='nibo_transferencias_listar', description='Lista transferências entre contas no Nibo',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='nibo_transferencias_criar', description='Cria transferência entre contas bancárias no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'fromBankAccountId': {'type': 'string', 'description': 'ID conta origem'},
                       'toBankAccountId': {'type': 'string', 'description': 'ID conta destino'},
                       'value': {'type': 'number', 'description': 'Valor em BRL'},
                       'date': {'type': 'string', 'description': 'Data da transferência (YYYY-MM-DD)'},
                   }, 'required': ['fromBankAccountId', 'toBankAccountId', 'value', 'date']}),

        # ── Conciliação ──────────────────────────────────────────────────
        types.Tool(name='nibo_conciliacao_listar', description='Lista conciliações de uma conta bancária no Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'bank_account_id': {'type': 'string', 'description': 'ID da conta bancária'},
                       **_PAGINATION,
                   }, 'required': ['bank_account_id']}),

        # ── Lançamentos / Extrato ────────────────────────────────────────
        types.Tool(name='nibo_lancamentos_listar', description='Lista lançamentos (extrato geral) do Nibo',
                   inputSchema={'type': 'object', 'properties': {**_DATE_RANGE, **_PAGINATION}, 'required': []}),

        # ── Relatórios ───────────────────────────────────────────────────
        types.Tool(name='nibo_relatorio_dre', description='Gera relatório DRE (Demonstrativo de Resultados) do Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'from_date': {'type': 'string', 'description': 'Data início (YYYY-MM-DD)'},
                       'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
                   }, 'required': ['from_date', 'to_date']}),
        types.Tool(name='nibo_relatorio_fluxo_caixa', description='Gera relatório de fluxo de caixa do Nibo',
                   inputSchema={'type': 'object', 'properties': {
                       'from_date': {'type': 'string', 'description': 'Data início (YYYY-MM-DD)'},
                       'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
                   }, 'required': ['from_date', 'to_date']}),
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
        case 'nibo_saldo': return c.get_balance()
        case 'nibo_titulos_pagar':
            return c.list_payables(from_date=args.get('from_date'), to_date=args.get('to_date'),
                                   limit=args.get('limit', 50), page=args.get('page', 1))
        case 'nibo_titulos_receber':
            return c.list_receivables(from_date=args.get('from_date'), to_date=args.get('to_date'),
                                      limit=args.get('limit', 50), page=args.get('page', 1))
        case 'nibo_pagar_obter': return c.get_payable(args['id'])
        case 'nibo_receber_obter': return c.get_receivable(args['id'])
        case 'nibo_pagar_titulo': return c.pay_payable(args['id'])
        case 'nibo_receber_titulo': return c.mark_received(args['id'])
        case 'nibo_criar_pagar':
            return c.create_payable(amount=args['amount'], due_date=args['due_date'],
                                    supplier=args['supplier'], category=args.get('category', ''),
                                    description=args.get('description', ''))
        case 'nibo_criar_receber':
            return c.create_receivable(amount=args['amount'], due_date=args['due_date'],
                                       customer=args['customer'], category=args.get('category', ''),
                                       description=args.get('description', ''))
        case 'nibo_excluir_pagar': return c.delete_payable(args['id'])
        case 'nibo_excluir_receber': return c.delete_receivable(args['id'])
        case 'nibo_empresa': return c.company_info()
        # Contas Bancárias
        case 'nibo_contas_bancarias_listar': return c.list_bank_accounts()
        case 'nibo_contas_bancarias_obter': return c.get_bank_account(args['id'])
        # Categorias
        case 'nibo_categorias_listar': return c.list_categories()
        case 'nibo_categorias_obter': return c.get_category(args['id'])
        case 'nibo_categorias_criar': return c.create_category(args)
        case 'nibo_categorias_atualizar':
            id = args.pop('id'); return c.update_category(id, args)
        case 'nibo_categorias_excluir': return c.delete_category(args['id'])
        # Centros de Custo
        case 'nibo_centros_custo_listar': return c.list_cost_centers()
        case 'nibo_centros_custo_obter': return c.get_cost_center(args['id'])
        case 'nibo_centros_custo_criar': return c.create_cost_center(args)
        case 'nibo_centros_custo_atualizar':
            id = args.pop('id'); return c.update_cost_center(id, args)
        case 'nibo_centros_custo_excluir': return c.delete_cost_center(args['id'])
        # Clientes
        case 'nibo_clientes_listar':
            return c.list_customers(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search'))
        case 'nibo_clientes_obter': return c.get_customer(args['id'])
        case 'nibo_clientes_criar': return c.create_customer(args)
        case 'nibo_clientes_atualizar':
            id = args.pop('id'); return c.update_customer(id, args)
        case 'nibo_clientes_excluir': return c.delete_customer(args['id'])
        # Fornecedores
        case 'nibo_fornecedores_listar':
            return c.list_suppliers(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search'))
        case 'nibo_fornecedores_obter': return c.get_supplier(args['id'])
        case 'nibo_fornecedores_criar': return c.create_supplier(args)
        case 'nibo_fornecedores_atualizar':
            id = args.pop('id'); return c.update_supplier(id, args)
        case 'nibo_fornecedores_excluir': return c.delete_supplier(args['id'])
        # Transferências
        case 'nibo_transferencias_listar':
            return c.list_transfers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'nibo_transferencias_criar': return c.create_transfer(args)
        # Conciliação
        case 'nibo_conciliacao_listar':
            return c.list_reconciliations(args['bank_account_id'], limit=args.get('limit', 50), page=args.get('page', 1))
        # Lançamentos
        case 'nibo_lancamentos_listar':
            return c.list_entries(limit=args.get('limit', 50), page=args.get('page', 1),
                                  from_date=args.get('from_date'), to_date=args.get('to_date'))
        # Relatórios
        case 'nibo_relatorio_dre': return c.get_dre_report(args['from_date'], args['to_date'])
        case 'nibo_relatorio_fluxo_caixa': return c.get_cashflow_report(args['from_date'], args['to_date'])
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
