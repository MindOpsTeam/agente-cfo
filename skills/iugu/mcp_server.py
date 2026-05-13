#!/usr/bin/env python3
"""
MCP server para Iugu — 36 tools.
Endpoints cobertos: cobranças, clientes, planos, assinaturas, transferências,
extrato, webhooks, marketplace, meios de pagamento, empresa.
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

_PAGINATION = {
    'limit': {'type': 'integer', 'description': 'Limite por página (default 50)', 'default': 50},
    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
}
_ID_REQUIRED = {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'ID do registro'}}, 'required': ['id']}
_EMPTY = {'type': 'object', 'properties': {}, 'required': []}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Cobranças/Faturas ────────────────────────────────────────────
        types.Tool(name='iugu_cobrancas_listar', description='Lista cobranças/faturas do Iugu (paginado)',
                   inputSchema={'type': 'object', 'properties': {
                       'status': {'type': 'string', 'description': 'Filtro de status (open, paid, overdue)', 'default': 'open'},
                       'customer_id': {'type': 'string', 'description': 'ID do cliente para filtrar'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='iugu_cobranca_detalhar', description='Retorna detalhes de uma cobrança/fatura do Iugu', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_cobranca_criar', description='Cria nova cobrança/fatura no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'customer_id': {'type': 'string', 'description': 'ID do cliente'},
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Data de vencimento (YYYY-MM-DD)'},
                       'description': {'type': 'string', 'description': 'Descrição da cobrança'},
                   }, 'required': ['customer_id', 'amount', 'due_date']}),
        types.Tool(name='iugu_cobranca_cancelar', description='Cancela uma cobrança/fatura no Iugu', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_cobranca_baixa_manual', description='Marca cobrança como paga manualmente no Iugu', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_enviar_link', description='Envia link de pagamento da cobrança via WhatsApp/email',
                   inputSchema={'type': 'object', 'properties': {
                       'invoice_id': {'type': 'string', 'description': 'ID da cobrança/fatura'},
                       'channel': {'type': 'string', 'description': 'Canal de envio (whatsapp, email)', 'default': 'whatsapp'},
                       'custom_message': {'type': 'string', 'description': 'Mensagem personalizada'},
                   }, 'required': ['invoice_id']}),
        types.Tool(name='iugu_meios_pagamento', description='Lista meios de pagamento disponíveis no Iugu', inputSchema=_EMPTY),

        # ── Clientes ─────────────────────────────────────────────────────
        types.Tool(name='iugu_clientes_listar', description='Lista clientes cadastrados no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por nome/email'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='iugu_cliente_detalhar', description='Retorna dados de um cliente do Iugu', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_cliente_criar', description='Cria novo cliente no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do cliente'},
                       'email': {'type': 'string', 'description': 'E-mail do cliente'},
                       'cpf_cnpj': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'phone': {'type': 'string', 'description': 'Telefone'},
                   }, 'required': ['name', 'email']}),
        types.Tool(name='iugu_cliente_atualizar', description='Atualiza dados de um cliente no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do cliente'},
                       'name': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                   }, 'required': ['id']}),
        types.Tool(name='iugu_cliente_excluir', description='Exclui cliente pelo ID', inputSchema=_ID_REQUIRED),

        # ── Planos ───────────────────────────────────────────────────────
        types.Tool(name='iugu_planos_listar', description='Lista planos cadastrados no Iugu',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='iugu_plano_detalhar', description='Obtém detalhes de um plano pelo ID', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_plano_criar', description='Cria novo plano no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do plano'},
                       'identifier': {'type': 'string', 'description': 'Identificador único do plano'},
                       'interval': {'type': 'integer', 'description': 'Intervalo em meses (1=mensal, 12=anual)'},
                       'interval_type': {'type': 'string', 'description': 'Tipo: months ou weeks'},
                       'value_cents': {'type': 'integer', 'description': 'Valor em centavos'},
                   }, 'required': ['name', 'identifier', 'value_cents']}),
        types.Tool(name='iugu_plano_atualizar', description='Atualiza plano no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do plano'},
                       'name': {'type': 'string', 'description': 'Nome'},
                       'value_cents': {'type': 'integer', 'description': 'Valor em centavos'},
                   }, 'required': ['id']}),
        types.Tool(name='iugu_plano_excluir', description='Exclui plano pelo ID', inputSchema=_ID_REQUIRED),

        # ── Assinaturas ──────────────────────────────────────────────────
        types.Tool(name='iugu_assinaturas_listar', description='Lista assinaturas do Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'customer_id': {'type': 'string', 'description': 'Filtrar por cliente'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='iugu_assinatura_detalhar', description='Obtém detalhes de uma assinatura', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_assinatura_criar', description='Cria nova assinatura no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'customer_id': {'type': 'string', 'description': 'ID do cliente'},
                       'plan_identifier': {'type': 'string', 'description': 'Identificador do plano'},
                   }, 'required': ['customer_id', 'plan_identifier']}),
        types.Tool(name='iugu_assinatura_atualizar', description='Atualiza assinatura no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID da assinatura'},
                       'plan_identifier': {'type': 'string', 'description': 'Novo identificador de plano'},
                   }, 'required': ['id']}),
        types.Tool(name='iugu_assinatura_suspender', description='Suspende uma assinatura no Iugu', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_assinatura_ativar', description='Ativa/reativa uma assinatura suspensa no Iugu', inputSchema=_ID_REQUIRED),
        types.Tool(name='iugu_assinatura_excluir', description='Exclui/cancela assinatura pelo ID', inputSchema=_ID_REQUIRED),

        # ── Transferências ───────────────────────────────────────────────
        types.Tool(name='iugu_transferencias_listar', description='Lista transferências do Iugu',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='iugu_transferencia_criar', description='Cria nova transferência no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'receiver_id': {'type': 'string', 'description': 'ID da conta destino'},
                       'amount_cents': {'type': 'integer', 'description': 'Valor em centavos'},
                   }, 'required': ['receiver_id', 'amount_cents']}),

        # ── Extrato ──────────────────────────────────────────────────────
        types.Tool(name='iugu_extrato', description='Obtém extrato financeiro da conta Iugu', inputSchema=_EMPTY),

        # ── Webhooks ─────────────────────────────────────────────────────
        types.Tool(name='iugu_webhooks_listar', description='Lista webhooks configurados no Iugu', inputSchema=_EMPTY),
        types.Tool(name='iugu_webhook_criar', description='Cria novo webhook no Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'url': {'type': 'string', 'description': 'URL do webhook'},
                       'event': {'type': 'string', 'description': 'Evento (ex: invoice.status_changed, all)'},
                   }, 'required': ['url', 'event']}),
        types.Tool(name='iugu_webhook_excluir', description='Exclui webhook pelo ID', inputSchema=_ID_REQUIRED),

        # ── Marketplace ──────────────────────────────────────────────────
        types.Tool(name='iugu_marketplace_listar', description='Lista subcontas do marketplace Iugu',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='iugu_marketplace_criar', description='Cria nova subconta no marketplace Iugu',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome da subconta'},
                       'commission_percent': {'type': 'number', 'description': 'Percentual de comissão'},
                   }, 'required': ['name']}),

        # ── Empresa ──────────────────────────────────────────────────────
        types.Tool(name='iugu_empresa', description='Informações da empresa/conta conectada ao Iugu', inputSchema=_EMPTY),
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
        # Cobranças
        case 'iugu_cobrancas_listar':
            return c.list_invoices(status=args.get('status', 'open'), customer_id=args.get('customer_id'),
                                   limit=args.get('limit', 50), page=args.get('page', 1))
        case 'iugu_cobranca_detalhar': return c.get_invoice(args['id'])
        case 'iugu_cobranca_criar':
            return c.create_invoice(customer_id=args['customer_id'], amount=args['amount'],
                                    due_date=args['due_date'], description=args.get('description', ''))
        case 'iugu_cobranca_cancelar': return c.cancel_invoice(args['id'])
        case 'iugu_cobranca_baixa_manual': return c.mark_invoice_paid_manually(args['id'])
        case 'iugu_enviar_link':
            return c.send_payment_link(invoice_id=args['invoice_id'], channel=args.get('channel', 'whatsapp'),
                                       custom_message=args.get('custom_message'))
        case 'iugu_meios_pagamento': return c.get_payment_methods()
        # Clientes
        case 'iugu_clientes_listar':
            return c.list_customers(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search'))
        case 'iugu_cliente_detalhar': return c.get_customer(args['id'])
        case 'iugu_cliente_criar': return c.create_customer(args)
        case 'iugu_cliente_atualizar':
            id = args.pop('id'); return c.update_customer(id, args)
        case 'iugu_cliente_excluir': return c.delete_customer(args['id'])
        # Planos
        case 'iugu_planos_listar': return c.list_plans(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'iugu_plano_detalhar': return c.get_plan(args['id'])
        case 'iugu_plano_criar': return c.create_plan(args)
        case 'iugu_plano_atualizar':
            id = args.pop('id'); return c.update_plan(id, args)
        case 'iugu_plano_excluir': return c.delete_plan(args['id'])
        # Assinaturas
        case 'iugu_assinaturas_listar':
            return c.list_subscriptions(limit=args.get('limit', 50), page=args.get('page', 1),
                                        customer_id=args.get('customer_id'))
        case 'iugu_assinatura_detalhar': return c.get_subscription(args['id'])
        case 'iugu_assinatura_criar': return c.create_subscription(args)
        case 'iugu_assinatura_atualizar':
            id = args.pop('id'); return c.update_subscription(id, args)
        case 'iugu_assinatura_suspender': return c.suspend_subscription(args['id'])
        case 'iugu_assinatura_ativar': return c.activate_subscription(args['id'])
        case 'iugu_assinatura_excluir': return c.delete_subscription(args['id'])
        # Transferências
        case 'iugu_transferencias_listar': return c.list_transfers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'iugu_transferencia_criar': return c.create_transfer(args)
        # Extrato
        case 'iugu_extrato': return c.get_financial_statement()
        # Webhooks
        case 'iugu_webhooks_listar': return c.list_webhooks()
        case 'iugu_webhook_criar': return c.create_webhook(args)
        case 'iugu_webhook_excluir': return c.delete_webhook(args['id'])
        # Marketplace
        case 'iugu_marketplace_listar': return c.list_marketplace_accounts(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'iugu_marketplace_criar': return c.create_marketplace_account(args)
        # Empresa
        case 'iugu_empresa': return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
