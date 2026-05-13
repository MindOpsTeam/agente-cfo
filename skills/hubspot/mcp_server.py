#!/usr/bin/env python3
"""
MCP server para HubSpot — 40 tools.
CRM completo: deals, contacts, companies, tickets, line_items, notes, calls,
emails, meetings, tasks, pipelines, owners, properties.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from hubspot_client import HubSpotClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('hubspot')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = HubSpotClient()
    return _client


def _tool(name, desc, props=None, required=None):
    return types.Tool(
        name=name,
        description=desc,
        inputSchema={
            'type': 'object',
            'properties': props or {},
            'required': required or [],
        },
    )


_LIMIT = {'type': 'integer', 'description': 'Limite de resultados (default 50)', 'default': 50}
_ID = lambda entity: {'type': 'string', 'description': f'ID do {entity}'}
_PROPS_DICT = {'type': 'object', 'description': 'Dicionario de propriedades a atualizar', 'additionalProperties': {'type': 'string'}}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Deals (8 existing) ───────────────────────────────────────────
        _tool('hubspot_deals_listar', 'Lista deals/oportunidades do HubSpot (paginado)', {
            'status': {'type': 'string', 'description': 'Filtro de status (open, won, lost)', 'default': 'open'},
            'limit': _LIMIT,
            'page': {'type': 'integer', 'description': 'Pagina (default 1)', 'default': 1},
        }),
        _tool('hubspot_deal_obter', 'Obtem detalhes de um deal especifico', {
            'id': _ID('deal'),
        }, ['id']),
        _tool('hubspot_deal_criar', 'Cria novo deal/oportunidade no HubSpot', {
            'title': {'type': 'string', 'description': 'Titulo do deal'},
            'amount': {'type': 'number', 'description': 'Valor do deal'},
            'pipeline': {'type': 'string', 'description': 'Pipeline/funil'},
        }, ['title']),
        _tool('hubspot_deal_atualizar', 'Atualiza valor e/ou data de fechamento do deal', {
            'id': _ID('deal'),
            'amount': {'type': 'number', 'description': 'Novo valor do deal'},
            'close_date': {'type': 'string', 'description': 'Nova data de fechamento (YYYY-MM-DD)'},
        }, ['id']),
        _tool('hubspot_deal_mover', 'Move deal para outra etapa/stage', {
            'id': _ID('deal'),
            'to_stage': {'type': 'string', 'description': 'Nome ou ID da etapa destino'},
        }, ['id', 'to_stage']),
        _tool('hubspot_deal_nota', 'Adiciona nota/comentario a um deal', {
            'id': _ID('deal'),
            'note': {'type': 'string', 'description': 'Texto da nota'},
        }, ['id', 'note']),
        _tool('hubspot_deal_ganho', 'Marca deal como ganho/won', {
            'id': _ID('deal'),
        }, ['id']),
        _tool('hubspot_deal_perdido', 'Marca deal como perdido/lost', {
            'id': _ID('deal'),
            'reason': {'type': 'string', 'description': 'Motivo da perda'},
        }, ['id']),
        _tool('hubspot_deal_excluir', 'Exclui um deal do HubSpot', {
            'id': _ID('deal'),
        }, ['id']),

        # ── Contacts (5) ─────────────────────────────────────────────────
        _tool('hubspot_contatos_listar', 'Lista contatos do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_contato_obter', 'Obtem detalhes de um contato', {
            'id': _ID('contato'),
        }, ['id']),
        _tool('hubspot_contato_criar', 'Cria novo contato no HubSpot', {
            'email': {'type': 'string', 'description': 'Email do contato'},
            'firstname': {'type': 'string', 'description': 'Primeiro nome'},
            'lastname': {'type': 'string', 'description': 'Sobrenome'},
            'phone': {'type': 'string', 'description': 'Telefone'},
        }, ['email']),
        _tool('hubspot_contato_atualizar', 'Atualiza propriedades de um contato', {
            'id': _ID('contato'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_contato_excluir', 'Exclui um contato do HubSpot', {
            'id': _ID('contato'),
        }, ['id']),

        # ── Companies (5) ────────────────────────────────────────────────
        _tool('hubspot_empresas_listar', 'Lista empresas do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_empresa_obter', 'Obtem detalhes de uma empresa', {
            'id': _ID('empresa'),
        }, ['id']),
        _tool('hubspot_empresa_criar', 'Cria nova empresa no HubSpot', {
            'name': {'type': 'string', 'description': 'Nome da empresa'},
            'domain': {'type': 'string', 'description': 'Dominio da empresa'},
            'industry': {'type': 'string', 'description': 'Industria/setor'},
        }, ['name']),
        _tool('hubspot_empresa_atualizar', 'Atualiza propriedades de uma empresa', {
            'id': _ID('empresa'),
            'properties': _PROPS_DICT,
        }, ['id', 'properties']),
        _tool('hubspot_empresa_excluir', 'Exclui uma empresa do HubSpot', {
            'id': _ID('empresa'),
        }, ['id']),

        # ── Tickets (3) ──────────────────────────────────────────────────
        _tool('hubspot_tickets_listar', 'Lista tickets de suporte do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_ticket_obter', 'Obtem detalhes de um ticket', {
            'id': _ID('ticket'),
        }, ['id']),
        _tool('hubspot_ticket_criar', 'Cria novo ticket de suporte', {
            'subject': {'type': 'string', 'description': 'Assunto do ticket'},
            'content': {'type': 'string', 'description': 'Descricao do ticket'},
            'priority': {'type': 'string', 'description': 'Prioridade (LOW, MEDIUM, HIGH)'},
        }, ['subject']),
        _tool('hubspot_ticket_excluir', 'Exclui um ticket do HubSpot', {
            'id': _ID('ticket'),
        }, ['id']),

        # ── Line Items (1) ───────────────────────────────────────────────
        _tool('hubspot_line_items_listar', 'Lista line items (itens de linha) do HubSpot', {
            'limit': _LIMIT,
        }),

        # ── Notes (2) ────────────────────────────────────────────────────
        _tool('hubspot_notas_listar', 'Lista notas/engagements do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_nota_criar', 'Cria nota associada a contato ou deal', {
            'body': {'type': 'string', 'description': 'Texto da nota'},
            'contact_id': {'type': 'string', 'description': 'ID do contato associado'},
            'deal_id': {'type': 'string', 'description': 'ID do deal associado'},
        }, ['body']),

        # ── Calls (2) ────────────────────────────────────────────────────
        _tool('hubspot_calls_listar', 'Lista chamadas/ligacoes do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_call_criar', 'Registra nova chamada/ligacao no HubSpot', {
            'title': {'type': 'string', 'description': 'Titulo da chamada'},
            'body': {'type': 'string', 'description': 'Notas da chamada'},
            'duration_ms': {'type': 'integer', 'description': 'Duracao em milissegundos'},
            'contact_id': {'type': 'string', 'description': 'ID do contato associado'},
        }, ['title']),

        # ── Emails (1) ───────────────────────────────────────────────────
        _tool('hubspot_emails_listar', 'Lista emails registrados no HubSpot', {
            'limit': _LIMIT,
        }),

        # ── Meetings (1) ─────────────────────────────────────────────────
        _tool('hubspot_meetings_listar', 'Lista reunioes/meetings do HubSpot', {
            'limit': _LIMIT,
        }),

        # ── Tasks (2) ────────────────────────────────────────────────────
        _tool('hubspot_tasks_listar', 'Lista tarefas do HubSpot', {
            'limit': _LIMIT,
        }),
        _tool('hubspot_task_criar', 'Cria nova tarefa no HubSpot', {
            'subject': {'type': 'string', 'description': 'Assunto da tarefa'},
            'body': {'type': 'string', 'description': 'Descricao da tarefa'},
            'priority': {'type': 'string', 'description': 'Prioridade (LOW, MEDIUM, HIGH)'},
            'due_date': {'type': 'string', 'description': 'Data limite (YYYY-MM-DD)'},
        }, ['subject']),

        # ── Pipelines (2) ────────────────────────────────────────────────
        _tool('hubspot_pipelines_listar', 'Lista pipelines/funis de deals', {
            'object_type': {'type': 'string', 'description': 'Tipo de objeto (deals, tickets)', 'default': 'deals'},
        }),
        _tool('hubspot_pipeline_stages', 'Lista etapas/stages de todas as pipelines de deals', {}),

        # ── Owners (1) ───────────────────────────────────────────────────
        _tool('hubspot_owners_listar', 'Lista proprietarios/owners do HubSpot', {
            'limit': {'type': 'integer', 'description': 'Limite de resultados (default 100)', 'default': 100},
        }),

        # ── Properties (2) ───────────────────────────────────────────────
        _tool('hubspot_properties_listar', 'Lista propriedades de um tipo de objeto', {
            'object_type': {'type': 'string', 'description': 'Tipo de objeto (deals, contacts, companies, tickets)', 'default': 'deals'},
        }),

        # ── Account/Company info (1) ─────────────────────────────────────
        _tool('hubspot_conta_info', 'Informacoes da conta/empresa conectada ao HubSpot', {}),

        # ── Search (3) ───────────────────────────────────────────────────
        _tool('hubspot_contatos_buscar', 'Busca contatos por email, nome ou telefone', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_empresas_buscar', 'Busca empresas por nome ou dominio', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
        _tool('hubspot_deals_buscar', 'Busca deals por nome', {
            'query': {'type': 'string', 'description': 'Termo de busca'},
            'limit': _LIMIT,
        }, ['query']),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = _dispatch(name, arguments)
        return [types.TextContent(type='text', text=json.dumps(result, ensure_ascii=False, default=str))]
    except Exception as e:
        return [types.TextContent(type='text', text=json.dumps({'error': str(e)}))]


def _search_objects(c, object_type: str, query: str, limit: int = 50) -> dict:
    """Generic CRM search via POST /crm/v3/objects/{type}/search."""
    body = {
        "query": query,
        "limit": limit,
    }
    raw = c._post_json(f"crm/v3/objects/{object_type}/search", body)
    results = raw.get("results", []) if isinstance(raw, dict) else []
    return {"items": results, "total": raw.get("total", len(results)) if isinstance(raw, dict) else len(results)}


def _dispatch(name: str, args: dict):
    c = _get_client()
    match name:
        # ── Deals ────────────────────────────────────────────────────
        case 'hubspot_deals_listar':
            return c.list_deals(
                status=args.get('status', 'open'),
                limit=args.get('limit', 50),
                page=args.get('page', 1),
            )
        case 'hubspot_deal_obter':
            return c.get_deal(args['id'])
        case 'hubspot_deal_criar':
            return c.create_deal(
                title=args['title'],
                amount=args.get('amount'),
                pipeline=args.get('pipeline'),
            )
        case 'hubspot_deal_atualizar':
            return c.update_deal(
                args['id'],
                amount=args.get('amount'),
                close_date=args.get('close_date'),
            )
        case 'hubspot_deal_mover':
            return c.move_deal(args['id'], args['to_stage'])
        case 'hubspot_deal_nota':
            return c.add_deal_note(args['id'], args['note'])
        case 'hubspot_deal_ganho':
            return c.mark_deal_won(args['id'])
        case 'hubspot_deal_perdido':
            return c.mark_deal_lost(args['id'], reason=args.get('reason', ''))
        case 'hubspot_deal_excluir':
            return c._delete_object('deals', args['id'])

        # ── Contacts ─────────────────────────────────────────────────
        case 'hubspot_contatos_listar':
            return c.list_contacts(limit=args.get('limit', 50))
        case 'hubspot_contato_obter':
            return c.get_contact(args['id'])
        case 'hubspot_contato_criar':
            return c.create_contact(
                email=args['email'],
                firstname=args.get('firstname'),
                lastname=args.get('lastname'),
                phone=args.get('phone'),
            )
        case 'hubspot_contato_atualizar':
            return c.update_contact(args['id'], args['properties'])
        case 'hubspot_contato_excluir':
            return c.delete_contact(args['id'])

        # ── Companies ────────────────────────────────────────────────
        case 'hubspot_empresas_listar':
            return c.list_companies(limit=args.get('limit', 50))
        case 'hubspot_empresa_obter':
            return c.get_company(args['id'])
        case 'hubspot_empresa_criar':
            return c.create_company(
                name=args['name'],
                domain=args.get('domain'),
                industry=args.get('industry'),
            )
        case 'hubspot_empresa_atualizar':
            return c.update_company(args['id'], args['properties'])
        case 'hubspot_empresa_excluir':
            return c.delete_company(args['id'])

        # ── Tickets ──────────────────────────────────────────────────
        case 'hubspot_tickets_listar':
            return c.list_tickets(limit=args.get('limit', 50))
        case 'hubspot_ticket_obter':
            return c.get_ticket(args['id'])
        case 'hubspot_ticket_criar':
            return c.create_ticket(
                subject=args['subject'],
                content=args.get('content'),
                priority=args.get('priority'),
            )
        case 'hubspot_ticket_excluir':
            return c._delete_object('tickets', args['id'])

        # ── Line Items ───────────────────────────────────────────────
        case 'hubspot_line_items_listar':
            return c.list_line_items(limit=args.get('limit', 50))

        # ── Notes ────────────────────────────────────────────────────
        case 'hubspot_notas_listar':
            return c.list_notes(limit=args.get('limit', 50))
        case 'hubspot_nota_criar':
            return c.create_note(
                body=args['body'],
                contact_id=args.get('contact_id'),
                deal_id=args.get('deal_id'),
            )

        # ── Calls ────────────────────────────────────────────────────
        case 'hubspot_calls_listar':
            return c.list_calls(limit=args.get('limit', 50))
        case 'hubspot_call_criar':
            return c.create_call(
                title=args['title'],
                body=args.get('body'),
                duration_ms=args.get('duration_ms'),
                contact_id=args.get('contact_id'),
            )

        # ── Emails ───────────────────────────────────────────────────
        case 'hubspot_emails_listar':
            return c.list_emails(limit=args.get('limit', 50))

        # ── Meetings ─────────────────────────────────────────────────
        case 'hubspot_meetings_listar':
            return c.list_meetings(limit=args.get('limit', 50))

        # ── Tasks ────────────────────────────────────────────────────
        case 'hubspot_tasks_listar':
            return c.list_tasks(limit=args.get('limit', 50))
        case 'hubspot_task_criar':
            return c.create_task(
                subject=args['subject'],
                body=args.get('body'),
                priority=args.get('priority'),
                due_date=args.get('due_date'),
            )

        # ── Pipelines ───────────────────────────────────────────────
        case 'hubspot_pipelines_listar':
            return c.list_pipelines(object_type=args.get('object_type', 'deals'))
        case 'hubspot_pipeline_stages':
            stages = c._fetch_stages()
            return {"items": [{"id": k, "label": v} for k, v in stages.items()], "total": len(stages)}

        # ── Owners ───────────────────────────────────────────────────
        case 'hubspot_owners_listar':
            return c.list_owners(limit=args.get('limit', 100))

        # ── Properties ───────────────────────────────────────────────
        case 'hubspot_properties_listar':
            return c.list_properties(object_type=args.get('object_type', 'deals'))

        # ── Account info ─────────────────────────────────────────────
        case 'hubspot_conta_info':
            return c.company_info()

        # ── Search ───────────────────────────────────────────────────
        case 'hubspot_contatos_buscar':
            return _search_objects(c, 'contacts', args['query'], limit=args.get('limit', 50))
        case 'hubspot_empresas_buscar':
            return _search_objects(c, 'companies', args['query'], limit=args.get('limit', 50))
        case 'hubspot_deals_buscar':
            return _search_objects(c, 'deals', args['query'], limit=args.get('limit', 50))

        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
