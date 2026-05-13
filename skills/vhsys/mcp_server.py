#!/usr/bin/env python3
"""
MCP server para VHSys — 35 tools.
Endpoints cobertos: saldo, contas a pagar/receber, clientes, fornecedores,
produtos, pedidos de venda/compra, notas fiscais, categorias financeiras,
centros de custo, transportadoras, vendedores, orcamentos, ordens de servico.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from vhsys_client import VHSYSClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('vhsys')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = VHSYSClient()
    return _client

# ── Schemas reutilizáveis ────────────────────────────────────────────────────

_PAGINATION = {
    'limit': {'type': 'integer', 'description': 'Limite por página (default 50)', 'default': 50},
    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
}

_DATE_RANGE = {
    'from_date': {'type': 'string', 'description': 'Data início (YYYY-MM-DD)'},
    'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
}

_ID_REQUIRED = {
    'type': 'object',
    'properties': {'id': {'type': 'string', 'description': 'ID do registro'}},
    'required': ['id'],
}

_EMPTY = {'type': 'object', 'properties': {}, 'required': []}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Financeiro existente ─────────────────────────────────────────
        types.Tool(
            name='vhsys_saldo',
            description='Saldo financeiro atual da empresa no VHSys',
            inputSchema=_EMPTY,
        ),
        types.Tool(
            name='vhsys_titulos_pagar',
            description='Lista contas a pagar do VHSys (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {**_DATE_RANGE, **_PAGINATION},
                'required': [],
            },
        ),
        types.Tool(
            name='vhsys_titulos_receber',
            description='Lista contas a receber do VHSys (paginado)',
            inputSchema={
                'type': 'object',
                'properties': {**_DATE_RANGE, **_PAGINATION},
                'required': [],
            },
        ),
        types.Tool(
            name='vhsys_pagar_obter',
            description='Obtém detalhes de um título a pagar pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_receber_obter',
            description='Obtém detalhes de um título a receber pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_pagar_titulo',
            description='Marca título a pagar como pago no VHSys',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_receber_titulo',
            description='Marca título a receber como recebido no VHSys',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_criar_pagar',
            description='Cria novo título a pagar no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'description': 'Valor em BRL'},
                    'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                    'supplier': {'type': 'string', 'description': 'Nome do fornecedor'},
                    'category': {'type': 'string', 'description': 'Categoria'},
                    'description': {'type': 'string', 'description': 'Descrição'},
                },
                'required': ['amount', 'due_date', 'supplier'],
            },
        ),
        types.Tool(
            name='vhsys_criar_receber',
            description='Cria novo título a receber no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'amount': {'type': 'number', 'description': 'Valor em BRL'},
                    'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                    'customer': {'type': 'string', 'description': 'Nome do cliente'},
                    'category': {'type': 'string', 'description': 'Categoria'},
                    'description': {'type': 'string', 'description': 'Descrição'},
                },
                'required': ['amount', 'due_date', 'customer'],
            },
        ),
        types.Tool(
            name='vhsys_excluir_pagar',
            description='Exclui título a pagar pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_excluir_receber',
            description='Exclui título a receber pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_empresa',
            description='Informações da empresa conectada ao VHSys',
            inputSchema=_EMPTY,
        ),

        # ── Contas Bancárias ─────────────────────────────────────────────
        types.Tool(
            name='vhsys_contas_bancarias_listar',
            description='Lista contas bancárias cadastradas no VHSys',
            inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []},
        ),
        types.Tool(
            name='vhsys_contas_bancarias_obter',
            description='Obtém detalhes de uma conta bancária pelo ID',
            inputSchema=_ID_REQUIRED,
        ),

        # ── Clientes ─────────────────────────────────────────────────────
        types.Tool(
            name='vhsys_clientes_listar',
            description='Lista clientes cadastrados no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'search': {'type': 'string', 'description': 'Buscar por razão social'},
                    **_PAGINATION,
                },
                'required': [],
            },
        ),
        types.Tool(
            name='vhsys_clientes_obter',
            description='Obtém detalhes de um cliente pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_clientes_criar',
            description='Cria novo cliente no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'razao_social': {'type': 'string', 'description': 'Razão social do cliente'},
                    'cnpj_cpf': {'type': 'string', 'description': 'CNPJ ou CPF'},
                    'email': {'type': 'string', 'description': 'E-mail'},
                    'telefone': {'type': 'string', 'description': 'Telefone'},
                    'endereco': {'type': 'string', 'description': 'Endereço'},
                    'cidade': {'type': 'string', 'description': 'Cidade'},
                    'uf': {'type': 'string', 'description': 'UF (2 letras)'},
                    'cep': {'type': 'string', 'description': 'CEP'},
                },
                'required': ['razao_social'],
            },
        ),
        types.Tool(
            name='vhsys_clientes_atualizar',
            description='Atualiza dados de um cliente no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do cliente'},
                    'razao_social': {'type': 'string', 'description': 'Razão social'},
                    'cnpj_cpf': {'type': 'string', 'description': 'CNPJ ou CPF'},
                    'email': {'type': 'string', 'description': 'E-mail'},
                    'telefone': {'type': 'string', 'description': 'Telefone'},
                },
                'required': ['id'],
            },
        ),
        types.Tool(
            name='vhsys_clientes_excluir',
            description='Exclui cliente pelo ID',
            inputSchema=_ID_REQUIRED,
        ),

        # ── Fornecedores ─────────────────────────────────────────────────
        types.Tool(
            name='vhsys_fornecedores_listar',
            description='Lista fornecedores cadastrados no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'search': {'type': 'string', 'description': 'Buscar por razão social'},
                    **_PAGINATION,
                },
                'required': [],
            },
        ),
        types.Tool(
            name='vhsys_fornecedores_obter',
            description='Obtém detalhes de um fornecedor pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_fornecedores_criar',
            description='Cria novo fornecedor no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'razao_social': {'type': 'string', 'description': 'Razão social'},
                    'cnpj_cpf': {'type': 'string', 'description': 'CNPJ ou CPF'},
                    'email': {'type': 'string', 'description': 'E-mail'},
                    'telefone': {'type': 'string', 'description': 'Telefone'},
                },
                'required': ['razao_social'],
            },
        ),
        types.Tool(
            name='vhsys_fornecedores_atualizar',
            description='Atualiza dados de um fornecedor no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do fornecedor'},
                    'razao_social': {'type': 'string', 'description': 'Razão social'},
                    'cnpj_cpf': {'type': 'string', 'description': 'CNPJ ou CPF'},
                    'email': {'type': 'string', 'description': 'E-mail'},
                },
                'required': ['id'],
            },
        ),
        types.Tool(
            name='vhsys_fornecedores_excluir',
            description='Exclui fornecedor pelo ID',
            inputSchema=_ID_REQUIRED,
        ),

        # ── Produtos ─────────────────────────────────────────────────────
        types.Tool(
            name='vhsys_produtos_listar',
            description='Lista produtos cadastrados no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'search': {'type': 'string', 'description': 'Buscar por descrição'},
                    **_PAGINATION,
                },
                'required': [],
            },
        ),
        types.Tool(
            name='vhsys_produtos_obter',
            description='Obtém detalhes de um produto pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_produtos_criar',
            description='Cria novo produto no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'descricao': {'type': 'string', 'description': 'Descrição do produto'},
                    'preco_venda': {'type': 'number', 'description': 'Preço de venda'},
                    'preco_custo': {'type': 'number', 'description': 'Preço de custo'},
                    'unidade': {'type': 'string', 'description': 'Unidade (UN, KG, etc)'},
                    'ncm': {'type': 'string', 'description': 'Código NCM'},
                    'estoque': {'type': 'number', 'description': 'Quantidade em estoque'},
                },
                'required': ['descricao'],
            },
        ),
        types.Tool(
            name='vhsys_produtos_atualizar',
            description='Atualiza dados de um produto no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do produto'},
                    'descricao': {'type': 'string', 'description': 'Descrição'},
                    'preco_venda': {'type': 'number', 'description': 'Preço de venda'},
                    'preco_custo': {'type': 'number', 'description': 'Preço de custo'},
                    'estoque': {'type': 'number', 'description': 'Quantidade em estoque'},
                },
                'required': ['id'],
            },
        ),
        types.Tool(
            name='vhsys_produtos_excluir',
            description='Exclui produto pelo ID',
            inputSchema=_ID_REQUIRED,
        ),

        # ── Pedidos de Venda ─────────────────────────────────────────────
        types.Tool(
            name='vhsys_pedidos_venda_listar',
            description='Lista pedidos de venda do VHSys',
            inputSchema={
                'type': 'object',
                'properties': {**_DATE_RANGE, **_PAGINATION},
                'required': [],
            },
        ),
        types.Tool(
            name='vhsys_pedidos_venda_obter',
            description='Obtém detalhes de um pedido de venda pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_pedidos_venda_criar',
            description='Cria novo pedido de venda no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id_cliente': {'type': 'string', 'description': 'ID do cliente'},
                    'itens': {'type': 'array', 'description': 'Lista de itens [{id_produto, quantidade, valor_unitario}]',
                              'items': {'type': 'object'}},
                    'observacao': {'type': 'string', 'description': 'Observação'},
                },
                'required': ['id_cliente', 'itens'],
            },
        ),
        types.Tool(
            name='vhsys_pedidos_venda_atualizar',
            description='Atualiza pedido de venda no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id': {'type': 'string', 'description': 'ID do pedido'},
                    'observacao': {'type': 'string', 'description': 'Observação'},
                    'situacao': {'type': 'string', 'description': 'Situação do pedido'},
                },
                'required': ['id'],
            },
        ),
        types.Tool(
            name='vhsys_pedidos_venda_excluir',
            description='Exclui pedido de venda pelo ID',
            inputSchema=_ID_REQUIRED,
        ),

        # ── Pedidos de Compra ────────────────────────────────────────────
        types.Tool(
            name='vhsys_pedidos_compra_listar',
            description='Lista pedidos de compra do VHSys',
            inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []},
        ),
        types.Tool(
            name='vhsys_pedidos_compra_obter',
            description='Obtém detalhes de um pedido de compra pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_pedidos_compra_criar',
            description='Cria novo pedido de compra no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id_fornecedor': {'type': 'string', 'description': 'ID do fornecedor'},
                    'itens': {'type': 'array', 'description': 'Lista de itens [{id_produto, quantidade, valor_unitario}]',
                              'items': {'type': 'object'}},
                    'observacao': {'type': 'string', 'description': 'Observação'},
                },
                'required': ['id_fornecedor', 'itens'],
            },
        ),

        # ── Notas Fiscais ────────────────────────────────────────────────
        types.Tool(
            name='vhsys_notas_fiscais_listar',
            description='Lista notas fiscais emitidas no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {**_DATE_RANGE, **_PAGINATION},
                'required': [],
            },
        ),
        types.Tool(
            name='vhsys_notas_fiscais_obter',
            description='Obtém detalhes de uma nota fiscal pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_notas_fiscais_emitir',
            description='Emite nova nota fiscal no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id_pedido_venda': {'type': 'string', 'description': 'ID do pedido de venda para gerar NF-e'},
                    'natureza_operacao': {'type': 'string', 'description': 'Natureza da operação'},
                },
                'required': ['id_pedido_venda'],
            },
        ),

        # ── Categorias Financeiras ───────────────────────────────────────
        types.Tool(
            name='vhsys_categorias_financeiras_listar',
            description='Lista categorias financeiras do VHSys',
            inputSchema=_EMPTY,
        ),
        types.Tool(
            name='vhsys_categorias_financeiras_criar',
            description='Cria nova categoria financeira no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'descricao': {'type': 'string', 'description': 'Descrição da categoria'},
                    'tipo': {'type': 'string', 'description': 'Tipo: receita ou despesa'},
                },
                'required': ['descricao'],
            },
        ),

        # ── Centros de Custo ─────────────────────────────────────────────
        types.Tool(
            name='vhsys_centros_custo_listar',
            description='Lista centros de custo do VHSys',
            inputSchema=_EMPTY,
        ),
        types.Tool(
            name='vhsys_centros_custo_criar',
            description='Cria novo centro de custo no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'descricao': {'type': 'string', 'description': 'Descrição do centro de custo'},
                },
                'required': ['descricao'],
            },
        ),

        # ── Transportadoras ──────────────────────────────────────────────
        types.Tool(
            name='vhsys_transportadoras_listar',
            description='Lista transportadoras cadastradas no VHSys',
            inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []},
        ),
        types.Tool(
            name='vhsys_transportadoras_obter',
            description='Obtém detalhes de uma transportadora pelo ID',
            inputSchema=_ID_REQUIRED,
        ),

        # ── Vendedores ───────────────────────────────────────────────────
        types.Tool(
            name='vhsys_vendedores_listar',
            description='Lista vendedores cadastrados no VHSys',
            inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []},
        ),
        types.Tool(
            name='vhsys_vendedores_obter',
            description='Obtém detalhes de um vendedor pelo ID',
            inputSchema=_ID_REQUIRED,
        ),

        # ── Orçamentos ───────────────────────────────────────────────────
        types.Tool(
            name='vhsys_orcamentos_listar',
            description='Lista orçamentos do VHSys',
            inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []},
        ),
        types.Tool(
            name='vhsys_orcamentos_obter',
            description='Obtém detalhes de um orçamento pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_orcamentos_criar',
            description='Cria novo orçamento no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id_cliente': {'type': 'string', 'description': 'ID do cliente'},
                    'itens': {'type': 'array', 'description': 'Lista de itens [{id_produto, quantidade, valor_unitario}]',
                              'items': {'type': 'object'}},
                    'validade': {'type': 'string', 'description': 'Data de validade (YYYY-MM-DD)'},
                    'observacao': {'type': 'string', 'description': 'Observação'},
                },
                'required': ['id_cliente', 'itens'],
            },
        ),

        # ── Ordens de Serviço ────────────────────────────────────────────
        types.Tool(
            name='vhsys_ordens_servico_listar',
            description='Lista ordens de serviço do VHSys',
            inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []},
        ),
        types.Tool(
            name='vhsys_ordens_servico_obter',
            description='Obtém detalhes de uma ordem de serviço pelo ID',
            inputSchema=_ID_REQUIRED,
        ),
        types.Tool(
            name='vhsys_ordens_servico_criar',
            description='Cria nova ordem de serviço no VHSys',
            inputSchema={
                'type': 'object',
                'properties': {
                    'id_cliente': {'type': 'string', 'description': 'ID do cliente'},
                    'descricao': {'type': 'string', 'description': 'Descrição do serviço'},
                    'valor': {'type': 'number', 'description': 'Valor do serviço'},
                    'data_previsao': {'type': 'string', 'description': 'Data prevista (YYYY-MM-DD)'},
                },
                'required': ['id_cliente', 'descricao'],
            },
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
        # ── Financeiro existente ─────────────────────────────────────────
        case 'vhsys_saldo':
            return c.get_balance()
        case 'vhsys_titulos_pagar':
            return c.list_payables(
                from_date=args.get('from_date'), to_date=args.get('to_date'),
                limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_titulos_receber':
            return c.list_receivables(
                from_date=args.get('from_date'), to_date=args.get('to_date'),
                limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_pagar_obter':
            return c.get_payable(args['id'])
        case 'vhsys_receber_obter':
            return c.get_receivable(args['id'])
        case 'vhsys_pagar_titulo':
            return c.pay_payable(args['id'])
        case 'vhsys_receber_titulo':
            return c.mark_received(args['id'])
        case 'vhsys_criar_pagar':
            return c.create_payable(
                amount=args['amount'], due_date=args['due_date'],
                supplier=args['supplier'], category=args.get('category', ''),
                description=args.get('description', ''))
        case 'vhsys_criar_receber':
            return c.create_receivable(
                amount=args['amount'], due_date=args['due_date'],
                customer=args['customer'], category=args.get('category', ''),
                description=args.get('description', ''))
        case 'vhsys_excluir_pagar':
            return c.delete_payable(args['id'])
        case 'vhsys_excluir_receber':
            return c.delete_receivable(args['id'])
        case 'vhsys_empresa':
            return c.company_info()

        # ── Contas Bancárias ─────────────────────────────────────────────
        case 'vhsys_contas_bancarias_listar':
            return c.list_bank_accounts(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_contas_bancarias_obter':
            return c.get_bank_account(args['id'])

        # ── Clientes ─────────────────────────────────────────────────────
        case 'vhsys_clientes_listar':
            return c.list_customers(limit=args.get('limit', 50), page=args.get('page', 1),
                                    search=args.get('search'))
        case 'vhsys_clientes_obter':
            return c.get_customer(args['id'])
        case 'vhsys_clientes_criar':
            data = {k: v for k, v in args.items() if v is not None}
            return c.create_customer(data)
        case 'vhsys_clientes_atualizar':
            id = args.pop('id')
            return c.update_customer(id, args)
        case 'vhsys_clientes_excluir':
            return c.delete_customer(args['id'])

        # ── Fornecedores ─────────────────────────────────────────────────
        case 'vhsys_fornecedores_listar':
            return c.list_suppliers(limit=args.get('limit', 50), page=args.get('page', 1),
                                    search=args.get('search'))
        case 'vhsys_fornecedores_obter':
            return c.get_supplier(args['id'])
        case 'vhsys_fornecedores_criar':
            data = {k: v for k, v in args.items() if v is not None}
            return c.create_supplier(data)
        case 'vhsys_fornecedores_atualizar':
            id = args.pop('id')
            return c.update_supplier(id, args)
        case 'vhsys_fornecedores_excluir':
            return c.delete_supplier(args['id'])

        # ── Produtos ─────────────────────────────────────────────────────
        case 'vhsys_produtos_listar':
            return c.list_products(limit=args.get('limit', 50), page=args.get('page', 1),
                                   search=args.get('search'))
        case 'vhsys_produtos_obter':
            return c.get_product(args['id'])
        case 'vhsys_produtos_criar':
            data = {k: v for k, v in args.items() if v is not None}
            return c.create_product(data)
        case 'vhsys_produtos_atualizar':
            id = args.pop('id')
            return c.update_product(id, args)
        case 'vhsys_produtos_excluir':
            return c.delete_product(args['id'])

        # ── Pedidos de Venda ─────────────────────────────────────────────
        case 'vhsys_pedidos_venda_listar':
            return c.list_sales_orders(
                limit=args.get('limit', 50), page=args.get('page', 1),
                from_date=args.get('from_date'), to_date=args.get('to_date'))
        case 'vhsys_pedidos_venda_obter':
            return c.get_sales_order(args['id'])
        case 'vhsys_pedidos_venda_criar':
            return c.create_sales_order(args)
        case 'vhsys_pedidos_venda_atualizar':
            id = args.pop('id')
            return c.update_sales_order(id, args)
        case 'vhsys_pedidos_venda_excluir':
            return c.delete_sales_order(args['id'])

        # ── Pedidos de Compra ────────────────────────────────────────────
        case 'vhsys_pedidos_compra_listar':
            return c.list_purchase_orders(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_pedidos_compra_obter':
            return c.get_purchase_order(args['id'])
        case 'vhsys_pedidos_compra_criar':
            return c.create_purchase_order(args)

        # ── Notas Fiscais ────────────────────────────────────────────────
        case 'vhsys_notas_fiscais_listar':
            return c.list_invoices(
                limit=args.get('limit', 50), page=args.get('page', 1),
                from_date=args.get('from_date'), to_date=args.get('to_date'))
        case 'vhsys_notas_fiscais_obter':
            return c.get_invoice(args['id'])
        case 'vhsys_notas_fiscais_emitir':
            return c.emit_invoice(args)

        # ── Categorias Financeiras ───────────────────────────────────────
        case 'vhsys_categorias_financeiras_listar':
            return c.list_financial_categories()
        case 'vhsys_categorias_financeiras_criar':
            return c.create_financial_category(args)

        # ── Centros de Custo ─────────────────────────────────────────────
        case 'vhsys_centros_custo_listar':
            return c.list_cost_centers()
        case 'vhsys_centros_custo_criar':
            return c.create_cost_center(args)

        # ── Transportadoras ──────────────────────────────────────────────
        case 'vhsys_transportadoras_listar':
            return c.list_carriers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_transportadoras_obter':
            return c.get_carrier(args['id'])

        # ── Vendedores ───────────────────────────────────────────────────
        case 'vhsys_vendedores_listar':
            return c.list_sellers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_vendedores_obter':
            return c.get_seller(args['id'])

        # ── Orçamentos ───────────────────────────────────────────────────
        case 'vhsys_orcamentos_listar':
            return c.list_quotes(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_orcamentos_obter':
            return c.get_quote(args['id'])
        case 'vhsys_orcamentos_criar':
            return c.create_quote(args)

        # ── Ordens de Serviço ────────────────────────────────────────────
        case 'vhsys_ordens_servico_listar':
            return c.list_service_orders(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'vhsys_ordens_servico_obter':
            return c.get_service_order(args['id'])
        case 'vhsys_ordens_servico_criar':
            return c.create_service_order(args)

        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
