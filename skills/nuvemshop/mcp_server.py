#!/usr/bin/env python3
"""
MCP server para Nuvemshop — 35 tools (Sprint 21).
Endpoints cobertos: pedidos, produtos, variantes, categorias, clientes,
cupons, paginas, webhooks, metafields, frete, abandonos, transacoes, imagens, empresa.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from nuvemshop_client import NuvemshopClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('nuvemshop')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = NuvemshopClient()
    return _client


def _tool(name, desc, props, required=None):
    return types.Tool(
        name=name,
        description=desc,
        inputSchema={
            'type': 'object',
            'properties': props,
            'required': required or []
        }
    )


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Pedidos ───────────────────────────────────────────────────────
        _tool('nuvemshop_pedidos_listar',
              'Lista pedidos/orders do Nuvemshop (paginado)',
              {'status': {'type': 'string', 'description': 'Filtro de status (paid, pending, shipped, delivered, cancelled, all)', 'default': 'paid'},
               'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
               'since': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'}}),
        _tool('nuvemshop_pedido_detalhar',
              'Retorna detalhes de um pedido do Nuvemshop',
              {'id': {'type': 'string', 'description': 'ID do pedido'}},
              ['id']),
        _tool('nuvemshop_pedido_atualizar',
              'Atualiza campos de um pedido (nota, owner, shipping_status)',
              {'order_id': {'type': 'string', 'description': 'ID do pedido'},
               'note': {'type': 'string', 'description': 'Nota interna'},
               'owner': {'type': 'string', 'description': 'Responsavel'},
               'shipping_status': {'type': 'string', 'description': 'Status de envio (shipped, delivered, etc)'}},
              ['order_id']),
        _tool('nuvemshop_pedido_enviar',
              'Marca pedido como enviado/shipped no Nuvemshop',
              {'id': {'type': 'string', 'description': 'ID do pedido'},
               'tracking_code': {'type': 'string', 'description': 'Codigo de rastreio'}},
              ['id']),
        _tool('nuvemshop_pedido_cancelar',
              'Cancela um pedido no Nuvemshop',
              {'id': {'type': 'string', 'description': 'ID do pedido'},
               'reason': {'type': 'string', 'description': 'Motivo do cancelamento'}},
              ['id']),

        # ── Produtos ──────────────────────────────────────────────────────
        _tool('nuvemshop_produtos_listar',
              'Lista produtos do Nuvemshop (paginado)',
              {'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
               'in_stock_only': {'type': 'boolean', 'description': 'Apenas com estoque', 'default': False}}),
        _tool('nuvemshop_produto_detalhar',
              'Retorna detalhes de um produto do Nuvemshop',
              {'id': {'type': 'string', 'description': 'ID do produto'}},
              ['id']),
        _tool('nuvemshop_produto_criar',
              'Cria um novo produto no Nuvemshop',
              {'name': {'type': 'string', 'description': 'Nome do produto'},
               'price': {'type': 'number', 'description': 'Preco do produto'},
               'sku': {'type': 'string', 'description': 'SKU (opcional)'},
               'stock': {'type': 'integer', 'description': 'Estoque inicial (opcional)'},
               'description': {'type': 'string', 'description': 'Descricao do produto'},
               'category_ids': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'IDs de categorias'}},
              ['name', 'price']),
        _tool('nuvemshop_produto_atualizar',
              'Atualiza um produto existente no Nuvemshop (nome, descricao, publicacao)',
              {'product_id': {'type': 'string', 'description': 'ID do produto'},
               'name': {'type': 'string', 'description': 'Novo nome'},
               'description': {'type': 'string', 'description': 'Nova descricao'},
               'published': {'type': 'boolean', 'description': 'Publicado?'}},
              ['product_id']),
        _tool('nuvemshop_produto_deletar',
              'Remove um produto do Nuvemshop',
              {'product_id': {'type': 'string', 'description': 'ID do produto'}},
              ['product_id']),
        _tool('nuvemshop_estoque_atualizar',
              'Atualiza quantidade em estoque de um produto no Nuvemshop',
              {'product_id': {'type': 'string', 'description': 'ID do produto'},
               'new_qty': {'type': 'integer', 'description': 'Nova quantidade em estoque'}},
              ['product_id', 'new_qty']),
        _tool('nuvemshop_preco_atualizar',
              'Atualiza preco de um produto no Nuvemshop',
              {'product_id': {'type': 'string', 'description': 'ID do produto'},
               'new_price': {'type': 'number', 'description': 'Novo preco'}},
              ['product_id', 'new_price']),

        # ── Variantes ─────────────────────────────────────────────────────
        _tool('nuvemshop_variantes_listar',
              'Lista variantes de um produto do Nuvemshop',
              {'product_id': {'type': 'string', 'description': 'ID do produto'}},
              ['product_id']),

        # ── Categorias ────────────────────────────────────────────────────
        _tool('nuvemshop_categorias_listar',
              'Lista categorias da loja Nuvemshop',
              {'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50}}),
        _tool('nuvemshop_categoria_detalhar',
              'Retorna detalhes de uma categoria do Nuvemshop',
              {'category_id': {'type': 'string', 'description': 'ID da categoria'}},
              ['category_id']),
        _tool('nuvemshop_categoria_criar',
              'Cria uma nova categoria no Nuvemshop',
              {'name': {'type': 'string', 'description': 'Nome da categoria'},
               'parent_id': {'type': 'string', 'description': 'ID da categoria pai (opcional)'}},
              ['name']),

        # ── Clientes ──────────────────────────────────────────────────────
        _tool('nuvemshop_clientes_listar',
              'Lista clientes da loja Nuvemshop',
              {'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50},
               'since': {'type': 'string', 'description': 'Data inicio (YYYY-MM-DD)'},
               'q': {'type': 'string', 'description': 'Busca por nome/email'}}),
        _tool('nuvemshop_cliente_detalhar',
              'Retorna detalhes de um cliente do Nuvemshop',
              {'customer_id': {'type': 'string', 'description': 'ID do cliente'}},
              ['customer_id']),
        _tool('nuvemshop_cliente_criar',
              'Cria um novo cliente no Nuvemshop',
              {'name': {'type': 'string', 'description': 'Nome completo'},
               'email': {'type': 'string', 'description': 'Email'},
               'phone': {'type': 'string', 'description': 'Telefone'},
               'identification': {'type': 'string', 'description': 'CPF/CNPJ'}},
              ['name', 'email']),
        _tool('nuvemshop_cliente_atualizar',
              'Atualiza dados de um cliente no Nuvemshop',
              {'customer_id': {'type': 'string', 'description': 'ID do cliente'},
               'name': {'type': 'string', 'description': 'Nome completo'},
               'email': {'type': 'string', 'description': 'Email'},
               'phone': {'type': 'string', 'description': 'Telefone'},
               'identification': {'type': 'string', 'description': 'CPF/CNPJ'},
               'note': {'type': 'string', 'description': 'Nota interna'}},
              ['customer_id']),

        # ── Cupons ────────────────────────────────────────────────────────
        _tool('nuvemshop_cupons_listar',
              'Lista cupons de desconto do Nuvemshop',
              {'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50}}),
        _tool('nuvemshop_cupom_detalhar',
              'Retorna detalhes de um cupom do Nuvemshop',
              {'coupon_id': {'type': 'string', 'description': 'ID do cupom'}},
              ['coupon_id']),
        _tool('nuvemshop_cupom_criar',
              'Cria um novo cupom de desconto no Nuvemshop',
              {'code': {'type': 'string', 'description': 'Codigo do cupom'},
               'value': {'type': 'number', 'description': 'Valor do desconto'},
               'coupon_type': {'type': 'string', 'description': 'Tipo: percentage ou absolute', 'default': 'percentage'},
               'min_price': {'type': 'number', 'description': 'Valor minimo do pedido'},
               'max_uses': {'type': 'integer', 'description': 'Maximo de usos'},
               'start_date': {'type': 'string', 'description': 'Data inicio (ISO)'},
               'end_date': {'type': 'string', 'description': 'Data fim (ISO)'},
               'categories': {'type': 'array', 'items': {'type': 'integer'}, 'description': 'IDs de categorias'}},
              ['code', 'value']),
        _tool('nuvemshop_cupom_deletar',
              'Remove um cupom de desconto do Nuvemshop',
              {'coupon_id': {'type': 'string', 'description': 'ID do cupom'}},
              ['coupon_id']),

        # ── Páginas ───────────────────────────────────────────────────────
        _tool('nuvemshop_paginas_listar',
              'Lista paginas institucionais da loja Nuvemshop',
              {'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50}}),
        _tool('nuvemshop_pagina_detalhar',
              'Retorna detalhes de uma pagina institucional do Nuvemshop',
              {'page_id': {'type': 'string', 'description': 'ID da pagina'}},
              ['page_id']),

        # ── Transacoes ────────────────────────────────────────────────────
        _tool('nuvemshop_pedido_transacoes_listar',
              'Lista transacoes de pagamento de um pedido do Nuvemshop',
              {'order_id': {'type': 'string', 'description': 'ID do pedido'}},
              ['order_id']),

        # ── Abandonos de carrinho ─────────────────────────────────────────
        _tool('nuvemshop_abandonos_listar',
              'Lista checkouts abandonados do Nuvemshop',
              {'limit': {'type': 'integer', 'description': 'Limite por pagina (default 50)', 'default': 50}}),

        # ── Imagens de produto ────────────────────────────────────────────
        _tool('nuvemshop_produto_imagens_listar',
              'Lista imagens de um produto do Nuvemshop',
              {'product_id': {'type': 'string', 'description': 'ID do produto'}},
              ['product_id']),

        # ── Webhooks ──────────────────────────────────────────────────────
        _tool('nuvemshop_webhooks_listar',
              'Lista webhooks configurados no Nuvemshop',
              {}),
        _tool('nuvemshop_webhook_criar',
              'Cria um novo webhook no Nuvemshop',
              {'url': {'type': 'string', 'description': 'URL de callback'},
               'event': {'type': 'string', 'description': 'Evento (ex: order/paid, product/created)'}},
              ['url', 'event']),
        _tool('nuvemshop_webhook_deletar',
              'Remove um webhook do Nuvemshop',
              {'webhook_id': {'type': 'string', 'description': 'ID do webhook'}},
              ['webhook_id']),

        # ── Metafields ────────────────────────────────────────────────────
        _tool('nuvemshop_metafields_listar',
              'Lista metafields de um recurso do Nuvemshop',
              {'resource': {'type': 'string', 'description': 'Tipo de recurso (store, products, categories, etc)', 'default': 'store'},
               'resource_id': {'type': 'string', 'description': 'ID do recurso (opcional para store)'}}),

        # ── Frete / Shipping Carriers ─────────────────────────────────────
        _tool('nuvemshop_transportadoras_listar',
              'Lista transportadoras/shipping carriers do Nuvemshop',
              {}),

        # ── Empresa ───────────────────────────────────────────────────────
        _tool('nuvemshop_empresa',
              'Informacoes da loja conectada ao Nuvemshop',
              {}),
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
        # Pedidos
        case 'nuvemshop_pedidos_listar':
            return c.list_orders(
                status=args.get('status', 'paid'),
                limit=args.get('limit', 50),
                since=args.get('since'),
            )
        case 'nuvemshop_pedido_detalhar':
            return c.get_order(args['id'])
        case 'nuvemshop_pedido_atualizar':
            return c.update_order(
                args['order_id'],
                note=args.get('note'),
                owner=args.get('owner'),
                shipping_status=args.get('shipping_status'),
            )
        case 'nuvemshop_pedido_enviar':
            return c.mark_order_shipped(args['id'], tracking_code=args.get('tracking_code', ''))
        case 'nuvemshop_pedido_cancelar':
            return c.cancel_order(args['id'], reason=args.get('reason', ''))

        # Produtos
        case 'nuvemshop_produtos_listar':
            return c.list_products(
                limit=args.get('limit', 50),
                in_stock_only=args.get('in_stock_only', False),
            )
        case 'nuvemshop_produto_detalhar':
            return c.get_product(args['id'])
        case 'nuvemshop_produto_criar':
            return c.create_product(
                name=args['name'],
                price=args['price'],
                sku=args.get('sku'),
                stock=args.get('stock'),
                description=args.get('description'),
                category_ids=args.get('category_ids'),
            )
        case 'nuvemshop_produto_atualizar':
            return c.update_product(
                args['product_id'],
                name=args.get('name'),
                description=args.get('description'),
                published=args.get('published'),
            )
        case 'nuvemshop_produto_deletar':
            return c.delete_product(args['product_id'])
        case 'nuvemshop_estoque_atualizar':
            return c.update_stock(args['product_id'], args['new_qty'])
        case 'nuvemshop_preco_atualizar':
            return c.update_price(args['product_id'], args['new_price'])

        # Variantes
        case 'nuvemshop_variantes_listar':
            return c.list_variants(args['product_id'])

        # Categorias
        case 'nuvemshop_categorias_listar':
            return c.list_categories(limit=args.get('limit', 50))
        case 'nuvemshop_categoria_detalhar':
            return c.get_category(args['category_id'])
        case 'nuvemshop_categoria_criar':
            return c.create_category(args['name'], parent_id=args.get('parent_id'))

        # Clientes
        case 'nuvemshop_clientes_listar':
            return c.list_customers(
                limit=args.get('limit', 50),
                since=args.get('since'),
                q=args.get('q'),
            )
        case 'nuvemshop_cliente_detalhar':
            return c.get_customer(args['customer_id'])
        case 'nuvemshop_cliente_criar':
            return c.create_customer(
                name=args['name'],
                email=args['email'],
                phone=args.get('phone'),
                identification=args.get('identification'),
            )
        case 'nuvemshop_cliente_atualizar':
            return c.update_customer(
                args['customer_id'],
                name=args.get('name'),
                email=args.get('email'),
                phone=args.get('phone'),
                identification=args.get('identification'),
                note=args.get('note'),
            )

        # Cupons
        case 'nuvemshop_cupons_listar':
            return c.list_coupons(limit=args.get('limit', 50))
        case 'nuvemshop_cupom_detalhar':
            return c.get_coupon(args['coupon_id'])
        case 'nuvemshop_cupom_criar':
            return c.create_coupon(
                code=args['code'],
                value=args['value'],
                coupon_type=args.get('coupon_type', 'percentage'),
                min_price=args.get('min_price'),
                max_uses=args.get('max_uses'),
                start_date=args.get('start_date'),
                end_date=args.get('end_date'),
                categories=args.get('categories'),
            )
        case 'nuvemshop_cupom_deletar':
            return c.delete_coupon(args['coupon_id'])

        # Páginas
        case 'nuvemshop_paginas_listar':
            return c.list_pages(limit=args.get('limit', 50))
        case 'nuvemshop_pagina_detalhar':
            return c.get_page(args['page_id'])

        # Transacoes
        case 'nuvemshop_pedido_transacoes_listar':
            return c.list_order_transactions(args['order_id'])

        # Abandonos
        case 'nuvemshop_abandonos_listar':
            return c.list_abandoned_checkouts(limit=args.get('limit', 50))

        # Imagens de produto
        case 'nuvemshop_produto_imagens_listar':
            return c.list_product_images(args['product_id'])

        # Webhooks
        case 'nuvemshop_webhooks_listar':
            return c.list_webhooks()
        case 'nuvemshop_webhook_criar':
            return c.create_webhook(url=args['url'], event=args['event'])
        case 'nuvemshop_webhook_deletar':
            return c.delete_webhook(args['webhook_id'])

        # Metafields
        case 'nuvemshop_metafields_listar':
            return c.list_metafields(
                resource=args.get('resource', 'store'),
                resource_id=args.get('resource_id'),
            )

        # Frete
        case 'nuvemshop_transportadoras_listar':
            return c.list_shipping_carriers()

        # Empresa
        case 'nuvemshop_empresa':
            return c.company_info()

        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
