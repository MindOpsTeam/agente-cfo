#!/usr/bin/env python3
"""
MCP server para Mercado Livre — 30 tools.
Endpoints cobertos: pedidos, produtos/publicações, perguntas/respostas,
mensagens, categorias, envios, vendedor, devoluções, campanhas, visitas.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from mercado_livre_client import MercadoLivreClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('mercado_livre')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = MercadoLivreClient()
    return _client

_ID = {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'ID'}}, 'required': ['id']}
_E = {'type': 'object', 'properties': {}, 'required': []}

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Pedidos ──────────────────────────────────────────────────────
        types.Tool(name='mercado_livre_pedidos_listar', description='Lista pedidos do Mercado Livre',
                   inputSchema={'type':'object','properties':{
                       'status':{'type':'string','default':'paid'},'limit':{'type':'integer','default':50},
                       'since':{'type':'string','description':'Data início (YYYY-MM-DD)'},
                   },'required':[]}),
        types.Tool(name='mercado_livre_pedido_detalhar', description='Detalhes de um pedido', inputSchema=_ID),
        types.Tool(name='mercado_livre_pedido_enviar', description='Marca pedido como enviado',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'tracking_code':{'type':'string'}},'required':['id']}),
        types.Tool(name='mercado_livre_pedido_cancelar', description='Cancela um pedido',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'reason':{'type':'string'}},'required':['id']}),

        # ── Produtos/Publicações ─────────────────────────────────────────
        types.Tool(name='mercado_livre_produtos_listar', description='Lista produtos/publicações do Mercado Livre',
                   inputSchema={'type':'object','properties':{'limit':{'type':'integer','default':50},'in_stock_only':{'type':'boolean','default':False}},'required':[]}),
        types.Tool(name='mercado_livre_produto_detalhar', description='Detalhes de um produto', inputSchema=_ID),
        types.Tool(name='mercado_livre_produto_criar', description='Cria nova publicação no Mercado Livre',
                   inputSchema={'type':'object','properties':{
                       'title':{'type':'string','description':'Título da publicação'},
                       'category_id':{'type':'string','description':'ID da categoria ML'},
                       'price':{'type':'number','description':'Preço'},
                       'available_quantity':{'type':'integer','description':'Quantidade'},
                       'condition':{'type':'string','description':'new ou used'},
                       'listing_type_id':{'type':'string','description':'gold_special, gold_pro, etc'},
                   },'required':['title','category_id','price','available_quantity']}),
        types.Tool(name='mercado_livre_produto_atualizar', description='Atualiza publicação no Mercado Livre',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'title':{'type':'string'},'price':{'type':'number'},'available_quantity':{'type':'integer'}},'required':['id']}),
        types.Tool(name='mercado_livre_produto_excluir', description='Exclui/encerra publicação', inputSchema=_ID),
        types.Tool(name='mercado_livre_estoque_atualizar', description='Atualiza estoque de um produto',
                   inputSchema={'type':'object','properties':{'product_id':{'type':'string'},'new_qty':{'type':'integer'}},'required':['product_id','new_qty']}),
        types.Tool(name='mercado_livre_preco_atualizar', description='Atualiza preço de um produto',
                   inputSchema={'type':'object','properties':{'product_id':{'type':'string'},'new_price':{'type':'number'}},'required':['product_id','new_price']}),
        types.Tool(name='mercado_livre_descricao_obter', description='Obtém descrição de um produto', inputSchema=_ID),
        types.Tool(name='mercado_livre_descricao_atualizar', description='Atualiza descrição de um produto',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'text':{'type':'string','description':'Novo texto'}},'required':['id','text']}),
        types.Tool(name='mercado_livre_visitas_obter', description='Obtém visitas/acessos de uma publicação',
                   inputSchema={'type':'object','properties':{'item_id':{'type':'string'},'from_date':{'type':'string'},'to_date':{'type':'string'}},'required':['item_id']}),

        # ── Perguntas/Respostas ──────────────────────────────────────────
        types.Tool(name='mercado_livre_perguntas_listar', description='Lista perguntas recebidas no ML',
                   inputSchema={'type':'object','properties':{
                       'item_id':{'type':'string','description':'Filtrar por publicação'},
                       'status':{'type':'string','description':'unanswered, answered','default':'unanswered'},
                       'limit':{'type':'integer','default':50},
                   },'required':[]}),
        types.Tool(name='mercado_livre_pergunta_obter', description='Obtém pergunta pelo ID', inputSchema=_ID),
        types.Tool(name='mercado_livre_pergunta_responder', description='Responde uma pergunta no ML',
                   inputSchema={'type':'object','properties':{'question_id':{'type':'string'},'text':{'type':'string'}},'required':['question_id','text']}),

        # ── Mensagens ────────────────────────────────────────────────────
        types.Tool(name='mercado_livre_mensagens_listar', description='Lista mensagens de um pedido',
                   inputSchema={'type':'object','properties':{'order_id':{'type':'string'}},'required':['order_id']}),
        types.Tool(name='mercado_livre_mensagem_enviar', description='Envia mensagem ao comprador de um pedido',
                   inputSchema={'type':'object','properties':{'order_id':{'type':'string'},'text':{'type':'string'}},'required':['order_id','text']}),

        # ── Categorias ───────────────────────────────────────────────────
        types.Tool(name='mercado_livre_categorias_listar', description='Lista categorias raiz do ML Brasil', inputSchema=_E),
        types.Tool(name='mercado_livre_categoria_obter', description='Obtém detalhes de uma categoria', inputSchema=_ID),

        # ── Envios ───────────────────────────────────────────────────────
        types.Tool(name='mercado_livre_envio_obter', description='Obtém detalhes de um envio pelo ID',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'}},'required':['id']}),
        types.Tool(name='mercado_livre_envio_itens', description='Lista itens de um envio',
                   inputSchema={'type':'object','properties':{'shipment_id':{'type':'string'}},'required':['shipment_id']}),

        # ── Vendedor ─────────────────────────────────────────────────────
        types.Tool(name='mercado_livre_reputacao', description='Reputação e dados do vendedor', inputSchema=_E),

        # ── Devoluções/Claims ────────────────────────────────────────────
        types.Tool(name='mercado_livre_reclamacoes_listar', description='Lista reclamações/devoluções',
                   inputSchema={'type':'object','properties':{'limit':{'type':'integer','default':50}},'required':[]}),

        # ── Campanhas/Anúncios ───────────────────────────────────────────
        types.Tool(name='mercado_livre_campanhas_listar', description='Lista campanhas de anúncios do ML', inputSchema=_E),

        # ── Empresa ──────────────────────────────────────────────────────
        types.Tool(name='mercado_livre_empresa', description='Info da loja conectada ao Mercado Livre', inputSchema=_E),
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
        case 'mercado_livre_pedidos_listar':
            return c.list_orders(status=args.get('status','paid'), limit=args.get('limit',50), since=args.get('since'))
        case 'mercado_livre_pedido_detalhar': return c.get_order(args['id'])
        case 'mercado_livre_pedido_enviar': return c.mark_order_shipped(args['id'], tracking_code=args.get('tracking_code',''))
        case 'mercado_livre_pedido_cancelar': return c.cancel_order(args['id'], reason=args.get('reason',''))
        case 'mercado_livre_produtos_listar':
            return c.list_products(limit=args.get('limit',50), in_stock_only=args.get('in_stock_only',False))
        case 'mercado_livre_produto_detalhar': return c.get_product(args['id'])
        case 'mercado_livre_produto_criar': return c.create_product(args)
        case 'mercado_livre_produto_atualizar': id=args.pop('id'); return c.update_product(id, args)
        case 'mercado_livre_produto_excluir': return c.delete_product(args['id'])
        case 'mercado_livre_estoque_atualizar': return c.update_stock(args['product_id'], args['new_qty'])
        case 'mercado_livre_preco_atualizar': return c.update_price(args['product_id'], args['new_price'])
        case 'mercado_livre_descricao_obter': return c.get_product_description(args['id'])
        case 'mercado_livre_descricao_atualizar': return c.update_product_description(args['id'], args['text'])
        case 'mercado_livre_visitas_obter':
            return c.get_item_visits(args['item_id'], from_date=args.get('from_date'), to_date=args.get('to_date'))
        case 'mercado_livre_perguntas_listar':
            return c.list_questions(item_id=args.get('item_id'), status=args.get('status','unanswered'), limit=args.get('limit',50))
        case 'mercado_livre_pergunta_obter': return c.get_question(args['id'])
        case 'mercado_livre_pergunta_responder': return c.answer_question(args['question_id'], args['text'])
        case 'mercado_livre_mensagens_listar': return c.list_messages(args['order_id'])
        case 'mercado_livre_mensagem_enviar': return c.send_message(args['order_id'], args['text'])
        case 'mercado_livre_categorias_listar': return c.list_categories()
        case 'mercado_livre_categoria_obter': return c.get_category(args['id'])
        case 'mercado_livre_envio_obter': return c.get_shipment(args['id'])
        case 'mercado_livre_envio_itens': return c.list_shipment_items(args['shipment_id'])
        case 'mercado_livre_reputacao': return c.get_seller_reputation()
        case 'mercado_livre_reclamacoes_listar': return c.list_claims(limit=args.get('limit',50))
        case 'mercado_livre_campanhas_listar': return c.list_campaigns()
        case 'mercado_livre_empresa': return c.company_info()
        case _: raise ValueError(f'Tool desconhecida: {name}')

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
