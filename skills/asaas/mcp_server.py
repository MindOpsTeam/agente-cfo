#!/usr/bin/env python3
"""
MCP server para Asaas — 38 tools.
Endpoints cobertos: cobranças, clientes, assinaturas, notificações, split,
antecipação, transferências, extrato, webhooks, subcontas, PIX, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from asaas_client import AsaasClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('asaas')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = AsaasClient()
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
        # ── Cobranças ────────────────────────────────────────────────────
        types.Tool(name='asaas_cobrancas_listar', description='Lista cobranças/faturas do Asaas (paginado)',
                   inputSchema={'type': 'object', 'properties': {
                       'status': {'type': 'string', 'description': 'Filtro (open, paid, overdue)', 'default': 'open'},
                       'customer_id': {'type': 'string', 'description': 'ID do cliente'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='asaas_cobranca_detalhar', description='Detalhes de uma cobrança do Asaas', inputSchema=_ID_REQUIRED),
        types.Tool(name='asaas_cobranca_criar', description='Cria nova cobrança no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'customer_id': {'type': 'string', 'description': 'ID do cliente'},
                       'amount': {'type': 'number', 'description': 'Valor em BRL'},
                       'due_date': {'type': 'string', 'description': 'Vencimento (YYYY-MM-DD)'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                       'billingType': {'type': 'string', 'description': 'BOLETO, PIX, CREDIT_CARD ou UNDEFINED'},
                   }, 'required': ['customer_id', 'amount', 'due_date']}),
        types.Tool(name='asaas_cobranca_cancelar', description='Cancela cobrança no Asaas', inputSchema=_ID_REQUIRED),
        types.Tool(name='asaas_cobranca_baixa_manual', description='Marca cobrança como paga manualmente', inputSchema=_ID_REQUIRED),
        types.Tool(name='asaas_enviar_link', description='Envia link de pagamento via email/WhatsApp',
                   inputSchema={'type': 'object', 'properties': {
                       'invoice_id': {'type': 'string', 'description': 'ID da cobrança'},
                       'channel': {'type': 'string', 'description': 'Canal (whatsapp, email)', 'default': 'whatsapp'},
                       'custom_message': {'type': 'string', 'description': 'Mensagem personalizada'},
                   }, 'required': ['invoice_id']}),
        types.Tool(name='asaas_meios_pagamento', description='Meios de pagamento disponíveis no Asaas', inputSchema=_EMPTY),
        types.Tool(name='asaas_pix_qrcode', description='Obtém QR Code PIX de uma cobrança',
                   inputSchema={'type': 'object', 'properties': {
                       'payment_id': {'type': 'string', 'description': 'ID da cobrança/pagamento'},
                   }, 'required': ['payment_id']}),

        # ── Clientes ─────────────────────────────────────────────────────
        types.Tool(name='asaas_clientes_listar', description='Lista clientes do Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'search': {'type': 'string', 'description': 'Buscar por nome'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='asaas_cliente_detalhar', description='Detalhes de um cliente do Asaas', inputSchema=_ID_REQUIRED),
        types.Tool(name='asaas_cliente_criar', description='Cria novo cliente no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome do cliente'},
                       'cpfCnpj': {'type': 'string', 'description': 'CPF ou CNPJ'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'mobilePhone': {'type': 'string', 'description': 'Celular'},
                   }, 'required': ['name', 'cpfCnpj']}),
        types.Tool(name='asaas_cliente_atualizar', description='Atualiza cliente no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID do cliente'},
                       'name': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                   }, 'required': ['id']}),
        types.Tool(name='asaas_cliente_excluir', description='Exclui cliente pelo ID', inputSchema=_ID_REQUIRED),

        # ── Assinaturas ──────────────────────────────────────────────────
        types.Tool(name='asaas_assinaturas_listar', description='Lista assinaturas do Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'customer_id': {'type': 'string', 'description': 'Filtrar por cliente'},
                       **_PAGINATION,
                   }, 'required': []}),
        types.Tool(name='asaas_assinatura_detalhar', description='Detalhes de uma assinatura', inputSchema=_ID_REQUIRED),
        types.Tool(name='asaas_assinatura_criar', description='Cria nova assinatura no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'customer': {'type': 'string', 'description': 'ID do cliente'},
                       'billingType': {'type': 'string', 'description': 'BOLETO, PIX, CREDIT_CARD ou UNDEFINED'},
                       'value': {'type': 'number', 'description': 'Valor em BRL'},
                       'cycle': {'type': 'string', 'description': 'MONTHLY, WEEKLY, BIWEEKLY, QUARTERLY, SEMIANNUALLY, YEARLY'},
                       'nextDueDate': {'type': 'string', 'description': 'Próximo vencimento (YYYY-MM-DD)'},
                       'description': {'type': 'string', 'description': 'Descrição'},
                   }, 'required': ['customer', 'billingType', 'value', 'cycle', 'nextDueDate']}),
        types.Tool(name='asaas_assinatura_atualizar', description='Atualiza assinatura no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'id': {'type': 'string', 'description': 'ID da assinatura'},
                       'value': {'type': 'number', 'description': 'Valor'},
                       'cycle': {'type': 'string', 'description': 'Ciclo'},
                   }, 'required': ['id']}),
        types.Tool(name='asaas_assinatura_excluir', description='Cancela/exclui assinatura pelo ID', inputSchema=_ID_REQUIRED),

        # ── Notificações ─────────────────────────────────────────────────
        types.Tool(name='asaas_notificacoes_listar', description='Lista notificações de um cliente Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'customer_id': {'type': 'string', 'description': 'ID do cliente'},
                   }, 'required': ['customer_id']}),
        types.Tool(name='asaas_notificacao_atualizar', description='Atualiza configuração de notificação',
                   inputSchema={'type': 'object', 'properties': {
                       'notification_id': {'type': 'string', 'description': 'ID da notificação'},
                       'enabled': {'type': 'boolean', 'description': 'Ativar/desativar'},
                   }, 'required': ['notification_id']}),

        # ── Split ────────────────────────────────────────────────────────
        types.Tool(name='asaas_split_listar', description='Lista splits de um pagamento',
                   inputSchema={'type': 'object', 'properties': {
                       'payment_id': {'type': 'string', 'description': 'ID do pagamento'},
                   }, 'required': ['payment_id']}),

        # ── Antecipação ──────────────────────────────────────────────────
        types.Tool(name='asaas_antecipacoes_listar', description='Lista antecipações solicitadas',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='asaas_antecipacao_solicitar', description='Solicita antecipação de recebíveis no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'payment': {'type': 'string', 'description': 'ID do pagamento'},
                       'installment': {'type': 'string', 'description': 'ID do parcelamento (opcional)'},
                   }, 'required': ['payment']}),

        # ── Transferências ───────────────────────────────────────────────
        types.Tool(name='asaas_transferencias_listar', description='Lista transferências do Asaas',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='asaas_transferencia_criar', description='Cria transferência bancária/PIX no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'value': {'type': 'number', 'description': 'Valor em BRL'},
                       'bankAccount': {'type': 'object', 'description': 'Dados bancários destino'},
                       'operationType': {'type': 'string', 'description': 'PIX ou TED'},
                   }, 'required': ['value', 'operationType']}),

        # ── Extrato ──────────────────────────────────────────────────────
        types.Tool(name='asaas_extrato', description='Extrato financeiro do Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'from_date': {'type': 'string', 'description': 'Data início (YYYY-MM-DD)'},
                       'to_date': {'type': 'string', 'description': 'Data fim (YYYY-MM-DD)'},
                   }, 'required': []}),

        # ── Webhooks ─────────────────────────────────────────────────────
        types.Tool(name='asaas_webhooks_listar', description='Lista webhooks configurados no Asaas', inputSchema=_EMPTY),
        types.Tool(name='asaas_webhook_criar', description='Cria webhook no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'url': {'type': 'string', 'description': 'URL do webhook'},
                       'email': {'type': 'string', 'description': 'E-mail de notificação'},
                       'enabled': {'type': 'boolean', 'description': 'Ativo', 'default': True},
                   }, 'required': ['url', 'email']}),

        # ── Subcontas ────────────────────────────────────────────────────
        types.Tool(name='asaas_subcontas_listar', description='Lista subcontas do Asaas',
                   inputSchema={'type': 'object', 'properties': {**_PAGINATION}, 'required': []}),
        types.Tool(name='asaas_subconta_criar', description='Cria nova subconta no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'name': {'type': 'string', 'description': 'Nome'},
                       'email': {'type': 'string', 'description': 'E-mail'},
                       'cpfCnpj': {'type': 'string', 'description': 'CPF ou CNPJ'},
                   }, 'required': ['name', 'email', 'cpfCnpj']}),

        # ── PIX ──────────────────────────────────────────────────────────
        types.Tool(name='asaas_pix_chaves_listar', description='Lista chaves PIX cadastradas no Asaas', inputSchema=_EMPTY),
        types.Tool(name='asaas_pix_chave_criar', description='Cria nova chave PIX no Asaas',
                   inputSchema={'type': 'object', 'properties': {
                       'type': {'type': 'string', 'description': 'Tipo: CPF, CNPJ, EMAIL, PHONE, EVP'},
                   }, 'required': ['type']}),

        # ── Empresa ──────────────────────────────────────────────────────
        types.Tool(name='asaas_empresa', description='Informações da empresa/conta conectada ao Asaas', inputSchema=_EMPTY),
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
        case 'asaas_cobrancas_listar':
            return c.list_invoices(status=args.get('status', 'open'), customer_id=args.get('customer_id'),
                                   limit=args.get('limit', 50), page=args.get('page', 1))
        case 'asaas_cobranca_detalhar': return c.get_invoice(args['id'])
        case 'asaas_cobranca_criar':
            return c.create_invoice(customer_id=args['customer_id'], amount=args['amount'],
                                    due_date=args['due_date'], description=args.get('description', ''))
        case 'asaas_cobranca_cancelar': return c.cancel_invoice(args['id'])
        case 'asaas_cobranca_baixa_manual': return c.mark_invoice_paid_manually(args['id'])
        case 'asaas_enviar_link':
            return c.send_payment_link(invoice_id=args['invoice_id'], channel=args.get('channel', 'whatsapp'),
                                       custom_message=args.get('custom_message'))
        case 'asaas_meios_pagamento': return c.get_payment_methods()
        case 'asaas_pix_qrcode': return c.get_pix_qrcode(args['payment_id'])
        # Clientes
        case 'asaas_clientes_listar':
            return c.list_customers(limit=args.get('limit', 50), page=args.get('page', 1), search=args.get('search'))
        case 'asaas_cliente_detalhar': return c.get_customer(args['id'])
        case 'asaas_cliente_criar': return c.create_customer(args)
        case 'asaas_cliente_atualizar':
            id = args.pop('id'); return c.update_customer(id, args)
        case 'asaas_cliente_excluir': return c.delete_customer(args['id'])
        # Assinaturas
        case 'asaas_assinaturas_listar':
            return c.list_subscriptions(limit=args.get('limit', 50), page=args.get('page', 1),
                                        customer_id=args.get('customer_id'))
        case 'asaas_assinatura_detalhar': return c.get_subscription(args['id'])
        case 'asaas_assinatura_criar': return c.create_subscription(args)
        case 'asaas_assinatura_atualizar':
            id = args.pop('id'); return c.update_subscription(id, args)
        case 'asaas_assinatura_excluir': return c.delete_subscription(args['id'])
        # Notificações
        case 'asaas_notificacoes_listar': return c.list_notifications(args['customer_id'])
        case 'asaas_notificacao_atualizar': return c.update_notification(args['notification_id'], args)
        # Split
        case 'asaas_split_listar': return c.list_payment_splits(args['payment_id'])
        # Antecipação
        case 'asaas_antecipacoes_listar': return c.list_anticipations(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'asaas_antecipacao_solicitar': return c.request_anticipation(args)
        # Transferências
        case 'asaas_transferencias_listar': return c.list_transfers(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'asaas_transferencia_criar': return c.create_transfer(args)
        # Extrato
        case 'asaas_extrato': return c.get_financial_statement(from_date=args.get('from_date'), to_date=args.get('to_date'))
        # Webhooks
        case 'asaas_webhooks_listar': return c.list_webhooks()
        case 'asaas_webhook_criar': return c.create_webhook(args)
        # Subcontas
        case 'asaas_subcontas_listar': return c.list_subaccounts(limit=args.get('limit', 50), page=args.get('page', 1))
        case 'asaas_subconta_criar': return c.create_subaccount(args)
        # PIX
        case 'asaas_pix_chaves_listar': return c.list_pix_keys()
        case 'asaas_pix_chave_criar': return c.create_pix_key(args)
        # Empresa
        case 'asaas_empresa': return c.company_info()
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
