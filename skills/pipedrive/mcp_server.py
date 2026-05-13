#!/usr/bin/env python3
"""
MCP server para Pipedrive — 144 tools.
Endpoints cobertos: deals, persons, organizations, activities, products,
pipelines, stages, notes, users, webhooks, goals, filters, empresa,
leads, lead labels, files, call logs, mailbox, custom fields, roles,
recents, item search, currencies, subscriptions, projects, meetings, changelogs.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from pipedrive_client import PipedriveClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('pipedrive')
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = PipedriveClient()
    return _client


def _t(name, desc, props, req=None):
    return types.Tool(name=name, description=desc, inputSchema={
        'type': 'object', 'properties': props, 'required': req or []})


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Deals ────────────────────────────────────────────────────────
        _t('pipedrive_deals_listar', 'Lista deals/oportunidades do Pipedrive (paginado)', {
            'status': {'type': 'string', 'description': 'Filtro: open, won, lost, all', 'default': 'open'},
            'limit': {'type': 'integer', 'default': 50},
            'page': {'type': 'integer', 'default': 1},
        }),
        _t('pipedrive_deal_detalhar', 'Retorna detalhes de um deal do Pipedrive', {
            'id': {'type': 'string', 'description': 'ID do deal'},
        }, ['id']),
        _t('pipedrive_deal_criar', 'Cria novo deal/oportunidade no Pipedrive', {
            'title': {'type': 'string'}, 'amount': {'type': 'number'},
            'pipeline': {'type': 'string', 'description': 'Pipeline ID ou nome'},
        }, ['title']),
        _t('pipedrive_deal_atualizar', 'Atualiza valor e/ou data de fechamento do deal', {
            'id': {'type': 'string'}, 'amount': {'type': 'number'},
            'close_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
        }, ['id']),
        _t('pipedrive_deal_mover', 'Move deal para outra etapa/stage', {
            'id': {'type': 'string'}, 'to_stage': {'type': 'string', 'description': 'Nome ou ID da etapa'},
        }, ['id', 'to_stage']),
        _t('pipedrive_deal_nota', 'Adiciona nota a um deal', {
            'id': {'type': 'string'}, 'note': {'type': 'string'},
        }, ['id', 'note']),
        _t('pipedrive_deal_ganho', 'Marca deal como ganho/won', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_deal_perdido', 'Marca deal como perdido/lost', {
            'id': {'type': 'string'}, 'reason': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_deal_excluir', 'Exclui um deal do Pipedrive', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Persons (Contacts) ───────────────────────────────────────────
        _t('pipedrive_contatos_listar', 'Lista contatos/persons do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_contato_detalhar', 'Detalhes de um contato/person', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_contato_criar', 'Cria contato/person no Pipedrive', {
            'name': {'type': 'string'}, 'email': {'type': 'string'},
            'phone': {'type': 'string'}, 'org_id': {'type': 'integer'},
        }, ['name']),
        _t('pipedrive_contato_atualizar', 'Atualiza contato/person', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
            'email': {'type': 'string'}, 'phone': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_contato_excluir', 'Exclui contato/person', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Organizations ────────────────────────────────────────────────
        _t('pipedrive_organizacoes_listar', 'Lista organizacoes do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_organizacao_detalhar', 'Detalhes de uma organizacao', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_organizacao_criar', 'Cria organizacao no Pipedrive', {
            'name': {'type': 'string'}, 'address': {'type': 'string'},
        }, ['name']),
        _t('pipedrive_organizacao_atualizar', 'Atualiza organizacao', {
            'id': {'type': 'string'}, 'name': {'type': 'string'}, 'address': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_organizacao_excluir', 'Exclui organizacao', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Activities ───────────────────────────────────────────────────
        _t('pipedrive_atividades_listar', 'Lista atividades do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_atividade_criar', 'Cria atividade (call, task, meeting, etc)', {
            'subject': {'type': 'string'}, 'type': {'type': 'string', 'default': 'task'},
            'due_date': {'type': 'string', 'description': 'YYYY-MM-DD'},
            'deal_id': {'type': 'integer'}, 'person_id': {'type': 'integer'},
        }, ['subject']),

        # ── Products ────────────────────────────────────────────────────
        _t('pipedrive_produtos_listar', 'Lista produtos do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_produto_detalhar', 'Detalhes de um produto', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_produto_criar', 'Cria produto no Pipedrive', {
            'name': {'type': 'string'}, 'code': {'type': 'string'},
            'unit': {'type': 'string'}, 'price': {'type': 'number'},
        }, ['name']),

        # ── Pipelines ───────────────────────────────────────────────────
        _t('pipedrive_pipelines_listar', 'Lista pipelines/funis do Pipedrive', {}),

        # ── Stages ──────────────────────────────────────────────────────
        _t('pipedrive_stages_listar', 'Lista etapas/stages (opcao: filtrar por pipeline)', {
            'pipeline_id': {'type': 'integer', 'description': 'ID do pipeline (opcional)'},
        }),

        # ── Notes ───────────────────────────────────────────────────────
        _t('pipedrive_notas_listar', 'Lista notas do Pipedrive', {
            'deal_id': {'type': 'integer'}, 'person_id': {'type': 'integer'},
            'limit': {'type': 'integer', 'default': 50}, 'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_nota_criar', 'Cria nota associada a deal/person/org', {
            'content': {'type': 'string'}, 'deal_id': {'type': 'integer'},
            'person_id': {'type': 'integer'}, 'org_id': {'type': 'integer'},
        }, ['content']),

        # ── Users ───────────────────────────────────────────────────────
        _t('pipedrive_usuarios_listar', 'Lista usuarios do Pipedrive', {}),

        # ── Webhooks ────────────────────────────────────────────────────
        _t('pipedrive_webhooks_listar', 'Lista webhooks configurados', {}),
        _t('pipedrive_webhook_criar', 'Cria webhook no Pipedrive', {
            'subscription_url': {'type': 'string'}, 'event_action': {'type': 'string', 'description': 'added, updated, merged, deleted, *'},
            'event_object': {'type': 'string', 'description': 'deal, person, organization, etc'},
        }, ['subscription_url', 'event_action', 'event_object']),
        _t('pipedrive_webhook_excluir', 'Exclui webhook', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Goals ───────────────────────────────────────────────────────
        _t('pipedrive_goals_listar', 'Lista goals/metas do Pipedrive', {}),

        # ── Filters ─────────────────────────────────────────────────────
        _t('pipedrive_filtros_listar', 'Lista filtros salvos do Pipedrive', {
            'type': {'type': 'string', 'description': 'Tipo: deals, persons, orgs, etc'},
        }),

        # ── Empresa ─────────────────────────────────────────────────────
        _t('pipedrive_empresa', 'Informacoes da empresa conectada ao Pipedrive', {}),

        # ── Leads ───────────────────────────────────────────────────────
        _t('pipedrive_leads_listar', 'Lista leads/inbox do Pipedrive (paginado)', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_lead_detalhar', 'Detalhes de um lead', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_lead_criar', 'Cria novo lead no Pipedrive', {
            'title': {'type': 'string'}, 'person_id': {'type': 'integer'},
            'organization_id': {'type': 'integer'}, 'value': {'type': 'number'},
        }, ['title']),
        _t('pipedrive_lead_atualizar', 'Atualiza titulo/labels de um lead', {
            'id': {'type': 'string'}, 'title': {'type': 'string'},
            'label_ids': {'type': 'array', 'items': {'type': 'string'}},
        }, ['id']),
        _t('pipedrive_lead_excluir', 'Exclui um lead', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Lead Labels ─────────────────────────────────────────────────
        _t('pipedrive_lead_labels_listar', 'Lista labels/etiquetas de leads', {}),
        _t('pipedrive_lead_label_criar', 'Cria label de lead', {
            'name': {'type': 'string'}, 'color': {'type': 'string', 'default': 'blue'},
        }, ['name']),
        _t('pipedrive_lead_label_atualizar', 'Atualiza label de lead', {
            'id': {'type': 'string'}, 'name': {'type': 'string'}, 'color': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_lead_label_excluir', 'Exclui label de lead', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Persons (extend) ────────────────────────────────────────────
        _t('pipedrive_contatos_merge', 'Merge dois contatos em um', {
            'id': {'type': 'string', 'description': 'ID do contato que permanece'},
            'merge_with_id': {'type': 'string', 'description': 'ID do contato a ser mesclado'},
        }, ['id', 'merge_with_id']),
        _t('pipedrive_contato_seguidores_listar', 'Lista seguidores de um contato', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_contato_seguidor_adicionar', 'Adiciona seguidor a um contato', {
            'id': {'type': 'string'}, 'user_id': {'type': 'integer'},
        }, ['id', 'user_id']),
        _t('pipedrive_contato_seguidor_excluir', 'Remove seguidor de um contato', {
            'id': {'type': 'string'}, 'follower_id': {'type': 'integer'},
        }, ['id', 'follower_id']),
        _t('pipedrive_contato_atualizacoes', 'Lista atualizacoes/flow de um contato', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_contato_atividades', 'Lista atividades de um contato', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_contato_deals', 'Lista deals de um contato', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_contato_arquivos', 'Lista arquivos de um contato', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),

        # ── Organizations (extend) ──────────────────────────────────────
        _t('pipedrive_organizacoes_merge', 'Merge duas organizacoes em uma', {
            'id': {'type': 'string', 'description': 'ID da org que permanece'},
            'merge_with_id': {'type': 'string', 'description': 'ID da org a ser mesclada'},
        }, ['id', 'merge_with_id']),
        _t('pipedrive_organizacao_seguidores', 'Lista seguidores de uma organizacao', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_organizacao_seguidor_adicionar', 'Adiciona seguidor a uma organizacao', {
            'id': {'type': 'string'}, 'user_id': {'type': 'integer'},
        }, ['id', 'user_id']),
        _t('pipedrive_organizacao_atualizacoes', 'Lista atualizacoes/flow de uma organizacao', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_organizacao_atividades', 'Lista atividades de uma organizacao', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_organizacao_deals', 'Lista deals de uma organizacao', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_organizacao_arquivos', 'Lista arquivos de uma organizacao', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_organizacao_contatos', 'Lista contatos de uma organizacao', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),

        # ── Deals (extend) ──────────────────────────────────────────────
        _t('pipedrive_deals_merge', 'Merge dois deals em um', {
            'id': {'type': 'string', 'description': 'ID do deal que permanece'},
            'merge_with_id': {'type': 'string', 'description': 'ID do deal a ser mesclado'},
        }, ['id', 'merge_with_id']),
        _t('pipedrive_deal_seguidores', 'Lista seguidores de um deal', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_deal_seguidor_adicionar', 'Adiciona seguidor a um deal', {
            'id': {'type': 'string'}, 'user_id': {'type': 'integer'},
        }, ['id', 'user_id']),
        _t('pipedrive_deal_participantes', 'Lista participantes de um deal', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_deal_participante_adicionar', 'Adiciona participante (person) a um deal', {
            'id': {'type': 'string'}, 'person_id': {'type': 'integer'},
        }, ['id', 'person_id']),
        _t('pipedrive_deal_participante_excluir', 'Remove participante de um deal', {
            'deal_id': {'type': 'string'}, 'participant_id': {'type': 'integer'},
        }, ['deal_id', 'participant_id']),
        _t('pipedrive_deal_atualizacoes', 'Lista atualizacoes/flow de um deal', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_deal_arquivos', 'Lista arquivos de um deal', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_deal_atividades', 'Lista atividades de um deal', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_deal_produtos', 'Lista produtos de um deal', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_deal_produto_adicionar', 'Adiciona produto a um deal', {
            'id': {'type': 'string'}, 'product_id': {'type': 'integer'},
            'item_price': {'type': 'number'}, 'quantity': {'type': 'integer', 'default': 1},
        }, ['id', 'product_id', 'item_price']),
        _t('pipedrive_deal_produto_atualizar', 'Atualiza produto vinculado a um deal', {
            'deal_id': {'type': 'string'}, 'product_attachment_id': {'type': 'integer'},
            'item_price': {'type': 'number'}, 'quantity': {'type': 'integer'},
        }, ['deal_id', 'product_attachment_id']),
        _t('pipedrive_deal_produto_excluir', 'Remove produto de um deal', {
            'deal_id': {'type': 'string'}, 'product_attachment_id': {'type': 'integer'},
        }, ['deal_id', 'product_attachment_id']),
        _t('pipedrive_deal_emails', 'Lista emails vinculados a um deal', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),

        # ── Activities (extend) ─────────────────────────────────────────
        _t('pipedrive_atividade_detalhar', 'Detalhes de uma atividade', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_atividade_atualizar', 'Atualiza atividade', {
            'id': {'type': 'string'}, 'subject': {'type': 'string'},
            'done': {'type': 'boolean'}, 'due_date': {'type': 'string'},
            'type': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_atividade_excluir', 'Exclui atividade', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_tipos_atividade', 'Lista tipos de atividade disponiveis', {}),

        # ── Files ───────────────────────────────────────────────────────
        _t('pipedrive_arquivos_listar', 'Lista arquivos do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_arquivo_detalhar', 'Detalhes de um arquivo', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_arquivo_excluir', 'Exclui arquivo', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Filters (extend) ───────────────────────────────────────────
        _t('pipedrive_filtro_criar', 'Cria filtro salvo no Pipedrive', {
            'name': {'type': 'string'}, 'type': {'type': 'string', 'description': 'deals, persons, orgs, etc'},
            'conditions': {'type': 'object', 'description': 'Objeto de condicoes do filtro'},
        }, ['name', 'type', 'conditions']),
        _t('pipedrive_filtro_detalhar', 'Detalhes de um filtro', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_filtro_atualizar', 'Atualiza filtro salvo', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
            'conditions': {'type': 'object'},
        }, ['id']),
        _t('pipedrive_filtro_excluir', 'Exclui filtro salvo', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Call Logs ───────────────────────────────────────────────────
        _t('pipedrive_call_logs_listar', 'Lista call logs do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_call_log_criar', 'Cria registro de ligacao', {
            'subject': {'type': 'string'}, 'duration': {'type': 'integer', 'description': 'Duracao em segundos'},
            'outcome': {'type': 'string', 'description': 'connected, no_answer, left_message, left_voicemail, wrong_number, busy'},
            'to_phone': {'type': 'string'}, 'from_phone': {'type': 'string'},
            'deal_id': {'type': 'integer'}, 'person_id': {'type': 'integer'}, 'org_id': {'type': 'integer'},
        }, ['subject', 'duration', 'outcome', 'to_phone']),
        _t('pipedrive_call_log_detalhar', 'Detalhes de um call log', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_call_log_excluir', 'Exclui call log', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Mailbox ─────────────────────────────────────────────────────
        _t('pipedrive_email_threads_listar', 'Lista threads de email do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
            'folder': {'type': 'string', 'default': 'inbox', 'description': 'inbox, drafts, sent, archive'},
        }),
        _t('pipedrive_email_mensagens_listar', 'Lista mensagens de uma thread de email', {
            'thread_id': {'type': 'string'},
        }, ['thread_id']),
        _t('pipedrive_email_mensagem_detalhar', 'Detalhes de uma mensagem de email', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Custom Fields ──────────────────────────────────────────────
        _t('pipedrive_deal_fields', 'Lista campos customizados de deals', {}),
        _t('pipedrive_person_fields', 'Lista campos customizados de contatos', {}),
        _t('pipedrive_org_fields', 'Lista campos customizados de organizacoes', {}),
        _t('pipedrive_activity_fields', 'Lista campos de atividades', {}),
        _t('pipedrive_product_fields', 'Lista campos customizados de produtos', {}),

        # ── Products (extend) ──────────────────────────────────────────
        _t('pipedrive_produto_atualizar', 'Atualiza produto no Pipedrive', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
            'code': {'type': 'string'}, 'unit': {'type': 'string'},
            'price': {'type': 'number'},
        }, ['id']),
        _t('pipedrive_produto_excluir', 'Exclui produto do Pipedrive', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_produto_deals', 'Lista deals vinculados a um produto', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_produto_arquivos', 'Lista arquivos de um produto', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),

        # ── Roles ──────────────────────────────────────────────────────
        _t('pipedrive_roles_listar', 'Lista roles/papeis do Pipedrive', {}),
        _t('pipedrive_role_criar', 'Cria role/papel no Pipedrive', {
            'name': {'type': 'string'}, 'parent_role_id': {'type': 'integer'},
        }, ['name']),
        _t('pipedrive_role_detalhar', 'Detalhes de um role', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_role_atualizar', 'Atualiza nome de um role', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
        }, ['id', 'name']),
        _t('pipedrive_role_excluir', 'Exclui role', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_role_atribuicoes', 'Lista usuarios atribuidos a um role', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Recents ────────────────────────────────────────────────────
        _t('pipedrive_recentes', 'Lista itens recentes/alterados desde timestamp', {
            'since_timestamp': {'type': 'string', 'description': 'YYYY-MM-DD HH:MM:SS'},
            'items': {'type': 'string', 'default': 'deal', 'description': 'deal, person, organization, activity, etc'},
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['since_timestamp']),

        # ── Item Search ────────────────────────────────────────────────
        _t('pipedrive_buscar', 'Busca global em deals, contatos, orgs, etc', {
            'term': {'type': 'string'}, 'item_types': {'type': 'string', 'default': 'deal', 'description': 'deal, person, organization, product, file'},
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['term']),

        # ── Notes (extend) ─────────────────────────────────────────────
        _t('pipedrive_nota_detalhar', 'Detalhes de uma nota', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_nota_atualizar', 'Atualiza conteudo de uma nota', {
            'id': {'type': 'string'}, 'content': {'type': 'string'},
        }, ['id', 'content']),
        _t('pipedrive_nota_excluir', 'Exclui nota', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Users (extend) ─────────────────────────────────────────────
        _t('pipedrive_usuario_detalhar', 'Detalhes de um usuario', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Currencies ─────────────────────────────────────────────────
        _t('pipedrive_moedas_listar', 'Lista moedas suportadas pelo Pipedrive', {}),

        # ── Pipelines (extend) ─────────────────────────────────────────
        _t('pipedrive_pipeline_detalhar', 'Detalhes de um pipeline/funil', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_pipeline_deals', 'Lista deals de um pipeline', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),
        _t('pipedrive_pipeline_criar', 'Cria pipeline/funil no Pipedrive', {
            'name': {'type': 'string'}, 'deal_probability': {'type': 'integer', 'default': 1},
            'active': {'type': 'boolean', 'default': True},
        }, ['name']),
        _t('pipedrive_pipeline_atualizar', 'Atualiza pipeline/funil', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
            'deal_probability': {'type': 'integer'}, 'active': {'type': 'boolean'},
        }, ['id']),
        _t('pipedrive_pipeline_excluir', 'Exclui pipeline/funil', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Stages (extend) ────────────────────────────────────────────
        _t('pipedrive_stage_detalhar', 'Detalhes de uma etapa/stage', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_stage_criar', 'Cria etapa/stage em um pipeline', {
            'name': {'type': 'string'}, 'pipeline_id': {'type': 'integer'},
            'order_nr': {'type': 'integer'},
        }, ['name', 'pipeline_id']),
        _t('pipedrive_stage_atualizar', 'Atualiza etapa/stage', {
            'id': {'type': 'string'}, 'name': {'type': 'string'},
            'order_nr': {'type': 'integer'}, 'pipeline_id': {'type': 'integer'},
        }, ['id']),
        _t('pipedrive_stage_excluir', 'Exclui etapa/stage', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_stage_deals', 'Lista deals de uma etapa/stage', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),

        # ── Lead Sources ───────────────────────────────────────────────
        _t('pipedrive_lead_sources', 'Lista fontes de leads disponiveis', {}),

        # ── Person emails ──────────────────────────────────────────────
        _t('pipedrive_contato_emails', 'Lista emails vinculados a um contato', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),

        # ── Org emails ─────────────────────────────────────────────────
        _t('pipedrive_organizacao_emails', 'Lista emails vinculados a uma organizacao', {
            'id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }, ['id']),

        # ── Subscriptions (recurring revenue) ──────────────────────────
        _t('pipedrive_subscriptions_listar', 'Lista subscriptions/receita recorrente do Pipedrive', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_subscription_detalhar', 'Detalhes de uma subscription', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_subscription_criar', 'Cria subscription recorrente no Pipedrive', {
            'body': {'type': 'object', 'description': 'Corpo da subscription (deal_id, currency, cadence_type, etc)'},
        }, ['body']),
        _t('pipedrive_subscription_atualizar', 'Atualiza subscription recorrente', {
            'id': {'type': 'string'},
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _t('pipedrive_subscription_excluir', 'Exclui/cancela subscription', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_subscription_payments', 'Lista pagamentos de uma subscription', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_subscription_deal', 'Busca subscription vinculada a um deal', {
            'deal_id': {'type': 'string'},
        }, ['deal_id']),

        # ── Projects (beta) ────────────────────────────────────────────
        _t('pipedrive_projects_listar', 'Lista projects do Pipedrive (beta)', {
            'limit': {'type': 'integer', 'default': 50},
            'start': {'type': 'integer', 'default': 0},
        }),
        _t('pipedrive_project_criar', 'Cria project no Pipedrive', {
            'body': {'type': 'object', 'description': 'Corpo do project (title, board_id, phase_id, etc)'},
        }, ['body']),
        _t('pipedrive_project_detalhar', 'Detalhes de um project', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_project_atualizar', 'Atualiza project', {
            'id': {'type': 'string'},
            'body': {'type': 'object', 'description': 'Campos a atualizar'},
        }, ['id', 'body']),
        _t('pipedrive_project_excluir', 'Exclui project', {
            'id': {'type': 'string'},
        }, ['id']),
        _t('pipedrive_project_tasks', 'Lista tasks de um project', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Meetings (scheduling) ──────────────────────────────────────
        _t('pipedrive_meetings_providers', 'Lista providers de meeting vinculados a usuarios', {}),
        _t('pipedrive_meetings_provider_criar', 'Vincula provider de meeting a usuario', {
            'body': {'type': 'object', 'description': 'Corpo do provider link (user_id, provider, etc)'},
        }, ['body']),
        _t('pipedrive_meetings_provider_excluir', 'Remove vinculo de provider de meeting', {
            'id': {'type': 'string'},
        }, ['id']),

        # ── Changelogs ─────────────────────────────────────────────────
        _t('pipedrive_changelogs', 'Lista changelogs do Pipedrive', {}),
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
        # Deals
        case 'pipedrive_deals_listar':
            return c.list_deals(status=args.get('status', 'open'), limit=args.get('limit', 50), page=args.get('page', 1))
        case 'pipedrive_deal_detalhar':
            return c.get_deal(args['id'])
        case 'pipedrive_deal_criar':
            return c.create_deal(title=args['title'], amount=args.get('amount'), pipeline=args.get('pipeline'))
        case 'pipedrive_deal_atualizar':
            return c.update_deal(args['id'], amount=args.get('amount'), close_date=args.get('close_date'))
        case 'pipedrive_deal_mover':
            return c.move_deal(args['id'], args['to_stage'])
        case 'pipedrive_deal_nota':
            return c.add_deal_note(args['id'], args['note'])
        case 'pipedrive_deal_ganho':
            return c.mark_deal_won(args['id'])
        case 'pipedrive_deal_perdido':
            return c.mark_deal_lost(args['id'], reason=args.get('reason', ''))
        case 'pipedrive_deal_excluir':
            return c.delete_deal(args['id'])
        # Persons
        case 'pipedrive_contatos_listar':
            return c.list_persons(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_contato_detalhar':
            return c.get_person(args['id'])
        case 'pipedrive_contato_criar':
            return c.create_person(name=args['name'], email=args.get('email'), phone=args.get('phone'), org_id=args.get('org_id'))
        case 'pipedrive_contato_atualizar':
            return c.update_person(args['id'], name=args.get('name'), email=args.get('email'), phone=args.get('phone'))
        case 'pipedrive_contato_excluir':
            return c.delete_person(args['id'])
        # Organizations
        case 'pipedrive_organizacoes_listar':
            return c.list_organizations(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_organizacao_detalhar':
            return c.get_organization(args['id'])
        case 'pipedrive_organizacao_criar':
            return c.create_organization(name=args['name'], address=args.get('address'))
        case 'pipedrive_organizacao_atualizar':
            return c.update_organization(args['id'], name=args.get('name'), address=args.get('address'))
        case 'pipedrive_organizacao_excluir':
            return c.delete_organization(args['id'])
        # Activities
        case 'pipedrive_atividades_listar':
            return c.list_activities(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_atividade_criar':
            return c.create_activity(subject=args['subject'], type=args.get('type', 'task'),
                                     due_date=args.get('due_date'), deal_id=args.get('deal_id'), person_id=args.get('person_id'))
        # Products
        case 'pipedrive_produtos_listar':
            return c.list_products(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_produto_detalhar':
            return c.get_product(args['id'])
        case 'pipedrive_produto_criar':
            return c.create_product(name=args['name'], code=args.get('code'), unit=args.get('unit'), price=args.get('price'))
        # Pipelines
        case 'pipedrive_pipelines_listar':
            return c.list_pipelines()
        # Stages
        case 'pipedrive_stages_listar':
            return c.list_stages(pipeline_id=args.get('pipeline_id'))
        # Notes
        case 'pipedrive_notas_listar':
            return c.list_notes(deal_id=args.get('deal_id'), person_id=args.get('person_id'),
                                limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_nota_criar':
            return c.create_note(content=args['content'], deal_id=args.get('deal_id'),
                                 person_id=args.get('person_id'), org_id=args.get('org_id'))
        # Users
        case 'pipedrive_usuarios_listar':
            return c.list_users()
        # Webhooks
        case 'pipedrive_webhooks_listar':
            return c.list_webhooks()
        case 'pipedrive_webhook_criar':
            return c.create_webhook(args['subscription_url'], args['event_action'], args['event_object'])
        case 'pipedrive_webhook_excluir':
            return c.delete_webhook(args['id'])
        # Goals
        case 'pipedrive_goals_listar':
            return c.list_goals()
        # Filters
        case 'pipedrive_filtros_listar':
            return c.list_filters(type=args.get('type'))
        # Empresa
        case 'pipedrive_empresa':
            return c.company_info()
        # Leads
        case 'pipedrive_leads_listar':
            return c.list_leads(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_lead_detalhar':
            return c.get_lead(args['id'])
        case 'pipedrive_lead_criar':
            return c.create_lead(title=args['title'], person_id=args.get('person_id'),
                                 organization_id=args.get('organization_id'), value=args.get('value'))
        case 'pipedrive_lead_atualizar':
            return c.update_lead(args['id'], title=args.get('title'), label_ids=args.get('label_ids'))
        case 'pipedrive_lead_excluir':
            return c.delete_lead(args['id'])
        # Lead Labels
        case 'pipedrive_lead_labels_listar':
            return c.list_lead_labels()
        case 'pipedrive_lead_label_criar':
            return c.create_lead_label(name=args['name'], color=args.get('color', 'blue'))
        case 'pipedrive_lead_label_atualizar':
            return c.update_lead_label(args['id'], name=args.get('name'), color=args.get('color'))
        case 'pipedrive_lead_label_excluir':
            return c.delete_lead_label(args['id'])
        # Persons (extend)
        case 'pipedrive_contatos_merge':
            return c.merge_persons(args['id'], args['merge_with_id'])
        case 'pipedrive_contato_seguidores_listar':
            return c.list_person_followers(args['id'])
        case 'pipedrive_contato_seguidor_adicionar':
            return c.add_person_follower(args['id'], args['user_id'])
        case 'pipedrive_contato_seguidor_excluir':
            return c.delete_person_follower(args['id'], args['follower_id'])
        case 'pipedrive_contato_atualizacoes':
            return c.list_person_updates(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_contato_atividades':
            return c.list_person_activities(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_contato_deals':
            return c.list_person_deals(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_contato_arquivos':
            return c.list_person_files(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        # Organizations (extend)
        case 'pipedrive_organizacoes_merge':
            return c.merge_organizations(args['id'], args['merge_with_id'])
        case 'pipedrive_organizacao_seguidores':
            return c.list_org_followers(args['id'])
        case 'pipedrive_organizacao_seguidor_adicionar':
            return c.add_org_follower(args['id'], args['user_id'])
        case 'pipedrive_organizacao_atualizacoes':
            return c.list_org_updates(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_organizacao_atividades':
            return c.list_org_activities(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_organizacao_deals':
            return c.list_org_deals(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_organizacao_arquivos':
            return c.list_org_files(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_organizacao_contatos':
            return c.list_org_persons(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        # Deals (extend)
        case 'pipedrive_deals_merge':
            return c.merge_deals(args['id'], args['merge_with_id'])
        case 'pipedrive_deal_seguidores':
            return c.list_deal_followers(args['id'])
        case 'pipedrive_deal_seguidor_adicionar':
            return c.add_deal_follower(args['id'], args['user_id'])
        case 'pipedrive_deal_participantes':
            return c.list_deal_participants(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_deal_participante_adicionar':
            return c.add_deal_participant(args['id'], args['person_id'])
        case 'pipedrive_deal_participante_excluir':
            return c.delete_deal_participant(args['deal_id'], args['participant_id'])
        case 'pipedrive_deal_atualizacoes':
            return c.list_deal_updates(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_deal_arquivos':
            return c.list_deal_files(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_deal_atividades':
            return c.list_deal_activities(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_deal_produtos':
            return c.list_deal_products(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_deal_produto_adicionar':
            return c.add_deal_product(args['id'], args['product_id'], args['item_price'], quantity=args.get('quantity', 1))
        case 'pipedrive_deal_produto_atualizar':
            return c.update_deal_product(args['deal_id'], args['product_attachment_id'],
                                         item_price=args.get('item_price'), quantity=args.get('quantity'))
        case 'pipedrive_deal_produto_excluir':
            return c.delete_deal_product(args['deal_id'], args['product_attachment_id'])
        case 'pipedrive_deal_emails':
            return c.list_deal_mail_messages(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        # Activities (extend)
        case 'pipedrive_atividade_detalhar':
            return c.get_activity(args['id'])
        case 'pipedrive_atividade_atualizar':
            return c.update_activity(args['id'], subject=args.get('subject'), done=args.get('done'),
                                     due_date=args.get('due_date'), type=args.get('type'))
        case 'pipedrive_atividade_excluir':
            return c.delete_activity(args['id'])
        case 'pipedrive_tipos_atividade':
            return c.list_activity_types()
        # Files
        case 'pipedrive_arquivos_listar':
            return c.list_files(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_arquivo_detalhar':
            return c.get_file(args['id'])
        case 'pipedrive_arquivo_excluir':
            return c.delete_file(args['id'])
        # Filters (extend)
        case 'pipedrive_filtro_criar':
            return c.create_filter(name=args['name'], type=args['type'], conditions=args['conditions'])
        case 'pipedrive_filtro_detalhar':
            return c.get_filter(args['id'])
        case 'pipedrive_filtro_atualizar':
            return c.update_filter(args['id'], name=args.get('name'), conditions=args.get('conditions'))
        case 'pipedrive_filtro_excluir':
            return c.delete_filter(args['id'])
        # Call Logs
        case 'pipedrive_call_logs_listar':
            return c.list_call_logs(limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_call_log_criar':
            return c.create_call_log(subject=args['subject'], duration=args['duration'], outcome=args['outcome'],
                                     to_phone=args['to_phone'], from_phone=args.get('from_phone', ''),
                                     deal_id=args.get('deal_id'), person_id=args.get('person_id'), org_id=args.get('org_id'))
        case 'pipedrive_call_log_detalhar':
            return c.get_call_log(args['id'])
        case 'pipedrive_call_log_excluir':
            return c.delete_call_log(args['id'])
        # Mailbox
        case 'pipedrive_email_threads_listar':
            return c.list_mail_threads(limit=args.get('limit', 50), start=args.get('start', 0), folder=args.get('folder', 'inbox'))
        case 'pipedrive_email_mensagens_listar':
            return c.list_mail_messages(args['thread_id'])
        case 'pipedrive_email_mensagem_detalhar':
            return c.get_mail_message(args['id'])
        # Custom Fields
        case 'pipedrive_deal_fields':
            return c.list_deal_fields()
        case 'pipedrive_person_fields':
            return c.list_person_fields()
        case 'pipedrive_org_fields':
            return c.list_org_fields()
        case 'pipedrive_activity_fields':
            return c.list_activity_fields()
        case 'pipedrive_product_fields':
            return c.list_product_fields()
        # Products (extend)
        case 'pipedrive_produto_atualizar':
            return c.update_product(args['id'], name=args.get('name'), code=args.get('code'),
                                    unit=args.get('unit'), price=args.get('price'))
        case 'pipedrive_produto_excluir':
            return c.delete_product(args['id'])
        case 'pipedrive_produto_deals':
            return c.list_product_deals(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_produto_arquivos':
            return c.list_product_files(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        # Roles
        case 'pipedrive_roles_listar':
            return c.list_roles()
        case 'pipedrive_role_criar':
            return c.create_role(name=args['name'], parent_role_id=args.get('parent_role_id'))
        case 'pipedrive_role_detalhar':
            return c.get_role(args['id'])
        case 'pipedrive_role_atualizar':
            return c.update_role(args['id'], name=args['name'])
        case 'pipedrive_role_excluir':
            return c.delete_role(args['id'])
        case 'pipedrive_role_atribuicoes':
            return c.list_role_assignments(args['id'])
        # Recents
        case 'pipedrive_recentes':
            return c.get_recents(since_timestamp=args['since_timestamp'], items=args.get('items', 'deal'),
                                 limit=args.get('limit', 50), start=args.get('start', 0))
        # Item Search
        case 'pipedrive_buscar':
            return c.search_items(term=args['term'], item_types=args.get('item_types', 'deal'),
                                  limit=args.get('limit', 50), start=args.get('start', 0))
        # Notes (extend)
        case 'pipedrive_nota_detalhar':
            return c.get_note(args['id'])
        case 'pipedrive_nota_atualizar':
            return c.update_note(args['id'], content=args['content'])
        case 'pipedrive_nota_excluir':
            return c.delete_note(args['id'])
        # Users (extend)
        case 'pipedrive_usuario_detalhar':
            return c.get_user(args['id'])
        # Currencies
        case 'pipedrive_moedas_listar':
            return c.list_currencies()
        # Pipelines (extend)
        case 'pipedrive_pipeline_detalhar':
            return c.get_pipeline(args['id'])
        case 'pipedrive_pipeline_deals':
            return c.get_pipeline_deals(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        case 'pipedrive_pipeline_criar':
            return c.create_pipeline(name=args['name'], deal_probability=args.get('deal_probability', 1),
                                     active=args.get('active', True))
        case 'pipedrive_pipeline_atualizar':
            return c.update_pipeline(args['id'], name=args.get('name'), deal_probability=args.get('deal_probability'),
                                     active=args.get('active'))
        case 'pipedrive_pipeline_excluir':
            return c.delete_pipeline(args['id'])
        # Stages (extend)
        case 'pipedrive_stage_detalhar':
            return c.get_stage(args['id'])
        case 'pipedrive_stage_criar':
            return c.create_stage(name=args['name'], pipeline_id=args['pipeline_id'], order_nr=args.get('order_nr'))
        case 'pipedrive_stage_atualizar':
            return c.update_stage(args['id'], name=args.get('name'), order_nr=args.get('order_nr'),
                                  pipeline_id=args.get('pipeline_id'))
        case 'pipedrive_stage_excluir':
            return c.delete_stage(args['id'])
        case 'pipedrive_stage_deals':
            return c.list_stage_deals(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        # Lead Sources
        case 'pipedrive_lead_sources':
            return c.list_lead_sources()
        # Person emails
        case 'pipedrive_contato_emails':
            return c.list_person_mail_messages(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        # Org emails
        case 'pipedrive_organizacao_emails':
            return c.list_org_mail_messages(args['id'], limit=args.get('limit', 50), start=args.get('start', 0))
        # Subscriptions
        case 'pipedrive_subscriptions_listar':
            return c._get("subscriptions", {"limit": args.get("limit", 50), "start": args.get("start", 0)})
        case 'pipedrive_subscription_detalhar':
            return c._get(f"subscriptions/{args['id']}")
        case 'pipedrive_subscription_criar':
            return c._post_json("subscriptions/recurring", args.get('body', {}))
        case 'pipedrive_subscription_atualizar':
            return c._put(f"subscriptions/recurring/{args['id']}", args.get('body', {}))
        case 'pipedrive_subscription_excluir':
            return c._delete(f"subscriptions/{args['id']}")
        case 'pipedrive_subscription_payments':
            return c._get(f"subscriptions/{args['id']}/payments")
        case 'pipedrive_subscription_deal':
            return c._get(f"subscriptions/find/{args['deal_id']}")
        # Projects
        case 'pipedrive_projects_listar':
            return c._get("projects", {"limit": args.get("limit", 50), "start": args.get("start", 0)})
        case 'pipedrive_project_criar':
            return c._post_json("projects", args.get('body', {}))
        case 'pipedrive_project_detalhar':
            return c._get(f"projects/{args['id']}")
        case 'pipedrive_project_atualizar':
            return c._put(f"projects/{args['id']}", args.get('body', {}))
        case 'pipedrive_project_excluir':
            return c._delete(f"projects/{args['id']}")
        case 'pipedrive_project_tasks':
            return c._get(f"projects/{args['id']}/tasks")
        # Meetings
        case 'pipedrive_meetings_providers':
            return c._get("meetings/userProviderLinks")
        case 'pipedrive_meetings_provider_criar':
            return c._post_json("meetings/userProviderLinks", args.get('body', {}))
        case 'pipedrive_meetings_provider_excluir':
            return c._delete(f"meetings/userProviderLinks/{args['id']}")
        # Changelogs
        case 'pipedrive_changelogs':
            return c._get("changelogs")
        case _:
            raise ValueError(f'Tool desconhecida: {name}')


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == '__main__':
    asyncio.run(main())
