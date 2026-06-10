#!/usr/bin/env python3
"""
MCP server para Holdprint (Holdworks) ERP — gráfica/impressão.
Tools: saldo (sem endpoint, retorna 0), contas a pagar/receber, vencidos,
projeção de caixa, dashboard, clientes, fornecedores, orçamentos, jobs.
Docs: https://docs.holdworks.ai  •  Base: https://api.holdworks.ai  •  Auth: x-api-key
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'scripts'))
sys.path.insert(0, str(Path(__file__).parent.parent / '_lib'))
from holdprint_client import HoldprintClient

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server('holdprint')
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = HoldprintClient()
    return _client


def _schema(props: dict, required: list | None = None):
    return {'type': 'object', 'properties': props, 'required': required or []}


_PAGINATED = {
    'limit': {'type': 'integer', 'description': 'Registros por página (default 50, máx 100)', 'default': 50},
    'page': {'type': 'integer', 'description': 'Página (default 1)', 'default': 1},
}
_DATE_RANGE = {
    'from_date': {'type': 'string', 'description': 'Data inicial YYYY-MM-DD (default: -365d)'},
    'to_date': {'type': 'string', 'description': 'Data final YYYY-MM-DD (default: +365d)'},
}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name='holdprint_saldo',
                   description='Saldo (Holdprint não expõe saldo bancário — retorna 0 + nota; use projeção)',
                   inputSchema=_schema({})),
        types.Tool(name='holdprint_contas_pagar',
                   description='Contas a pagar (despesas) do Holdprint, com filtro de data/status',
                   inputSchema=_schema({**_DATE_RANGE, **_PAGINATED,
                                        'status': {'type': 'string', 'description': 'pending|paid|overdue|cancelled'}})),
        types.Tool(name='holdprint_contas_receber',
                   description='Contas a receber (receitas) do Holdprint, com filtro de data/status',
                   inputSchema=_schema({**_DATE_RANGE, **_PAGINATED,
                                        'status': {'type': 'string', 'description': 'pending|received|overdue|cancelled'}})),
        types.Tool(name='holdprint_vencidos',
                   description='Contas vencidas (a pagar + a receber em atraso)',
                   inputSchema=_schema({})),
        types.Tool(name='holdprint_projecao_caixa',
                   description='Projeção de fluxo de caixa para N dias (entradas - saídas previstas)',
                   inputSchema=_schema({'days': {'type': 'integer', 'description': 'Horizonte em dias (default 30)', 'default': 30}})),
        types.Tool(name='holdprint_dashboard',
                   description='KPIs financeiros consolidados (saldo, a receber, a pagar, vencidos, projeção)',
                   inputSchema=_schema({})),
        types.Tool(name='holdprint_clientes',
                   description='Lista clientes cadastrados no Holdprint',
                   inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='holdprint_fornecedores',
                   description='Lista fornecedores cadastrados no Holdprint',
                   inputSchema=_schema({**_PAGINATED})),
        types.Tool(name='holdprint_orcamentos',
                   description='Lista orçamentos do Holdprint',
                   inputSchema=_schema({**_DATE_RANGE, **_PAGINATED})),
        types.Tool(name='holdprint_jobs',
                   description='Lista jobs de produção do Holdprint',
                   inputSchema=_schema({**_DATE_RANGE, **_PAGINATED})),
    ]


def _dispatch(name: str, a: dict):
    c = _get_client()
    limit = int(a.get('limit', 50))
    page = int(a.get('page', 1))
    fd, td = a.get('from_date'), a.get('to_date')
    if name == 'holdprint_saldo':
        return c.get_balance()
    if name == 'holdprint_contas_pagar':
        r = c.list_payables(from_date=fd, to_date=td, limit=limit, page=page)
        if a.get('status'):
            r['items'] = [i for i in r['items'] if i.get('status') == a['status']]
        return r
    if name == 'holdprint_contas_receber':
        r = c.list_receivables(from_date=fd, to_date=td, limit=limit, page=page)
        if a.get('status'):
            r['items'] = [i for i in r['items'] if i.get('status') == a['status']]
        return r
    if name == 'holdprint_vencidos':
        return c.list_overdue()
    if name == 'holdprint_projecao_caixa':
        return c.get_cash_projection(days=int(a.get('days', 30)))
    if name == 'holdprint_dashboard':
        return c.get_dashboard_metrics()
    if name == 'holdprint_clientes':
        return c.list_customers(limit=limit, page=page)
    if name == 'holdprint_fornecedores':
        return c.list_suppliers(limit=limit, page=page)
    if name == 'holdprint_orcamentos':
        return c.list_budgets(from_date=fd, to_date=td, limit=limit, page=page)
    if name == 'holdprint_jobs':
        return c.list_jobs(from_date=fd, to_date=td, limit=limit, page=page)
    return {'error': f'tool desconhecida: {name}'}


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = _dispatch(name, arguments or {})
        return [types.TextContent(type='text', text=json.dumps(result, ensure_ascii=False, default=str))]
    except Exception as e:
        return [types.TextContent(type='text', text=json.dumps({'error': str(e)}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
