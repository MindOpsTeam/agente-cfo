#!/usr/bin/env python3
"""
MCP server para Omie ERP — 96 tools.
Endpoints cobertos: clientes, produtos, pedidos, financeiro (pagar/receber),
NF-e, NFS-e, estoque, departamentos, projetos, categorias, contas correntes/bancárias,
centros de custo, tags, lançamentos, fluxo de caixa, ordens de serviço, empresa,
saldo, vencidos, fornecedores, vendedores, transportadoras, serviços,
transferências entre contas, download XML NF-e, pedidos de compra.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
from omie_client import (
    clientes_listar, clientes_buscar, clientes_detalhar,
    clientes_criar, clientes_atualizar, clientes_excluir,
    produtos_listar, produtos_detalhar,
    produtos_criar, produtos_atualizar, produtos_excluir,
    pedidos_listar, pedidos_detalhar, pedidos_status, pedidos_criar,
    pedidos_excluir, pedidos_alterar,
    contas_receber, contas_pagar, resumo_financeiro,
    contas_pagar_detalhar, contas_pagar_incluir, contas_pagar_alterar,
    contas_receber_detalhar, contas_receber_incluir, contas_receber_alterar,
    nfe_listar, nfe_detalhar, nfe_xml, nfe_cancelar,
    nfe_consultar_status, nfe_inutilizar,
    nfse_listar, nfse_detalhar, nfse_cancelar,
    estoque_posicao, estoque_produto,
    departamentos_listar, projetos_listar, categorias_listar,
    categorias_incluir, categorias_alterar, categorias_excluir,
    contas_correntes_listar, tags_listar,
    contas_bancarias_listar, contas_bancarias_incluir, contas_bancarias_alterar,
    contas_bancarias_detalhar, contas_bancarias_excluir,
    centros_custo_listar_v2, centros_custo_incluir, centros_custo_alterar, centros_custo_excluir,
    lancamentos_listar, fluxo_caixa,
    os_listar, os_detalhar, os_incluir, os_alterar,
    fornecedores_listar, fornecedores_detalhar, fornecedores_incluir,
    fornecedores_alterar, fornecedores_excluir,
    vendedores_listar, vendedores_incluir, vendedores_alterar, vendedores_excluir,
    transportadoras_listar, transportadoras_incluir, transportadoras_alterar,
    servicos_listar, servicos_incluir, servicos_alterar, servicos_excluir,
    empresa_consultar, empresa_alterar,
    unified_get_balance, unified_list_payables, unified_list_receivables,
    unified_list_overdue, unified_company_info,
    unified_pay_payable, unified_mark_received,
    unified_create_payable, unified_create_receivable, unified_cancel_payable,
)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

import urllib.request
import urllib.error

_OMIE_BASE = "https://app.omie.com.br/api/v1"

def _omie_rpc(endpoint: str, call: str, param: list) -> dict:
    """Direct Omie RPC call for endpoints not in omie_client."""
    payload = json.dumps({
        "call": call,
        "app_key": os.environ.get("OMIE_APP_KEY", ""),
        "app_secret": os.environ.get("OMIE_APP_SECRET", ""),
        "param": param,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{_OMIE_BASE}/{endpoint}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}", "detail": body}
    except Exception as e:
        return {"error": str(e)}

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
        # ── Novos Sprint 21 ──
        types.Tool(name='omie_clientes_criar', description='Cria novo cliente no Omie',
                   inputSchema={'type':'object','properties':{
                       'razao_social':{'type':'string'},'cnpj_cpf':{'type':'string'},
                       'nome_fantasia':{'type':'string'},'email':{'type':'string'},
                       'telefone1_numero':{'type':'string'},
                   },'required':['razao_social','cnpj_cpf']}),
        types.Tool(name='omie_clientes_atualizar', description='Atualiza cliente no Omie',
                   inputSchema={'type':'object','properties':{
                       'codigo_cliente_omie':{'type':'integer','description':'Código do cliente'},
                       'razao_social':{'type':'string'},'email':{'type':'string'},
                   },'required':['codigo_cliente_omie']}),
        types.Tool(name='omie_produtos_criar', description='Cria novo produto no Omie',
                   inputSchema={'type':'object','properties':{
                       'descricao':{'type':'string'},'valor_unitario':{'type':'number'},
                       'codigo':{'type':'string','description':'Código interno'},
                       'unidade':{'type':'string'},
                   },'required':['descricao']}),
        types.Tool(name='omie_produtos_atualizar', description='Atualiza produto no Omie',
                   inputSchema={'type':'object','properties':{
                       'codigo_produto':{'type':'integer'},'descricao':{'type':'string'},
                       'valor_unitario':{'type':'number'},
                   },'required':['codigo_produto']}),
        types.Tool(name='omie_pedidos_criar', description='Cria novo pedido de venda no Omie',
                   inputSchema={'type':'object','properties':{
                       'codigo_cliente':{'type':'integer','description':'Código do cliente'},
                       'itens':{'type':'array','description':'Lista de itens do pedido'},
                   },'required':['codigo_cliente','itens']}),
        types.Tool(name='omie_departamentos_listar', description='Lista departamentos do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_projetos_listar', description='Lista projetos do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_categorias_listar', description='Lista categorias financeiras do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':50}},'required':[]}),
        types.Tool(name='omie_contas_correntes_listar', description='Lista contas correntes/bancárias do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_tags_listar', description='Lista tags/etiquetas do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':50}},'required':[]}),
        types.Tool(name='omie_lancamentos_listar', description='Lista lançamentos financeiros (extrato) do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_fluxo_caixa', description='Consulta fluxo de caixa do Omie',
                   inputSchema={'type':'object','properties':{
                       'data_inicio':{'type':'string','description':'DD/MM/YYYY'},
                       'data_fim':{'type':'string','description':'DD/MM/YYYY'},
                   },'required':[]}),
        types.Tool(name='omie_nfe_xml', description='Obtém XML de uma NF-e pelo número',
                   inputSchema={'type':'object','properties':{'numero':{'type':'integer'}},'required':['numero']}),
        types.Tool(name='omie_nfe_cancelar', description='Cancela uma NF-e no Omie',
                   inputSchema={'type':'object','properties':{'numero':{'type':'integer'},'motivo':{'type':'string','default':'Cancelamento'}},'required':['numero']}),
        types.Tool(name='omie_os_listar', description='Lista ordens de serviço do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_os_detalhar', description='Obtém detalhes de uma ordem de serviço',
                   inputSchema={'type':'object','properties':{'numero':{'type':'integer'}},'required':['numero']}),
        # ── Fornecedores ──
        types.Tool(name='omie_fornecedores_listar', description='Lista fornecedores cadastrados no Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_fornecedores_detalhar', description='Detalha fornecedor pelo codigo Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do fornecedor'}},'required':['codigo']}),
        types.Tool(name='omie_fornecedores_incluir', description='Inclui fornecedor no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (razao_social, cnpj_cpf obrigatorios)'}},'required':['body']}),
        types.Tool(name='omie_fornecedores_alterar', description='Altera fornecedor no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (codigo_cliente_omie obrigatorio)'}},'required':['body']}),
        types.Tool(name='omie_fornecedores_excluir', description='Exclui fornecedor no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do fornecedor'}},'required':['codigo']}),
        # ── Contas Bancárias extras ──
        types.Tool(name='omie_contas_bancarias_incluir', description='Inclui conta bancaria no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (descricao obrigatorio)'}},'required':['body']}),
        types.Tool(name='omie_contas_bancarias_alterar', description='Altera conta bancaria no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (nCodCC obrigatorio)'}},'required':['body']}),
        types.Tool(name='omie_contas_bancarias_detalhar', description='Detalha conta bancaria pelo codigo',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo da conta corrente (nCodCC)'}},'required':['codigo']}),
        types.Tool(name='omie_contas_bancarias_excluir', description='Exclui conta bancaria no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo da conta corrente (nCodCC)'}},'required':['codigo']}),
        # ── Centros de Custo ──
        types.Tool(name='omie_centros_custo_listar', description='Lista centros de custo do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':50}},'required':[]}),
        types.Tool(name='omie_centros_custo_incluir', description='Inclui centro de custo no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (cCodCCusto, descricao obrigatorios)'}},'required':['body']}),
        types.Tool(name='omie_centros_custo_alterar', description='Altera centro de custo no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (cCodCCusto obrigatorio)'}},'required':['body']}),
        types.Tool(name='omie_centros_custo_excluir', description='Exclui centro de custo no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'string','description':'Codigo do centro de custo (cCodCCusto)'}},'required':['codigo']}),
        # ── Serviços ──
        types.Tool(name='omie_servicos_listar', description='Lista servicos cadastrados no Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_servicos_incluir', description='Inclui servico no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (descricao obrigatorio)'}},'required':['body']}),
        types.Tool(name='omie_servicos_alterar', description='Altera servico no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (codigo_produto obrigatorio)'}},'required':['body']}),
        types.Tool(name='omie_servicos_excluir', description='Exclui servico no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do servico'}},'required':['codigo']}),
        # ── NF-e extras ──
        types.Tool(name='omie_nfe_consultar_status', description='Consulta status de uma NF-e pelo numero',
                   inputSchema={'type':'object','properties':{'numero':{'type':'integer','description':'Numero da NF-e'}},'required':['numero']}),
        types.Tool(name='omie_nfe_inutilizar', description='Inutiliza numeracao de NF-e no Omie',
                   inputSchema={'type':'object','properties':{'numero_inicio':{'type':'integer','description':'Numero inicial'},'numero_fim':{'type':'integer','description':'Numero final'},'motivo':{'type':'string','default':'Inutilizacao'}},'required':['numero_inicio','numero_fim']}),
        # ── Vendedores ──
        types.Tool(name='omie_vendedores_listar', description='Lista vendedores cadastrados no Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_vendedores_incluir', description='Inclui vendedor no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_vendedores_alterar', description='Altera vendedor no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_vendedores_excluir', description='Exclui vendedor no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do vendedor'}},'required':['codigo']}),
        # ── Transportadoras ──
        types.Tool(name='omie_transportadoras_listar', description='Lista transportadoras cadastradas no Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_transportadoras_incluir', description='Inclui transportadora no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_transportadoras_alterar', description='Altera transportadora no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        # ── Categorias extras ──
        types.Tool(name='omie_categorias_incluir', description='Inclui categoria financeira no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_categorias_alterar', description='Altera categoria financeira no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_categorias_excluir', description='Exclui categoria financeira no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'string','description':'Codigo da categoria (cCodCateg)'}},'required':['codigo']}),
        # ── Empresa ──
        types.Tool(name='omie_empresa_consultar', description='Consulta dados da empresa no Omie',
                   inputSchema={'type':'object','properties':{},'required':[]}),
        types.Tool(name='omie_empresa_alterar', description='Altera dados da empresa no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        # ── Clientes excluir ──
        types.Tool(name='omie_clientes_excluir', description='Exclui cliente no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do cliente'}},'required':['codigo']}),
        # ── Produtos excluir ──
        types.Tool(name='omie_produtos_excluir', description='Exclui produto no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do produto'}},'required':['codigo']}),
        # ── Pedidos extras ──
        types.Tool(name='omie_pedidos_excluir', description='Exclui pedido de venda no Omie',
                   inputSchema={'type':'object','properties':{'numero':{'type':'integer','description':'Numero do pedido'}},'required':['numero']}),
        types.Tool(name='omie_pedidos_alterar', description='Altera pedido de venda no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        # ── Contas a pagar extras ──
        types.Tool(name='omie_contas_pagar_detalhar', description='Detalha conta a pagar pelo codigo',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do titulo (nCodTitulo)'}},'required':['codigo']}),
        types.Tool(name='omie_contas_pagar_incluir', description='Inclui conta a pagar nativa no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_contas_pagar_alterar', description='Altera conta a pagar no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        # ── Contas a receber extras ──
        types.Tool(name='omie_contas_receber_detalhar', description='Detalha conta a receber pelo codigo',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo do titulo (nCodTitulo)'}},'required':['codigo']}),
        types.Tool(name='omie_contas_receber_incluir', description='Inclui conta a receber nativa no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_contas_receber_alterar', description='Altera conta a receber no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        # ── NFS-e ──
        types.Tool(name='omie_nfse_listar', description='Lista notas fiscais de servico (NFS-e) do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_nfse_detalhar', description='Detalha NFS-e pelo numero',
                   inputSchema={'type':'object','properties':{'numero':{'type':'integer','description':'Numero da NFS-e'}},'required':['numero']}),
        types.Tool(name='omie_nfse_cancelar', description='Cancela NFS-e no Omie',
                   inputSchema={'type':'object','properties':{'numero':{'type':'integer','description':'Numero da NFS-e'},'motivo':{'type':'string','default':'Cancelamento'}},'required':['numero']}),
        # ── OS extras ──
        types.Tool(name='omie_os_incluir', description='Inclui ordem de servico no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_os_alterar', description='Altera ordem de servico no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        # ── Transferências entre contas ──
        types.Tool(name='omie_transferencia_incluir', description='Inclui transferencia entre contas no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_transferencia_listar', description='Lista transferencias entre contas do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_transferencia_excluir', description='Exclui transferencia entre contas no Omie',
                   inputSchema={'type':'object','properties':{'codigo':{'type':'integer','description':'Codigo da transferencia'}},'required':['codigo']}),
        # ── Tags extras (CRUD) ──
        types.Tool(name='omie_tags_incluir', description='Inclui tag/etiqueta no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_tags_excluir', description='Exclui tag/etiqueta no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (nCodTag ou cTag)'}},'required':['body']}),
        # ── Download XML NF-e ──
        types.Tool(name='omie_nfe_download_xml', description='Faz download do XML completo de uma NF-e',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (nNF, cSerie, etc)'}},'required':['body']}),
        # ── Pedidos de Compra ──
        types.Tool(name='omie_pedido_compra_incluir', description='Inclui pedido de compra no Omie',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie'}},'required':['body']}),
        types.Tool(name='omie_pedido_compra_listar', description='Lista pedidos de compra do Omie',
                   inputSchema={'type':'object','properties':{'pagina':{'type':'integer','default':1},'por_pagina':{'type':'integer','default':20}},'required':[]}),
        types.Tool(name='omie_pedido_compra_detalhar', description='Detalha pedido de compra pelo codigo',
                   inputSchema={'type':'object','properties':{'body':{'type':'object','description':'Corpo da requisicao conforme API Omie (nCodPedido ou cCodIntPedido)'}},'required':['body']}),
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
        # Novos Sprint 21
        case 'omie_clientes_criar': return clientes_criar(args)
        case 'omie_clientes_atualizar': return clientes_atualizar(args)
        case 'omie_produtos_criar': return produtos_criar(args)
        case 'omie_produtos_atualizar': return produtos_atualizar(args)
        case 'omie_pedidos_criar': return pedidos_criar(args)
        case 'omie_departamentos_listar':
            return departamentos_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_projetos_listar':
            return projetos_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_categorias_listar':
            return categorias_listar(args.get('pagina', 1), args.get('por_pagina', 50))
        case 'omie_contas_correntes_listar':
            return contas_correntes_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_tags_listar':
            return tags_listar(args.get('pagina', 1), args.get('por_pagina', 50))
        case 'omie_lancamentos_listar':
            return lancamentos_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_fluxo_caixa':
            return fluxo_caixa(data_inicio=args.get('data_inicio'), data_fim=args.get('data_fim'))
        case 'omie_nfe_xml': return nfe_xml(args['numero'])
        case 'omie_nfe_cancelar': return nfe_cancelar(args['numero'], motivo=args.get('motivo', 'Cancelamento'))
        case 'omie_os_listar':
            return os_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_os_detalhar': return os_detalhar(args['numero'])
        # Fornecedores
        case 'omie_fornecedores_listar':
            return fornecedores_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_fornecedores_detalhar': return fornecedores_detalhar(args['codigo'])
        case 'omie_fornecedores_incluir': return fornecedores_incluir(args['body'])
        case 'omie_fornecedores_alterar': return fornecedores_alterar(args['body'])
        case 'omie_fornecedores_excluir': return fornecedores_excluir(args['codigo'])
        # Contas Bancárias extras
        case 'omie_contas_bancarias_incluir': return contas_bancarias_incluir(args['body'])
        case 'omie_contas_bancarias_alterar': return contas_bancarias_alterar(args['body'])
        case 'omie_contas_bancarias_detalhar': return contas_bancarias_detalhar(args['codigo'])
        case 'omie_contas_bancarias_excluir': return contas_bancarias_excluir(args['codigo'])
        # Centros de Custo
        case 'omie_centros_custo_listar':
            return centros_custo_listar_v2(args.get('pagina', 1), args.get('por_pagina', 50))
        case 'omie_centros_custo_incluir': return centros_custo_incluir(args['body'])
        case 'omie_centros_custo_alterar': return centros_custo_alterar(args['body'])
        case 'omie_centros_custo_excluir': return centros_custo_excluir(args['codigo'])
        # Serviços
        case 'omie_servicos_listar':
            return servicos_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_servicos_incluir': return servicos_incluir(args['body'])
        case 'omie_servicos_alterar': return servicos_alterar(args['body'])
        case 'omie_servicos_excluir': return servicos_excluir(args['codigo'])
        # NF-e extras
        case 'omie_nfe_consultar_status': return nfe_consultar_status(args['numero'])
        case 'omie_nfe_inutilizar':
            return nfe_inutilizar(args['numero_inicio'], args['numero_fim'], motivo=args.get('motivo', 'Inutilizacao'))
        # Vendedores
        case 'omie_vendedores_listar':
            return vendedores_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_vendedores_incluir': return vendedores_incluir(args['body'])
        case 'omie_vendedores_alterar': return vendedores_alterar(args['body'])
        case 'omie_vendedores_excluir': return vendedores_excluir(args['codigo'])
        # Transportadoras
        case 'omie_transportadoras_listar':
            return transportadoras_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_transportadoras_incluir': return transportadoras_incluir(args['body'])
        case 'omie_transportadoras_alterar': return transportadoras_alterar(args['body'])
        # Categorias extras
        case 'omie_categorias_incluir': return categorias_incluir(args['body'])
        case 'omie_categorias_alterar': return categorias_alterar(args['body'])
        case 'omie_categorias_excluir': return categorias_excluir(args['codigo'])
        # Empresa
        case 'omie_empresa_consultar': return empresa_consultar()
        case 'omie_empresa_alterar': return empresa_alterar(args['body'])
        # Clientes excluir
        case 'omie_clientes_excluir': return clientes_excluir(args['codigo'])
        # Produtos excluir
        case 'omie_produtos_excluir': return produtos_excluir(args['codigo'])
        # Pedidos extras
        case 'omie_pedidos_excluir': return pedidos_excluir(args['numero'])
        case 'omie_pedidos_alterar': return pedidos_alterar(args['body'])
        # Contas a pagar extras
        case 'omie_contas_pagar_detalhar': return contas_pagar_detalhar(args['codigo'])
        case 'omie_contas_pagar_incluir': return contas_pagar_incluir(args['body'])
        case 'omie_contas_pagar_alterar': return contas_pagar_alterar(args['body'])
        # Contas a receber extras
        case 'omie_contas_receber_detalhar': return contas_receber_detalhar(args['codigo'])
        case 'omie_contas_receber_incluir': return contas_receber_incluir(args['body'])
        case 'omie_contas_receber_alterar': return contas_receber_alterar(args['body'])
        # NFS-e
        case 'omie_nfse_listar':
            return nfse_listar(args.get('pagina', 1), args.get('por_pagina', 20))
        case 'omie_nfse_detalhar': return nfse_detalhar(args['numero'])
        case 'omie_nfse_cancelar':
            return nfse_cancelar(args['numero'], motivo=args.get('motivo', 'Cancelamento'))
        # OS extras
        case 'omie_os_incluir': return os_incluir(args['body'])
        case 'omie_os_alterar': return os_alterar(args['body'])
        # Transferências entre contas
        case 'omie_transferencia_incluir':
            return _omie_rpc("financas/transferencia/", "IncluirTransferencia", [args['body']])
        case 'omie_transferencia_listar':
            return _omie_rpc("financas/transferencia/", "ListarTransferencias", [
                {"nPagina": args.get('pagina', 1), "nRegPorPagina": args.get('por_pagina', 20)}
            ])
        case 'omie_transferencia_excluir':
            return _omie_rpc("financas/transferencia/", "ExcluirTransferencia", [
                {"nCodTransf": args['codigo']}
            ])
        # Tags extras (CRUD)
        case 'omie_tags_incluir':
            return _omie_rpc("geral/tags/", "IncluirTag", [args['body']])
        case 'omie_tags_excluir':
            return _omie_rpc("geral/tags/", "ExcluirTag", [args['body']])
        # Download XML NF-e
        case 'omie_nfe_download_xml':
            return _omie_rpc("produtos/nfe/", "ObterXmlNFe", [args['body']])
        # Pedidos de Compra
        case 'omie_pedido_compra_incluir':
            return _omie_rpc("estoque/pedido/", "IncluirPedido", [args['body']])
        case 'omie_pedido_compra_listar':
            return _omie_rpc("estoque/pedido/", "ListarPedidos", [
                {"nPagina": args.get('pagina', 1), "nRegPorPagina": args.get('por_pagina', 20)}
            ])
        case 'omie_pedido_compra_detalhar':
            return _omie_rpc("estoque/pedido/", "ConsultarPedido", [args['body']])
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
