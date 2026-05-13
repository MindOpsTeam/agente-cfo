#!/usr/bin/env python3
"""
MCP server para Bling — 116 tools.
Endpoints cobertos: saldo, contas a pagar/receber, produtos, pedidos de venda/compra,
NF-e, NFC-e, NFS-e, contatos, fornecedores, estoque, categorias, formas de pagamento,
contas correntes, servicos, logisticas, depositos, webhooks, vendedores, naturezas de
operacao, borderos, transferencias, contratos, propostas, ordens de producao, notas de
compra, campos customizados, situacoes, formatos, homologacoes, tributacoes, unidades
de medida.
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
        types.Tool(name='bling_empresa_detalhar', description='Detalhes completos da empresa no Bling', inputSchema=_empty()),
        # ── Contatos extras ────────────────────────────────────────────
        types.Tool(name='bling_excluir_contato', description='Exclui um contato do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do contato'}}, ['id'])),
        # ── Produtos extras ────────────────────────────────────────────
        types.Tool(name='bling_produtos_situacoes', description='Lista situacoes de produto no Bling', inputSchema=_empty()),
        # ── Pedidos extras ─────────────────────────────────────────────
        types.Tool(name='bling_atualizar_pedido', description='Atualiza pedido de venda existente no Bling',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do pedido'},
                'body': {'type': 'object', 'description': 'Corpo da atualizacao conforme API Bling v3'},
            }, ['id', 'body'])),
        types.Tool(name='bling_excluir_pedido', description='Exclui pedido de venda do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do pedido'}}, ['id'])),
        types.Tool(name='bling_pedidos_venda_situacoes', description='Lista situacoes de pedidos de venda', inputSchema=_empty()),
        # ── NF-e extras ────────────────────────────────────────────────
        types.Tool(name='bling_cancelar_nfe', description='Cancela uma NF-e no Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NF-e'}}, ['id'])),
        types.Tool(name='bling_nfe_xml', description='Obtem XML de uma NF-e',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NF-e'}}, ['id'])),
        # ── NFC-e extras ───────────────────────────────────────────────
        types.Tool(name='bling_criar_nfce', description='Cria uma NFC-e no Bling (corpo livre)',
            inputSchema=_schema({'body': {'type': 'object', 'description': 'Corpo da NFC-e conforme API Bling v3'}}, ['body'])),
        types.Tool(name='bling_transmitir_nfce', description='Transmite uma NFC-e para SEFAZ',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NFC-e'}}, ['id'])),
        types.Tool(name='bling_cancelar_nfce', description='Cancela uma NFC-e',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NFC-e'}}, ['id'])),
        # ── Contas pagar extras ────────────────────────────────────────
        types.Tool(name='bling_atualizar_pagar', description='Atualiza titulo a pagar existente',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do titulo'},
                'body': {'type': 'object', 'description': 'Corpo da atualizacao'},
            }, ['id', 'body'])),
        types.Tool(name='bling_estornar_pagar', description='Estorna baixa de conta a pagar',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo'}}, ['id'])),
        # ── Contas receber extras ──────────────────────────────────────
        types.Tool(name='bling_atualizar_receber', description='Atualiza titulo a receber existente',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do titulo'},
                'body': {'type': 'object', 'description': 'Corpo da atualizacao'},
            }, ['id', 'body'])),
        types.Tool(name='bling_estornar_receber', description='Estorna baixa de conta a receber',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do titulo'}}, ['id'])),
        # ── Contas correntes extras ────────────────────────────────────
        types.Tool(name='bling_contas_correntes_detalhar', description='Detalha uma conta corrente pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da conta corrente'}}, ['id'])),
        types.Tool(name='bling_contas_correntes_saldo', description='Saldo de uma conta corrente especifica',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da conta corrente'}}, ['id'])),
        # ── Fornecedores ───────────────────────────────────────────────
        types.Tool(name='bling_fornecedores_listar', description='Lista fornecedores cadastrados no Bling',
            inputSchema=_schema({
                'nome': {'type': 'string', 'description': 'Filtrar por nome'},
                **_PAGINATED,
            })),
        types.Tool(name='bling_fornecedores_detalhar', description='Detalha um fornecedor pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do fornecedor'}}, ['id'])),
        types.Tool(name='bling_fornecedores_criar', description='Cria um novo fornecedor no Bling',
            inputSchema=_schema({
                'nome': {'type': 'string', 'description': 'Nome do fornecedor'},
                'tipoPessoa': {'type': 'string', 'description': 'F=fisica, J=juridica', 'default': 'J'},
                'numeroDocumento': {'type': 'string', 'description': 'CPF ou CNPJ'},
                'email': {'type': 'string', 'description': 'Email'},
                'telefone': {'type': 'string', 'description': 'Telefone'},
            }, ['nome'])),
        types.Tool(name='bling_fornecedores_atualizar', description='Atualiza um fornecedor existente',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do fornecedor'},
                'nome': {'type': 'string', 'description': 'Nome'},
                'email': {'type': 'string', 'description': 'Email'},
                'telefone': {'type': 'string', 'description': 'Telefone'},
            }, ['id'])),
        # ── Categorias financeiras ─────────────────────────────────────
        types.Tool(name='bling_categorias_financeiras', description='Lista categorias de receitas e despesas',
            inputSchema=_schema({**_PAGINATED})),
        # ── Situacoes ──────────────────────────────────────────────────
        types.Tool(name='bling_situacoes_modulos', description='Lista situacoes por modulo do Bling',
            inputSchema=_schema({'module': {'type': 'string', 'description': 'Nome do modulo (ex: vendas, compras)'}})),
        # ── Campos customizados ────────────────────────────────────────
        types.Tool(name='bling_campos_customizados', description='Lista campos customizados por modulo',
            inputSchema=_schema({'module': {'type': 'string', 'description': 'Nome do modulo'}})),
        # ── Depositos ──────────────────────────────────────────────────
        types.Tool(name='bling_depositos_listar', description='Lista depositos/armazens cadastrados no Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_depositos_detalhar', description='Detalha um deposito pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do deposito'}}, ['id'])),
        # ── Servicos ───────────────────────────────────────────────────
        types.Tool(name='bling_servicos_listar', description='Lista servicos cadastrados no Bling',
            inputSchema=_schema({
                'nome': {'type': 'string', 'description': 'Filtrar por nome'},
                **_PAGINATED,
            })),
        types.Tool(name='bling_servicos_detalhar', description='Detalha um servico pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do servico'}}, ['id'])),
        types.Tool(name='bling_servicos_criar', description='Cria um novo servico no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo do servico conforme API Bling v3'},
            }, ['body'])),
        # ── Logisticas ─────────────────────────────────────────────────
        types.Tool(name='bling_logisticas_listar', description='Lista logisticas cadastradas no Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_logisticas_detalhar', description='Detalha uma logistica pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da logistica'}}, ['id'])),
        # ── Pedidos de compra ──────────────────────────────────────────
        types.Tool(name='bling_pedidos_compra_listar', description='Lista pedidos de compra do Bling',
            inputSchema=_schema({**_DATE_RANGE, **_PAGINATED})),
        types.Tool(name='bling_pedidos_compra_detalhar', description='Detalha um pedido de compra pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do pedido de compra'}}, ['id'])),
        types.Tool(name='bling_pedidos_compra_criar', description='Cria um pedido de compra no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo do pedido de compra conforme API Bling v3'},
            }, ['body'])),
        # ── Formatos ───────────────────────────────────────────────────
        types.Tool(name='bling_formatos_listar', description='Lista formatos de produto no Bling',
            inputSchema=_schema({**_PAGINATED})),
        # ── Webhooks ───────────────────────────────────────────────────
        types.Tool(name='bling_webhooks_listar', description='Lista webhooks (callbacks) cadastrados no Bling', inputSchema=_empty()),
        types.Tool(name='bling_webhooks_criar', description='Cria um webhook (callback) no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo do webhook conforme API Bling v3'},
            }, ['body'])),
        types.Tool(name='bling_webhooks_excluir', description='Exclui um webhook do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do webhook'}}, ['id'])),
        # ── Estoque extras ─────────────────────────────────────────────
        types.Tool(name='bling_estoque_movimentacoes', description='Lista movimentacoes de estoque',
            inputSchema=_schema({
                'product_id': {'type': 'string', 'description': 'Filtrar por ID do produto'},
                **_PAGINATED,
            })),
        types.Tool(name='bling_estoque_saldos', description='Lista saldos de estoque de todos os produtos',
            inputSchema=_schema({**_PAGINATED})),
        # ── NFS-e ──────────────────────────────────────────────────────
        types.Tool(name='bling_nfse_listar', description='Lista notas fiscais de servico (NFS-e)',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_nfse_detalhar', description='Detalha uma NFS-e pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NFS-e'}}, ['id'])),
        types.Tool(name='bling_nfse_criar', description='Cria uma NFS-e no Bling (corpo livre)',
            inputSchema=_schema({'body': {'type': 'object', 'description': 'Corpo da NFS-e conforme API Bling v3'}}, ['body'])),
        types.Tool(name='bling_nfse_transmitir', description='Transmite uma NFS-e para prefeitura',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NFS-e'}}, ['id'])),
        types.Tool(name='bling_nfse_cancelar', description='Cancela uma NFS-e',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da NFS-e'}}, ['id'])),
        # ── Vendedores ─────────────────────────────────────────────────
        types.Tool(name='bling_vendedores_listar', description='Lista vendedores cadastrados no Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_vendedores_detalhar', description='Detalha um vendedor pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do vendedor'}}, ['id'])),
        types.Tool(name='bling_vendedores_criar', description='Cria um novo vendedor no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo do vendedor conforme API Bling v3'},
            }, ['body'])),
        # ── Natureza de operacao ───────────────────────────────────────
        types.Tool(name='bling_naturezas_operacao_listar', description='Lista naturezas de operacao',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_naturezas_operacao_detalhar', description='Detalha uma natureza de operacao pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da natureza de operacao'}}, ['id'])),
        types.Tool(name='bling_naturezas_operacao_criar', description='Cria uma natureza de operacao no Bling',
            inputSchema=_schema({'body': {'type': 'object', 'description': 'Corpo da natureza de operacao conforme API Bling v3'}}, ['body'])),
        types.Tool(name='bling_naturezas_operacao_atualizar', description='Atualiza uma natureza de operacao existente',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID da natureza de operacao'},
                'body': {'type': 'object', 'description': 'Corpo da atualizacao'},
            }, ['id', 'body'])),
        types.Tool(name='bling_naturezas_operacao_excluir', description='Exclui uma natureza de operacao do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da natureza de operacao'}}, ['id'])),
        # ── Formas de recebimento ──────────────────────────────────────
        types.Tool(name='bling_formas_recebimento_listar', description='Lista formas de recebimento',
            inputSchema=_schema({**_PAGINATED})),
        # ── Borderos ───────────────────────────────────────────────────
        types.Tool(name='bling_borderos_listar', description='Lista borderos do Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_borderos_detalhar', description='Detalha um bordero pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do bordero'}}, ['id'])),
        # ── Transferencias ─────────────────────────────────────────────
        types.Tool(name='bling_transferencias_listar', description='Lista transferencias entre contas',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_transferencias_criar', description='Cria transferencia entre contas no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo da transferencia conforme API Bling v3'},
            }, ['body'])),
        # ── Homologacao ────────────────────────────────────────────────
        types.Tool(name='bling_homologacao_listar', description='Lista homologacoes do Bling',
            inputSchema=_schema({**_PAGINATED})),
        # ── Contratos ──────────────────────────────────────────────────
        types.Tool(name='bling_contratos_listar', description='Lista contratos cadastrados no Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_contratos_detalhar', description='Detalha um contrato pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do contrato'}}, ['id'])),
        types.Tool(name='bling_contratos_criar', description='Cria um contrato no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo do contrato conforme API Bling v3'},
            }, ['body'])),
        types.Tool(name='bling_contratos_atualizar', description='Atualiza um contrato existente no Bling',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do contrato'},
                'body': {'type': 'object', 'description': 'Corpo da atualizacao'},
            }, ['id', 'body'])),
        types.Tool(name='bling_contratos_excluir', description='Exclui um contrato do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do contrato'}}, ['id'])),
        # ── Propostas comerciais ───────────────────────────────────────
        types.Tool(name='bling_propostas_listar', description='Lista propostas comerciais do Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_propostas_detalhar', description='Detalha uma proposta comercial pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da proposta'}}, ['id'])),
        types.Tool(name='bling_propostas_criar', description='Cria uma proposta comercial no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo da proposta conforme API Bling v3'},
            }, ['body'])),
        # ── Ordem de producao ──────────────────────────────────────────
        types.Tool(name='bling_ordens_producao_listar', description='Lista ordens de producao do Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_ordens_producao_detalhar', description='Detalha uma ordem de producao pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da ordem de producao'}}, ['id'])),
        types.Tool(name='bling_ordens_producao_criar', description='Cria uma ordem de producao no Bling',
            inputSchema=_schema({
                'body': {'type': 'object', 'description': 'Corpo da ordem de producao conforme API Bling v3'},
            }, ['body'])),
        # ── Notas de compra ────────────────────────────────────────────
        types.Tool(name='bling_notas_compra_listar', description='Lista notas de compra do Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_notas_compra_detalhar', description='Detalha uma nota de compra pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da nota de compra'}}, ['id'])),
        # ── Tributacoes ────────────────────────────────────────────────
        types.Tool(name='bling_tributacoes_listar', description='Lista tributacoes cadastradas no Bling',
            inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='bling_tributacoes_detalhar', description='Detalha uma tributacao pelo ID',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID da tributacao'}}, ['id'])),
        # ── Unidades de medida ─────────────────────────────────────────
        types.Tool(name='bling_unidades_medida_listar', description='Lista unidades de medida cadastradas no Bling',
            inputSchema=_schema({})),
        # ── Fornecedores excluir ───────────────────────────────────────
        types.Tool(name='bling_fornecedores_excluir', description='Exclui um fornecedor do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do fornecedor'}}, ['id'])),
        # ── Vendedores extras ──────────────────────────────────────────
        types.Tool(name='bling_vendedores_atualizar', description='Atualiza um vendedor existente no Bling',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do vendedor'},
                'body': {'type': 'object', 'description': 'Corpo da atualizacao'},
            }, ['id', 'body'])),
        types.Tool(name='bling_vendedores_excluir', description='Exclui um vendedor do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do vendedor'}}, ['id'])),
        # ── Depositos extras ───────────────────────────────────────────
        types.Tool(name='bling_depositos_criar', description='Cria um deposito/armazem no Bling',
            inputSchema=_schema({'body': {'type': 'object', 'description': 'Corpo do deposito conforme API Bling v3'}}, ['body'])),
        types.Tool(name='bling_depositos_atualizar', description='Atualiza um deposito/armazem existente',
            inputSchema=_schema({
                'id': {'type': 'string', 'description': 'ID do deposito'},
                'body': {'type': 'object', 'description': 'Corpo da atualizacao'},
            }, ['id', 'body'])),
        types.Tool(name='bling_depositos_excluir', description='Exclui um deposito/armazem do Bling',
            inputSchema=_schema({'id': {'type': 'string', 'description': 'ID do deposito'}}, ['id'])),
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
        case 'bling_empresa_detalhar':
            return c.get_company_detail()
        # ── Contatos extras ────────────────────────────────────────
        case 'bling_excluir_contato':
            return c.delete_contact(args['id'])
        # ── Produtos extras ────────────────────────────────────────
        case 'bling_produtos_situacoes':
            return c.list_product_situations()
        # ── Pedidos extras ─────────────────────────────────────────
        case 'bling_atualizar_pedido':
            return c.update_sales_order(args['id'], args['body'])
        case 'bling_excluir_pedido':
            return c.delete_sales_order(args['id'])
        case 'bling_pedidos_venda_situacoes':
            return c.list_sales_order_situations()
        # ── NF-e extras ────────────────────────────────────────────
        case 'bling_cancelar_nfe':
            return c.cancel_nfe(args['id'])
        case 'bling_nfe_xml':
            return c.get_nfe_xml(args['id'])
        # ── NFC-e extras ───────────────────────────────────────────
        case 'bling_criar_nfce':
            return c.create_nfce(args['body'])
        case 'bling_transmitir_nfce':
            return c.transmit_nfce(args['id'])
        case 'bling_cancelar_nfce':
            return c.cancel_nfce(args['id'])
        # ── Contas pagar extras ────────────────────────────────────
        case 'bling_atualizar_pagar':
            return c.update_payable(args['id'], args['body'])
        case 'bling_estornar_pagar':
            return c.reverse_payable(args['id'])
        # ── Contas receber extras ──────────────────────────────────
        case 'bling_atualizar_receber':
            return c.update_receivable(args['id'], args['body'])
        case 'bling_estornar_receber':
            return c.reverse_receivable(args['id'])
        # ── Contas correntes extras ────────────────────────────────
        case 'bling_contas_correntes_detalhar':
            return c.get_bank_account(args['id'])
        case 'bling_contas_correntes_saldo':
            return c.get_bank_account_balance(args['id'])
        # ── Fornecedores ───────────────────────────────────────────
        case 'bling_fornecedores_listar':
            return c.list_suppliers(page=args.get('page', 1), limit=args.get('limit', 100), nome=args.get('nome'))
        case 'bling_fornecedores_detalhar':
            return c.get_supplier(args['id'])
        case 'bling_fornecedores_criar':
            body = {'nome': args['nome'], 'tipo': 'F'}
            for k in ('tipoPessoa', 'numeroDocumento', 'email', 'telefone'):
                if args.get(k): body[k] = args[k]
            return c.create_supplier(body)
        case 'bling_fornecedores_atualizar':
            body = {}
            for k in ('nome', 'email', 'telefone'):
                if args.get(k): body[k] = args[k]
            return c.update_supplier(args['id'], body)
        # ── Categorias financeiras ─────────────────────────────────
        case 'bling_categorias_financeiras':
            return c.list_financial_categories(page=args.get('page', 1), limit=args.get('limit', 100))
        # ── Situacoes ──────────────────────────────────────────────
        case 'bling_situacoes_modulos':
            return c.list_module_situations(module=args.get('module', ''))
        # ── Campos customizados ────────────────────────────────────
        case 'bling_campos_customizados':
            return c.list_custom_fields(module=args.get('module', ''))
        # ── Depositos ──────────────────────────────────────────────
        case 'bling_depositos_listar':
            return c.list_warehouses(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_depositos_detalhar':
            return c.get_warehouse(args['id'])
        # ── Servicos ───────────────────────────────────────────────
        case 'bling_servicos_listar':
            return c.list_services(page=args.get('page', 1), limit=args.get('limit', 100), nome=args.get('nome'))
        case 'bling_servicos_detalhar':
            return c.get_service(args['id'])
        case 'bling_servicos_criar':
            return c.create_service(args['body'])
        # ── Logisticas ─────────────────────────────────────────────
        case 'bling_logisticas_listar':
            return c.list_logistics(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_logisticas_detalhar':
            return c.get_logistics(args['id'])
        # ── Pedidos de compra ──────────────────────────────────────
        case 'bling_pedidos_compra_listar':
            return c.list_purchase_orders(
                page=args.get('page', 1), limit=args.get('limit', 100),
                from_date=args.get('from_date'), to_date=args.get('to_date'))
        case 'bling_pedidos_compra_detalhar':
            return c.get_purchase_order(args['id'])
        case 'bling_pedidos_compra_criar':
            return c.create_purchase_order(args['body'])
        # ── Formatos ───────────────────────────────────────────────
        case 'bling_formatos_listar':
            return c.list_formats(page=args.get('page', 1), limit=args.get('limit', 100))
        # ── Webhooks ───────────────────────────────────────────────
        case 'bling_webhooks_listar':
            return c.list_webhooks()
        case 'bling_webhooks_criar':
            return c.create_webhook(args['body'])
        case 'bling_webhooks_excluir':
            return c.delete_webhook(args['id'])
        # ── Estoque extras ─────────────────────────────────────────
        case 'bling_estoque_movimentacoes':
            return c.list_stock_movements(
                page=args.get('page', 1), limit=args.get('limit', 100),
                product_id=args.get('product_id'))
        case 'bling_estoque_saldos':
            return c.list_stock_balances(page=args.get('page', 1), limit=args.get('limit', 100))
        # ── NFS-e ──────────────────────────────────────────────────
        case 'bling_nfse_listar':
            return c.list_nfse(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_nfse_detalhar':
            return c.get_nfse(args['id'])
        case 'bling_nfse_criar':
            return c.create_nfse(args['body'])
        case 'bling_nfse_transmitir':
            return c.transmit_nfse(args['id'])
        case 'bling_nfse_cancelar':
            return c.cancel_nfse(args['id'])
        # ── Vendedores ─────────────────────────────────────────────
        case 'bling_vendedores_listar':
            return c.list_sellers(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_vendedores_detalhar':
            return c.get_seller(args['id'])
        case 'bling_vendedores_criar':
            return c.create_seller(args['body'])
        # ── Natureza de operacao ───────────────────────────────────
        case 'bling_naturezas_operacao_listar':
            return c.list_nature_operations(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_naturezas_operacao_detalhar':
            return c._get(f"naturezas-de-operacao/{args['id']}")
        case 'bling_naturezas_operacao_criar':
            return c._post_json("naturezas-de-operacao", args['body'])
        case 'bling_naturezas_operacao_atualizar':
            return c._put(f"naturezas-de-operacao/{args['id']}", args['body'])
        case 'bling_naturezas_operacao_excluir':
            return c._delete(f"naturezas-de-operacao/{args['id']}")
        # ── Formas de recebimento ──────────────────────────────────
        case 'bling_formas_recebimento_listar':
            return c.list_receipt_methods(page=args.get('page', 1), limit=args.get('limit', 100))
        # ── Borderos ───────────────────────────────────────────────
        case 'bling_borderos_listar':
            return c.list_borderos(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_borderos_detalhar':
            return c.get_bordero(args['id'])
        # ── Transferencias ─────────────────────────────────────────
        case 'bling_transferencias_listar':
            return c.list_transfers(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_transferencias_criar':
            return c.create_transfer(args['body'])
        # ── Homologacao ────────────────────────────────────────────
        case 'bling_homologacao_listar':
            return c.list_homologations(page=args.get('page', 1), limit=args.get('limit', 100))
        # ── Contratos ──────────────────────────────────────────────
        case 'bling_contratos_listar':
            return c.list_contracts(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_contratos_detalhar':
            return c.get_contract(args['id'])
        case 'bling_contratos_criar':
            return c.create_contract(args['body'])
        case 'bling_contratos_atualizar':
            return c._put(f"contratos/{args['id']}", args['body'])
        case 'bling_contratos_excluir':
            return c._delete(f"contratos/{args['id']}")
        # ── Propostas comerciais ───────────────────────────────────
        case 'bling_propostas_listar':
            return c.list_proposals(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_propostas_detalhar':
            return c.get_proposal(args['id'])
        case 'bling_propostas_criar':
            return c.create_proposal(args['body'])
        # ── Ordem de producao ──────────────────────────────────────
        case 'bling_ordens_producao_listar':
            return c.list_production_orders(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_ordens_producao_detalhar':
            return c.get_production_order(args['id'])
        case 'bling_ordens_producao_criar':
            return c.create_production_order(args['body'])
        # ── Notas de compra ────────────────────────────────────────
        case 'bling_notas_compra_listar':
            return c.list_purchase_notes(page=args.get('page', 1), limit=args.get('limit', 100))
        case 'bling_notas_compra_detalhar':
            return c.get_purchase_note(args['id'])
        # ── Tributacoes ────────────────────────────────────────────
        case 'bling_tributacoes_listar':
            return c._get(f"tributacoes?pagina={args.get('page', 1)}&limite={args.get('limit', 100)}")
        case 'bling_tributacoes_detalhar':
            return c._get(f"tributacoes/{args['id']}")
        # ── Unidades de medida ─────────────────────────────────────
        case 'bling_unidades_medida_listar':
            return c._get("unidades")
        # ── Fornecedores excluir ───────────────────────────────────
        case 'bling_fornecedores_excluir':
            return c._delete(f"contatos/{args['id']}")
        # ── Vendedores extras ──────────────────────────────────────
        case 'bling_vendedores_atualizar':
            return c._put(f"vendedores/{args['id']}", args['body'])
        case 'bling_vendedores_excluir':
            return c._delete(f"vendedores/{args['id']}")
        # ── Depositos extras ───────────────────────────────────────
        case 'bling_depositos_criar':
            return c._post_json("depositos", args['body'])
        case 'bling_depositos_atualizar':
            return c._put(f"depositos/{args['id']}", args['body'])
        case 'bling_depositos_excluir':
            return c._delete(f"depositos/{args['id']}")
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
