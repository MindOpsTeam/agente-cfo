#!/usr/bin/env python3
"""Omie ERP API Client — com interface unificada CFO."""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, date, timezone, timedelta

# ── Secrets ──────────────────────────────────────────────────────────────────

def _load_secrets():
    path = os.path.expanduser("~/.openclaw/secrets/omie.env")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

_load_secrets()

APP_KEY = os.environ.get("OMIE_APP_KEY", "")
APP_SECRET = os.environ.get("OMIE_APP_SECRET", "")
BASE_URL = "https://app.omie.com.br/api/v1"


def api_call(endpoint: str, call: str, params: list) -> dict:
    """Make an Omie API call."""
    payload = json.dumps({
        "call": call,
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "param": params
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/{endpoint}/",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}", "detail": body}
    except Exception as e:
        return {"error": str(e)}


# ── Clientes ──────────────────────────────────────────────────────────────────

def clientes_listar(pagina=1, por_pagina=20):
    return api_call("geral/clientes", "ListarClientesResumido", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])


def clientes_buscar(filtro: dict):
    params = {"pagina": 1, "registros_por_pagina": 50}
    if "cnpj_cpf" in filtro:
        params["clientesFiltro"] = {"cnpj_cpf": filtro["cnpj_cpf"]}
    if "codigo" in filtro:
        params["clientesFiltro"] = {"codigo_cliente_omie": int(filtro["codigo"])}
    if "nome" in filtro:
        params["clientesFiltro"] = {"nome_fantasia": filtro["nome"]}
    return api_call("geral/clientes", "ListarClientesResumido", [params])


def clientes_detalhar(codigo: int):
    return api_call("geral/clientes", "ConsultarCliente", [
        {"codigo_cliente_omie": codigo}
    ])


# ── Produtos ──────────────────────────────────────────────────────────────────

def produtos_listar(pagina=1, por_pagina=20):
    return api_call("geral/produtos", "ListarProdutosResumido", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])


def produtos_detalhar(codigo: int):
    return api_call("geral/produtos", "ConsultarProduto", [
        {"codigo_produto": codigo}
    ])


# ── Pedidos de Venda ──────────────────────────────────────────────────────────

def pedidos_listar(pagina=1, por_pagina=20):
    return api_call("produtos/pedido", "ListarPedidos", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])


def pedidos_detalhar(numero: int):
    return api_call("produtos/pedido", "ConsultarPedido", [
        {"numero_pedido": numero}
    ])


def pedidos_status(numero: int):
    return api_call("produtos/pedido", "ConsultarStatusPedido", [
        {"numero_pedido": numero}
    ])


# ── Financeiro ────────────────────────────────────────────────────────────────

def contas_receber(pagina=1, por_pagina=20):
    return api_call("financas/contasreceber", "ListarContasReceber", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])


def contas_pagar(pagina=1, por_pagina=20):
    return api_call("financas/contaspagar", "ListarContasPagar", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])


def resumo_financeiro():
    hoje = datetime.now().strftime("%d/%m/%Y")
    data = api_call("financas/contasreceber", "ListarContasReceber", [
        {"pagina": 1, "registros_por_pagina": 1}
    ])
    return {"data": hoje, "resumo": data}


# ── Notas Fiscais ─────────────────────────────────────────────────────────────

def nfe_listar(pagina=1, por_pagina=20):
    return api_call("produtos/nfe", "ListarNFe", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])


def nfe_detalhar(numero: int):
    return api_call("produtos/nfe", "ConsultarNFe", [
        {"numero_nfe": numero}
    ])


# ── Estoque ───────────────────────────────────────────────────────────────────

def estoque_posicao(pagina=1, por_pagina=20):
    return api_call("estoque/saldo", "ConsultarSaldoEstoque", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])


def estoque_produto(codigo: int):
    return api_call("estoque/saldo", "ConsultarSaldoEstoque", [
        {"codigo_produto": codigo}
    ])


# ── Interface unificada CFO ───────────────────────────────────────────────────
# Mapeamento para o schema comum de todas as skills ERP

def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _map_status_pagar(status_omie: str) -> str:
    if status_omie.upper() in ("PAGO", "LIQUIDADO"):
        return "paid"
    return "pending"


def _map_status_receber(status_omie: str) -> str:
    if status_omie.upper() in ("RECEBIDO", "LIQUIDADO"):
        return "received"
    return "pending"


def unified_get_balance():
    data = resumo_financeiro()
    saldo = 0.0
    if isinstance(data.get("resumo"), dict):
        resumo = data["resumo"]
        if "resumoCaixa" in resumo:
            saldo = float(resumo.get("resumoCaixa", {}).get("saldoAtual", 0) or 0)
        elif "saldo" in resumo:
            saldo = float(resumo.get("saldo", 0) or 0)
    return {"balance_brl": saldo, "as_of": now_iso()}


def unified_list_payables(from_date=None, to_date=None, limit=50, page=1):
    data = contas_pagar(page, min(limit, 50))
    items_raw = data.get("conta_pagar_cadastro", []) or []
    items = []
    for r in items_raw:
        items.append({
            "id": str(r.get("nCodTitulo", "")),
            "due_date": r.get("dDtVenc", ""),
            "amount_brl": float(r.get("nValorTitulo", 0) or 0),
            "counterparty": r.get("nomeFornecedor", r.get("cFornecedor", "")),
            "status": _map_status_pagar(r.get("cStatus", "")),
            "category": r.get("cCategoria", None),
            "raw": r,
        })
    total = data.get("nTotalDeRegistros", len(items))
    total_pages = max(1, -(-total // limit))
    return {"items": items, "page": page, "total_pages": total_pages, "total_count": total}


def unified_list_receivables(from_date=None, to_date=None, limit=50, page=1):
    data = contas_receber(page, min(limit, 50))
    items_raw = data.get("conta_receber_cadastro", []) or []
    items = []
    for r in items_raw:
        items.append({
            "id": str(r.get("nCodTitulo", "")),
            "due_date": r.get("dDtVenc", ""),
            "amount_brl": float(r.get("nValorTitulo", 0) or 0),
            "counterparty": r.get("nomeCliente", r.get("cCliente", "")),
            "status": _map_status_receber(r.get("cStatus", "")),
            "category": r.get("cCategoria", None),
            "raw": r,
        })
    total = data.get("nTotalDeRegistros", len(items))
    total_pages = max(1, -(-total // limit))
    return {"items": items, "page": page, "total_pages": total_pages, "total_count": total}


def unified_company_info():
    return {"name": os.environ.get("OMIE_COMPANY_NAME", "N/A"), "cnpj": None, "segment": "ERP"}


def unified_pay_payable(id: str) -> dict:
    """Marca conta a pagar como paga via AlterarContaPagar."""
    today = datetime.now().strftime("%d/%m/%Y")
    data = api_call("financas/contaspagar", "AlterarContaPagar", [
        {"nCodTitulo": int(id), "cStatus": "PAGO", "dDtPagamento": today}
    ])
    if "error" in data:
        raise RuntimeError(f"Omie pay_payable: {data}")
    return {"success": True, "action": "pay_payable", "id": id,
            "before": {"status": "pending"}, "after": {"status": "paid", "paid_at": date.today().isoformat()},
            "raw": data}


def unified_mark_received(id: str) -> dict:
    """Marca conta a receber como recebida via AlterarContaReceber."""
    today = datetime.now().strftime("%d/%m/%Y")
    data = api_call("financas/contasreceber", "AlterarContaReceber", [
        {"nCodTitulo": int(id), "cStatus": "RECEBIDO", "dDtRecebimento": today}
    ])
    if "error" in data:
        raise RuntimeError(f"Omie mark_received: {data}")
    return {"success": True, "action": "mark_received", "id": id,
            "before": {"status": "pending"}, "after": {"status": "received", "received_at": date.today().isoformat()},
            "raw": data}


def unified_create_payable(amount: float, due_date: str, supplier: str, **kwargs) -> dict:
    """Cria conta a pagar via IncluirContaPagar."""
    data = api_call("financas/contaspagar", "IncluirContaPagar", [{
        "nValorTitulo": amount,
        "dDtVenc": due_date,
        "cFornecedor": supplier,
        "cCategoria": kwargs.get("category", ""),
        "cObs": kwargs.get("description", ""),
    }])
    if "error" in data:
        raise RuntimeError(f"Omie create_payable: {data}")
    new_id = data.get("nCodTitulo", "")
    return {"success": True, "action": "create_payable", "id": str(new_id), "raw": data}


def unified_create_receivable(amount: float, due_date: str, customer: str, **kwargs) -> dict:
    """Cria conta a receber via IncluirContaReceber."""
    data = api_call("financas/contasreceber", "IncluirContaReceber", [{
        "nValorTitulo": amount,
        "dDtVenc": due_date,
        "cCliente": customer,
        "cCategoria": kwargs.get("category", ""),
        "cObs": kwargs.get("description", ""),
    }])
    if "error" in data:
        raise RuntimeError(f"Omie create_receivable: {data}")
    new_id = data.get("nCodTitulo", "")
    return {"success": True, "action": "create_receivable", "id": str(new_id), "raw": data}


def unified_cancel_payable(id: str) -> dict:
    """Exclui conta a pagar via ExcluirContaPagar."""
    data = api_call("financas/contaspagar", "ExcluirContaPagar", [
        {"nCodTitulo": int(id)}
    ])
    if "error" in data:
        raise RuntimeError(f"Omie cancel_payable: {data}")
    return {"success": True, "action": "cancel_payable", "id": id, "raw": data}


def unified_list_overdue():
    today = date.today().isoformat()
    pag = unified_list_payables(limit=200)
    rec = unified_list_receivables(limit=200)
    overdue = [
        i for i in pag["items"] + rec["items"]
        if i.get("status") in ("pending", "overdue") and i.get("due_date", "9999") < today
    ]
    return {"items": overdue, "page": 1, "total_pages": 1, "total_count": len(overdue)}


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_kwargs(args):
    kwargs = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            key = args[i][2:].replace("-", "_")
            kwargs[key] = args[i + 1]
            i += 2
        else:
            i += 1
    return kwargs


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: omie_client.py <command> [args]")
        print("\nComandos unificados (schema CFO):")
        print("  get_balance")
        print("  list_payables [--from DATE] [--to DATE] [--limit N] [--page N]")
        print("  list_receivables [--from DATE] [--to DATE] [--limit N] [--page N]")
        print("  list_overdue")
        print("  company_info")
        print("\nComandos legados (Omie nativo):")
        print("  clientes_listar [pagina] [por_pagina]")
        print("  clientes_buscar [filtro]")
        print("  clientes_detalhar codigo")
        print("  produtos_listar [pagina] [por_pagina]")
        print("  produtos_detalhar codigo")
        print("  pedidos_listar [pagina] [por_pagina]")
        print("  pedidos_detalhar numero")
        print("  pedidos_status numero")
        print("  contas_receber [pagina] [por_pagina]")
        print("  contas_pagar [pagina] [por_pagina]")
        print("  resumo_financeiro")
        print("  nfe_listar [pagina] [por_pagina]")
        print("  nfe_detalhar numero")
        print("  estoque_posicao [pagina] [por_pagina]")
        print("  estoque_produto codigo")
        sys.exit(1)

    command = sys.argv[1]

    try:
        # ── Comandos unificados CFO ──
        if command == "get_balance":
            result = unified_get_balance()
        elif command == "list_payables":
            kw = _parse_kwargs(sys.argv[2:])
            result = unified_list_payables(
                from_date=kw.get("from"),
                to_date=kw.get("to"),
                limit=int(kw.get("limit", 50)),
                page=int(kw.get("page", 1)),
            )
        elif command == "list_receivables":
            kw = _parse_kwargs(sys.argv[2:])
            result = unified_list_receivables(
                from_date=kw.get("from"),
                to_date=kw.get("to"),
                limit=int(kw.get("limit", 50)),
                page=int(kw.get("page", 1)),
            )
        elif command == "list_overdue":
            result = unified_list_overdue()
        elif command == "company_info":
            result = unified_company_info()
        elif command == "pay_payable":
            kw = _parse_kwargs(sys.argv[2:])
            result = unified_pay_payable(id=kw.get("id", ""))
        elif command == "mark_received":
            kw = _parse_kwargs(sys.argv[2:])
            result = unified_mark_received(id=kw.get("id", ""))
        elif command == "create_payable":
            kw = _parse_kwargs(sys.argv[2:])
            result = unified_create_payable(
                amount=float(kw.get("amount", 0)),
                due_date=kw.get("due_date", ""),
                supplier=kw.get("supplier", ""),
                category=kw.get("category"),
                description=kw.get("description"),
            )
        elif command == "create_receivable":
            kw = _parse_kwargs(sys.argv[2:])
            result = unified_create_receivable(
                amount=float(kw.get("amount", 0)),
                due_date=kw.get("due_date", ""),
                customer=kw.get("customer", ""),
                category=kw.get("category"),
                description=kw.get("description"),
            )
        elif command == "cancel_payable":
            kw = _parse_kwargs(sys.argv[2:])
            result = unified_cancel_payable(id=kw.get("id", ""))

        # ── Comandos legados Omie ──
        elif command == "clientes_listar":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            result = clientes_listar(page, per_page)
        elif command == "clientes_buscar":
            filtro = {}
            for arg in sys.argv[2:]:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    filtro[k] = v
            result = clientes_buscar(filtro)
        elif command == "clientes_detalhar":
            result = clientes_detalhar(int(sys.argv[2]))
        elif command == "produtos_listar":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            result = produtos_listar(page, per_page)
        elif command == "produtos_detalhar":
            result = produtos_detalhar(int(sys.argv[2]))
        elif command == "pedidos_listar":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            result = pedidos_listar(page, per_page)
        elif command == "pedidos_detalhar":
            result = pedidos_detalhar(int(sys.argv[2]))
        elif command == "pedidos_status":
            result = pedidos_status(int(sys.argv[2]))
        elif command == "contas_receber":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            result = contas_receber(page, per_page)
        elif command == "contas_pagar":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            result = contas_pagar(page, per_page)
        elif command == "resumo_financeiro":
            result = resumo_financeiro()
        elif command == "nfe_listar":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            result = nfe_listar(page, per_page)
        elif command == "nfe_detalhar":
            result = nfe_detalhar(int(sys.argv[2]))
        elif command == "estoque_posicao":
            page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 20
            result = estoque_posicao(page, per_page)
        elif command == "estoque_produto":
            result = estoque_produto(int(sys.argv[2]))
        else:
            print(json.dumps({"error": f"Comando desconhecido: {command}"}))
            sys.exit(1)

        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)


# ── Departamentos ────────────────────────────────────────────────────────────

def departamentos_listar(pagina=1, por_pagina=20):
    return api_call("geral/departamentos", "ListarDepartamentos", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])

# ── Projetos ─────────────────────────────────────────────────────────────────

def projetos_listar(pagina=1, por_pagina=20):
    return api_call("geral/projetos", "ListarProjetos", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])

# ── Categorias ───────────────────────────────────────────────────────────────

def categorias_listar(pagina=1, por_pagina=50):
    return api_call("geral/categorias", "ListarCategorias", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])

# ── Contas Correntes ─────────────────────────────────────────────────────────

def contas_correntes_listar(pagina=1, por_pagina=20):
    return api_call("geral/contacorrente", "ListarContasCorrentes", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])

# ── Centros de Custo ─────────────────────────────────────────────────────────

def centros_custo_listar(pagina=1, por_pagina=50):
    # TODO: verificar endpoint exato na doc oficial
    return api_call("geral/categorias", "ListarCategorias", [
        {"pagina": pagina, "registros_por_pagina": por_pagina, "filtrar_apenas_tipo": "D"}
    ])

# ── Tags/Etiquetas ───────────────────────────────────────────────────────────

def tags_listar(pagina=1, por_pagina=50):
    return api_call("geral/etiquetas", "ListarEtiquetas", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])

# ── Lançamentos Financeiros (extrato) ────────────────────────────────────────

def lancamentos_listar(pagina=1, por_pagina=20):
    return api_call("financas/extrato", "ListarExtrato", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])

# ── Fluxo de Caixa ──────────────────────────────────────────────────────────

def fluxo_caixa(data_inicio=None, data_fim=None):
    params = {}
    if data_inicio:
        params["dDtInicio"] = data_inicio
    if data_fim:
        params["dDtFim"] = data_fim
    return api_call("financas/pesquisartitulos", "PesquisarLancamentos", [params])

# ── NF-e extras ──────────────────────────────────────────────────────────────

def nfe_xml(numero: int):
    return api_call("produtos/nfe", "ObterNFe", [
        {"nNF": numero, "lRetornarXml": True}
    ])

def nfe_cancelar(numero: int, motivo: str = "Cancelamento"):
    return api_call("produtos/nfe", "CancelarNFe", [
        {"nNF": numero, "cMotivo": motivo}
    ])

# ── Clientes extras ─────────────────────────────────────────────────────────

def clientes_criar(dados: dict):
    return api_call("geral/clientes", "IncluirCliente", [dados])

def clientes_atualizar(dados: dict):
    return api_call("geral/clientes", "AlterarCliente", [dados])

# ── Produtos extras ──────────────────────────────────────────────────────────

def produtos_criar(dados: dict):
    return api_call("geral/produtos", "IncluirProduto", [dados])

def produtos_atualizar(dados: dict):
    return api_call("geral/produtos", "AlterarProduto", [dados])

# ── Pedidos extras ───────────────────────────────────────────────────────────

def pedidos_criar(dados: dict):
    return api_call("produtos/pedido", "IncluirPedido", [dados])

# ── Ordem de Serviço ─────────────────────────────────────────────────────────

def os_listar(pagina=1, por_pagina=20):
    return api_call("servicos/os", "ListarOS", [
        {"pagina": pagina, "registros_por_pagina": por_pagina}
    ])

def os_detalhar(numero: int):
    return api_call("servicos/os", "ConsultarOS", [
        {"nCodOS": numero}
    ])
