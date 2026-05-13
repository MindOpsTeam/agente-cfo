#!/usr/bin/env python3
"""
MCP server para PipeRun — 28 tools.
Endpoints cobertos: deals CRUD, contatos CRUD, empresas, pipelines, stages,
atividades, produtos, campos custom, usuários, motivos de perda.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from piperun_client import PipeRunClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('piperun')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = PipeRunClient()
    return _client

_P = {'limit': {'type': 'integer', 'default': 50}, 'page': {'type': 'integer', 'default': 1}}
_ID = {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'ID'}}, 'required': ['id']}
_E = {'type': 'object', 'properties': {}, 'required': []}

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # Deals
        types.Tool(name='piperun_deals_listar', description='Lista deals do PipeRun',
                   inputSchema={'type':'object','properties':{'status':{'type':'string','default':'open'},**_P},'required':[]}),
        types.Tool(name='piperun_deal_obter', description='Obtém deal pelo ID', inputSchema=_ID),
        types.Tool(name='piperun_deal_criar', description='Cria novo deal no PipeRun',
                   inputSchema={'type':'object','properties':{'title':{'type':'string'},'amount':{'type':'number'},'pipeline':{'type':'string'}},'required':['title']}),
        types.Tool(name='piperun_deal_atualizar', description='Atualiza deal no PipeRun',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'amount':{'type':'number'},'close_date':{'type':'string'}},'required':['id']}),
        types.Tool(name='piperun_deal_mover', description='Move deal para outra etapa',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'to_stage':{'type':'string'}},'required':['id','to_stage']}),
        types.Tool(name='piperun_deal_nota', description='Adiciona nota a um deal',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'note':{'type':'string'}},'required':['id','note']}),
        types.Tool(name='piperun_deal_ganho', description='Marca deal como ganho', inputSchema=_ID),
        types.Tool(name='piperun_deal_perdido', description='Marca deal como perdido',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'reason':{'type':'string'}},'required':['id']}),
        # Contatos
        types.Tool(name='piperun_contatos_listar', description='Lista contatos do PipeRun',
                   inputSchema={'type':'object','properties':{'search':{'type':'string'},**_P},'required':[]}),
        types.Tool(name='piperun_contato_obter', description='Obtém contato pelo ID', inputSchema=_ID),
        types.Tool(name='piperun_contato_criar', description='Cria novo contato no PipeRun',
                   inputSchema={'type':'object','properties':{'name':{'type':'string'},'email':{'type':'string'},'phone':{'type':'string'}},'required':['name']}),
        types.Tool(name='piperun_contato_atualizar', description='Atualiza contato no PipeRun',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'name':{'type':'string'},'email':{'type':'string'}},'required':['id']}),
        types.Tool(name='piperun_contato_excluir', description='Exclui contato pelo ID', inputSchema=_ID),
        # Empresas
        types.Tool(name='piperun_empresas_listar', description='Lista empresas do PipeRun',
                   inputSchema={'type':'object','properties':{'search':{'type':'string'},**_P},'required':[]}),
        types.Tool(name='piperun_empresa_obter', description='Obtém empresa pelo ID', inputSchema=_ID),
        types.Tool(name='piperun_empresa_criar', description='Cria nova empresa no PipeRun',
                   inputSchema={'type':'object','properties':{'name':{'type':'string'},'cnpj':{'type':'string'}},'required':['name']}),
        types.Tool(name='piperun_empresa_atualizar', description='Atualiza empresa no PipeRun',
                   inputSchema={'type':'object','properties':{'id':{'type':'string'},'name':{'type':'string'}},'required':['id']}),
        # Pipeline & Stages
        types.Tool(name='piperun_pipelines_listar', description='Lista pipelines do PipeRun', inputSchema=_E),
        types.Tool(name='piperun_stages_listar', description='Lista etapas do funil',
                   inputSchema={'type':'object','properties':{'pipeline_id':{'type':'string'}},'required':[]}),
        # Atividades
        types.Tool(name='piperun_atividades_listar', description='Lista atividades do PipeRun',
                   inputSchema={'type':'object','properties':{'deal_id':{'type':'string'},**_P},'required':[]}),
        types.Tool(name='piperun_atividade_criar', description='Cria atividade no PipeRun',
                   inputSchema={'type':'object','properties':{'deal_id':{'type':'string'},'subject':{'type':'string'},'type':{'type':'string'}},'required':['deal_id','subject']}),
        # Produtos
        types.Tool(name='piperun_produtos_listar', description='Lista produtos do PipeRun',
                   inputSchema={'type':'object','properties':{**_P},'required':[]}),
        types.Tool(name='piperun_produto_obter', description='Obtém produto pelo ID', inputSchema=_ID),
        # Auxiliares
        types.Tool(name='piperun_campos_custom_listar', description='Lista campos customizados', inputSchema=_E),
        types.Tool(name='piperun_usuarios_listar', description='Lista usuários do PipeRun', inputSchema=_E),
        types.Tool(name='piperun_motivos_perda_listar', description='Lista motivos de perda do PipeRun', inputSchema=_E),
        # Empresa conectada
        types.Tool(name='piperun_empresa_info', description='Info da empresa conectada ao PipeRun', inputSchema=_E),
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
        case 'piperun_deals_listar':
            return c.list_deals(status=args.get('status','open'), limit=args.get('limit',50), page=args.get('page',1))
        case 'piperun_deal_obter': return c.get_deal(args['id'])
        case 'piperun_deal_criar':
            return c.create_deal(title=args['title'], amount=args.get('amount'), pipeline=args.get('pipeline'))
        case 'piperun_deal_atualizar':
            return c.update_deal(args['id'], amount=args.get('amount'), close_date=args.get('close_date'))
        case 'piperun_deal_mover': return c.move_deal(args['id'], args['to_stage'])
        case 'piperun_deal_nota': return c.add_deal_note(args['id'], args['note'])
        case 'piperun_deal_ganho': return c.mark_deal_won(args['id'])
        case 'piperun_deal_perdido': return c.mark_deal_lost(args['id'], reason=args.get('reason',''))
        case 'piperun_contatos_listar':
            return c.list_contacts(limit=args.get('limit',50), page=args.get('page',1), search=args.get('search'))
        case 'piperun_contato_obter': return c.get_contact(args['id'])
        case 'piperun_contato_criar': return c.create_contact(args)
        case 'piperun_contato_atualizar': id=args.pop('id'); return c.update_contact(id, args)
        case 'piperun_contato_excluir': return c.delete_contact(args['id'])
        case 'piperun_empresas_listar':
            return c.list_companies(limit=args.get('limit',50), page=args.get('page',1), search=args.get('search'))
        case 'piperun_empresa_obter': return c.get_company(args['id'])
        case 'piperun_empresa_criar': return c.create_company(args)
        case 'piperun_empresa_atualizar': id=args.pop('id'); return c.update_company(id, args)
        case 'piperun_pipelines_listar': return c.list_pipelines()
        case 'piperun_stages_listar': return c.list_stages(pipeline_id=args.get('pipeline_id'))
        case 'piperun_atividades_listar':
            return c.list_activities(deal_id=args.get('deal_id'), limit=args.get('limit',50), page=args.get('page',1))
        case 'piperun_atividade_criar': return c.create_activity(args)
        case 'piperun_produtos_listar': return c.list_products(limit=args.get('limit',50), page=args.get('page',1))
        case 'piperun_produto_obter': return c.get_product(args['id'])
        case 'piperun_campos_custom_listar': return c.list_custom_fields()
        case 'piperun_usuarios_listar': return c.list_users()
        case 'piperun_motivos_perda_listar': return c.list_lost_reasons()
        case 'piperun_empresa_info': return c.company_info()
        case _: raise ValueError(f'Tool desconhecida: {name}')

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
