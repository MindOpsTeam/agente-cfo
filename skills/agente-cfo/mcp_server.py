#!/usr/bin/env python3
"""
MCP server para skill agente-cfo — 14 tools tipadas.

Wrappeia erp_gateway.py, crm_gateway.py, cobranca_gateway.py e os helpers
panel_post_reply.sh / panel_write_event.sh via subprocess. Marcos pode chamar
via protocolo MCP (schema JSON validado) em vez de bash shell-out direto.

Tools expostas (prefixo cfo_):
  Leitura:  cfo_get_balance, cfo_list_payables, cfo_list_receivables,
            cfo_list_overdue, cfo_get_cash_projection, cfo_company_info
  Write ERP: cfo_create_payable, cfo_create_receivable, cfo_pay_payable,
             cfo_mark_received, cfo_cancel_payable, cfo_update_category
  Canal:    cfo_write_event, cfo_post_reply
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── Caminhos ──────────────────────────────────────────────────────────────────

SKILL_DIR   = Path(__file__).parent
SCRIPTS_DIR = SKILL_DIR / "scripts"

# Caminho do Python do venv (mesmo usado pelas demais skills)
_venv_py = Path.home() / ".openclaw" / "workspace" / ".venv" / "bin" / "python3"
if not _venv_py.exists():
    # Fallback: venv do repo de dev
    _venv_py = Path(__file__).parent.parent.parent / ".venv" / "bin" / "python3"
PYTHON = str(_venv_py) if _venv_py.exists() else sys.executable

# ── Helpers de execução ───────────────────────────────────────────────────────

def _run_erp(cmd_args: list[str]) -> dict:
    """Chama erp_gateway.py com os args dados. Retorna dict JSON."""
    result = subprocess.run(
        [PYTHON, str(SCRIPTS_DIR / "erp_gateway.py")] + cmd_args,
        capture_output=True, text=True, timeout=60,
        cwd=str(SCRIPTS_DIR),
    )
    raw = result.stdout.strip() or result.stderr.strip()
    try:
        return json.loads(raw) if raw else {"error": "sem resposta do erp_gateway"}
    except json.JSONDecodeError:
        return {"error": "resposta não-JSON do erp_gateway", "raw": raw[:500]}


def _run_sh(script: str, *args: str) -> dict:
    """Chama um script shell e devolve {ok, output, error}."""
    path = SCRIPTS_DIR / script
    if not path.exists():
        return {"error": f"Script não encontrado: {path}"}
    try:
        result = subprocess.run(
            ["bash", str(path)] + list(args),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return {"ok": True, "output": result.stdout.strip()}
        return {"ok": False, "error": result.stderr.strip() or result.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"error": "timeout ao executar script"}
    except Exception as e:
        return {"error": str(e)}


def _tool_result(data: dict) -> list[types.TextContent]:
    """Serializa um dict para list[TextContent]."""
    return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]


def _err_result(msg: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps({"error": msg}))]


# ── Server ────────────────────────────────────────────────────────────────────

server = Server("agente-cfo")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Leitura ERP ──────────────────────────────────────────────────────
        types.Tool(
            name="cfo_get_balance",
            description="Retorna saldo atual do ERP ativo (caixa/conta corrente).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="cfo_list_payables",
            description="Lista contas a pagar do ERP ativo com filtro de datas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "Data início (YYYY-MM-DD)"},
                    "to_date":   {"type": "string", "description": "Data fim (YYYY-MM-DD)"},
                    "limit":     {"type": "integer", "description": "Máx de registros (default 50)", "default": 50},
                    "page":      {"type": "integer", "description": "Página (default 1)", "default": 1},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="cfo_list_receivables",
            description="Lista contas a receber do ERP ativo com filtro de datas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "Data início (YYYY-MM-DD)"},
                    "to_date":   {"type": "string", "description": "Data fim (YYYY-MM-DD)"},
                    "limit":     {"type": "integer", "description": "Máx de registros (default 50)", "default": 50},
                    "page":      {"type": "integer", "description": "Página (default 1)", "default": 1},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="cfo_list_overdue",
            description="Lista todas as contas vencidas (em atraso) do ERP ativo.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="cfo_get_cash_projection",
            description="Retorna projeção de caixa para os próximos N dias.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Horizonte em dias (default 30)", "default": 30},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="cfo_company_info",
            description="Retorna dados cadastrais da empresa no ERP ativo.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # ── Write ERP ────────────────────────────────────────────────────────
        types.Tool(
            name="cfo_create_payable",
            description=(
                "Cria uma conta a pagar no ERP ativo. REQUER confirmação prévia do dono. "
                "Retorna {success, id} ou {error}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "amount":    {"type": "number",  "description": "Valor em BRL (ex: 50.00)"},
                    "due_date":  {"type": "string",  "description": "Vencimento YYYY-MM-DD"},
                    "supplier":  {"type": "string",  "description": "Nome do fornecedor/credor"},
                    "category":  {"type": "string",  "description": "Categoria (ex: Transporte)"},
                },
                "required": ["amount", "due_date", "supplier"],
            },
        ),
        types.Tool(
            name="cfo_create_receivable",
            description=(
                "Cria uma conta a receber no ERP ativo. REQUER confirmação prévia do dono. "
                "Retorna {success, id} ou {error}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "amount":   {"type": "number", "description": "Valor em BRL (ex: 1500.00)"},
                    "due_date": {"type": "string", "description": "Vencimento YYYY-MM-DD"},
                    "customer": {"type": "string", "description": "Nome do cliente/devedor"},
                    "category": {"type": "string", "description": "Categoria (ex: Receita)"},
                },
                "required": ["amount", "due_date", "customer"],
            },
        ),
        types.Tool(
            name="cfo_pay_payable",
            description=(
                "Baixa (marca como pago) uma conta a pagar pelo ID interno do ERP. "
                "REQUER confirmação prévia do dono."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID interno da conta no ERP"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="cfo_mark_received",
            description=(
                "Baixa (marca como recebido) uma conta a receber pelo ID interno. "
                "REQUER confirmação prévia do dono."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID interno da conta no ERP"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="cfo_cancel_payable",
            description=(
                "Cancela uma conta a pagar pelo ID interno. "
                "REQUER confirmação prévia do dono."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID interno da conta no ERP"},
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="cfo_update_category",
            description="Atualiza a categoria de um registro (payable ou receivable) pelo ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id":          {"type": "string", "description": "ID interno do registro no ERP"},
                    "category":    {"type": "string", "description": "Nova categoria"},
                    "record_type": {
                        "type": "string",
                        "enum": ["payable", "receivable"],
                        "description": "Tipo do registro",
                        "default": "payable",
                    },
                },
                "required": ["id", "category"],
            },
        ),
        # ── Canal / Painel ───────────────────────────────────────────────────
        types.Tool(
            name="cfo_write_event",
            description=(
                "Registra um write executado (create_payable, pay_payable, etc.) "
                "na tabela cfo_write_events do painel para auditoria e dedup. "
                "Retorna {ok, id, duplicate}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "channel":    {"type": "string", "description": "Canal de origem (ex: whatsapp:inst)"},
                    "thread_id":  {"type": "string", "description": "ID do thread de conversa"},
                    "action":     {"type": "string", "description": "Ação executada (ex: create_payable)"},
                    "run_id":     {"type": "string", "description": "Run ID do turn"},
                    "erp":        {"type": "string", "description": "Nome do ERP (ex: omie)"},
                    "erp_record_id": {"type": "string", "description": "ID do registro no ERP"},
                    "amount":     {"type": "number", "description": "Valor em BRL"},
                    "supplier":   {"type": "string", "description": "Fornecedor ou cliente"},
                    "due_date":   {"type": "string", "description": "Data de vencimento YYYY-MM-DD"},
                    "category":   {"type": "string", "description": "Categoria do lançamento"},
                    "raw_text":   {"type": "string", "description": "Texto original do usuário"},
                    "status":     {"type": "string", "description": "success | error | duplicate"},
                },
                "required": ["channel", "thread_id", "action"],
            },
        ),
        types.Tool(
            name="cfo_post_reply",
            description=(
                "Envia resposta de Marcos para o canal de origem (WhatsApp, Telegram ou painel) "
                "e grava no histórico do painel. "
                "Use SEMPRE ao terminar um run — é o único ponto de saída de mensagem."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "channel":     {"type": "string", "description": "Canal (ex: whatsapp:inst)"},
                    "external_id": {"type": "string", "description": "Phone / chat_id / user_id"},
                    "reply":       {"type": "string", "description": "Texto da resposta"},
                    "thread_id":   {"type": "string", "description": "Thread ID"},
                    "run_id":      {"type": "string", "description": "Run ID"},
                },
                "required": ["channel", "external_id", "reply", "thread_id", "run_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        match name:

            # ── Leitura ERP ──────────────────────────────────────────────────

            case "cfo_get_balance":
                return _tool_result(_run_erp(["get_balance"]))

            case "cfo_list_payables":
                args = ["list_payables"]
                if arguments.get("from_date"): args += ["--from", arguments["from_date"]]
                if arguments.get("to_date"):   args += ["--to",   arguments["to_date"]]
                if arguments.get("limit"):     args += ["--limit", str(arguments["limit"])]
                if arguments.get("page"):      args += ["--page",  str(arguments["page"])]
                return _tool_result(_run_erp(args))

            case "cfo_list_receivables":
                args = ["list_receivables"]
                if arguments.get("from_date"): args += ["--from", arguments["from_date"]]
                if arguments.get("to_date"):   args += ["--to",   arguments["to_date"]]
                if arguments.get("limit"):     args += ["--limit", str(arguments["limit"])]
                if arguments.get("page"):      args += ["--page",  str(arguments["page"])]
                return _tool_result(_run_erp(args))

            case "cfo_list_overdue":
                return _tool_result(_run_erp(["list_overdue"]))

            case "cfo_get_cash_projection":
                days = str(arguments.get("days", 30))
                return _tool_result(_run_erp(["get_cash_projection", "--days", days]))

            case "cfo_company_info":
                return _tool_result(_run_erp(["company_info"]))

            # ── Write ERP ────────────────────────────────────────────────────

            case "cfo_create_payable":
                args = [
                    "create_payable",
                    "--amount",   str(arguments["amount"]),
                    "--due_date", arguments["due_date"],
                    "--supplier", arguments["supplier"],
                ]
                if arguments.get("category"):
                    args += ["--category", arguments["category"]]
                return _tool_result(_run_erp(args))

            case "cfo_create_receivable":
                args = [
                    "create_receivable",
                    "--amount",   str(arguments["amount"]),
                    "--due_date", arguments["due_date"],
                    "--customer", arguments["customer"],
                ]
                if arguments.get("category"):
                    args += ["--category", arguments["category"]]
                return _tool_result(_run_erp(args))

            case "cfo_pay_payable":
                return _tool_result(_run_erp(["pay_payable", "--id", arguments["id"]]))

            case "cfo_mark_received":
                return _tool_result(_run_erp(["mark_received", "--id", arguments["id"]]))

            case "cfo_cancel_payable":
                return _tool_result(_run_erp(["cancel_payable", "--id", arguments["id"]]))

            case "cfo_update_category":
                args = [
                    "update_category",
                    "--id",       arguments["id"],
                    "--category", arguments["category"],
                ]
                if arguments.get("record_type"):
                    args += ["--record_type", arguments["record_type"]]
                return _tool_result(_run_erp(args))

            # ── Canal / Painel ───────────────────────────────────────────────

            case "cfo_write_event":
                sh_args = [
                    "--action",    arguments["action"],
                    "--thread_id", arguments["thread_id"],
                    "--channel",   arguments["channel"],
                ]
                optional = ["run_id", "erp", "erp_record_id", "supplier",
                            "due_date", "category", "raw_text", "status"]
                for k in optional:
                    if arguments.get(k):
                        sh_args += [f"--{k}", str(arguments[k])]
                if arguments.get("amount") is not None:
                    sh_args += ["--amount", str(arguments["amount"])]
                result = _run_sh("panel_write_event.sh", *sh_args)
                return _tool_result(result)

            case "cfo_post_reply":
                result = _run_sh(
                    "panel_post_reply.sh",
                    arguments["channel"],
                    arguments["external_id"],
                    arguments["reply"],
                    arguments["thread_id"],
                    arguments["run_id"],
                )
                return _tool_result(result)

            case _:
                return _err_result(f"Tool desconhecida: {name}")

    except KeyError as e:
        return _err_result(f"Argumento obrigatório faltando: {e}")
    except subprocess.TimeoutExpired:
        return _err_result("Timeout ao executar comando ERP")
    except Exception as e:
        return _err_result(f"Erro interno: {type(e).__name__}: {e}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
