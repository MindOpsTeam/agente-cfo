#!/usr/bin/env python3
"""VHSYS ERP Client — Agente CFO skill."""

import os
import sys

import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseERPClient, http_request, emit, emit_error, now_iso, make_list_response


class VHSYSClient(BaseERPClient):
    SKILL_NAME = "vhsys"
    BASE_URL = "https://api.vhsys.com/v2"

    def _validate_env(self):
        if not os.environ.get("VHSYS_ACCESS_TOKEN") or not os.environ.get("VHSYS_SECRET_TOKEN"):
            raise RuntimeError("VHSYS_ACCESS_TOKEN e VHSYS_SECRET_TOKEN nao definidos. Execute connect.sh.")
        self.headers = {
            "access-token": os.environ["VHSYS_ACCESS_TOKEN"],
            "secret-access-token": os.environ["VHSYS_SECRET_TOKEN"],
            "Content-Type": "application/json",
        }

    def _get(self, path, params=""):
        url = f"{self.BASE_URL}/{path}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self.headers)

    def _map_status(self, situacao):
        if situacao and situacao.lower() in ("pago", "liquidado"):
            return "paid"
        return "pending"

    def _map_status_receber(self, situacao):
        if situacao and situacao.lower() in ("recebido", "liquidado", "pago"):
            return "received"
        return "pending"

    def get_balance(self):
        data = self._get("contas-bancarias")
        contas = data.get("data", []) if isinstance(data, dict) else []
        saldo = sum(float(c.get("saldo_atual", 0) or 0) for c in contas)
        return {"balance_brl": round(saldo, 2), "as_of": now_iso()}

    def list_payables(self, from_date=None, to_date=None, limit=50, page=1):
        offset = (page - 1) * limit
        params = f"offset={offset}&limit={limit}"
        if from_date:
            params += f"&data_vencimento_de={from_date}"
        if to_date:
            params += f"&data_vencimento_ate={to_date}"
        data = self._get("contas-pagar", params)
        items = []
        records = data.get("data", []) if isinstance(data, dict) else []
        for r in records:
            items.append({
                "id": str(r.get("id", "")),
                "due_date": r.get("data_vencimento", ""),
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": r.get("nome_fornecedor", ""),
                "status": self._map_status(r.get("situacao", "")),
                "category": None,
                "raw": r,
            })
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def list_receivables(self, from_date=None, to_date=None, limit=50, page=1):
        offset = (page - 1) * limit
        params = f"offset={offset}&limit={limit}"
        if from_date:
            params += f"&data_vencimento_de={from_date}"
        if to_date:
            params += f"&data_vencimento_ate={to_date}"
        data = self._get("contas-receber", params)
        items = []
        records = data.get("data", []) if isinstance(data, dict) else []
        for r in records:
            items.append({
                "id": str(r.get("id", "")),
                "due_date": r.get("data_vencimento", ""),
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": r.get("nome_cliente", ""),
                "status": self._map_status_receber(r.get("situacao", "")),
                "category": None,
                "raw": r,
            })
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def _put(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("PUT", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def _post(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("POST", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def pay_payable(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._put(f"contas-pagar/{id}", {"situacao": "pago", "data_pagamento": today})
        return {"success": True, "action": "pay_payable", "id": id,
                "before": {"status": "pending"}, "after": {"status": "paid", "paid_at": today}, "raw": raw}

    def mark_received(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._put(f"contas-receber/{id}", {"situacao": "recebido", "data_recebimento": today})
        return {"success": True, "action": "mark_received", "id": id,
                "before": {"status": "pending"}, "after": {"status": "received", "received_at": today}, "raw": raw}

    def create_payable(self, amount: float, due_date: str, supplier: str, **kwargs) -> dict:
        body = {"valor": amount, "data_vencimento": due_date, "nome_fornecedor": supplier}
        if kwargs.get("description"):
            body["observacao"] = kwargs["description"]
        raw = self._post("contas-pagar", body)
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_payable", "id": str(new_id), "raw": raw}

    def create_receivable(self, amount: float, due_date: str, customer: str, **kwargs) -> dict:
        body = {"valor": amount, "data_vencimento": due_date, "nome_cliente": customer}
        if kwargs.get("description"):
            body["observacao"] = kwargs["description"]
        raw = self._post("contas-receber", body)
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_receivable", "id": str(new_id), "raw": raw}

    def _delete(self, path):
        url = f"{self.BASE_URL}/{path}"
        return http_request("DELETE", url, headers=self.headers)

    def company_info(self):
        return {"name": "N/A", "cnpj": None, "segment": "ERP"}

    # ── Contas Bancárias ─────────────────────────────────────────────────────
    def list_bank_accounts(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("contas-bancarias", f"offset={offset}&limit={limit}")

    def get_bank_account(self, id: str):
        return self._get(f"contas-bancarias/{id}")

    # ── Clientes ─────────────────────────────────────────────────────────────
    def list_customers(self, limit=50, page=1, search=None):
        offset = (page - 1) * limit
        params = f"offset={offset}&limit={limit}"
        if search:
            params += f"&razao_social={search}"
        return self._get("clientes", params)

    def get_customer(self, id: str):
        return self._get(f"clientes/{id}")

    def create_customer(self, data: dict):
        return self._post("clientes", data)

    def update_customer(self, id: str, data: dict):
        return self._put(f"clientes/{id}", data)

    def delete_customer(self, id: str):
        return self._delete(f"clientes/{id}")

    # ── Fornecedores ─────────────────────────────────────────────────────────
    def list_suppliers(self, limit=50, page=1, search=None):
        offset = (page - 1) * limit
        params = f"offset={offset}&limit={limit}"
        if search:
            params += f"&razao_social={search}"
        return self._get("fornecedores", params)

    def get_supplier(self, id: str):
        return self._get(f"fornecedores/{id}")

    def create_supplier(self, data: dict):
        return self._post("fornecedores", data)

    def update_supplier(self, id: str, data: dict):
        return self._put(f"fornecedores/{id}", data)

    def delete_supplier(self, id: str):
        return self._delete(f"fornecedores/{id}")

    # ── Produtos ─────────────────────────────────────────────────────────────
    def list_products(self, limit=50, page=1, search=None):
        offset = (page - 1) * limit
        params = f"offset={offset}&limit={limit}"
        if search:
            params += f"&descricao={search}"
        return self._get("produtos", params)

    def get_product(self, id: str):
        return self._get(f"produtos/{id}")

    def create_product(self, data: dict):
        return self._post("produtos", data)

    def update_product(self, id: str, data: dict):
        return self._put(f"produtos/{id}", data)

    def delete_product(self, id: str):
        return self._delete(f"produtos/{id}")

    # ── Pedidos de Venda ─────────────────────────────────────────────────────
    def list_sales_orders(self, limit=50, page=1, from_date=None, to_date=None):
        offset = (page - 1) * limit
        params = f"offset={offset}&limit={limit}"
        if from_date:
            params += f"&data_de={from_date}"
        if to_date:
            params += f"&data_ate={to_date}"
        return self._get("pedidos-venda", params)

    def get_sales_order(self, id: str):
        return self._get(f"pedidos-venda/{id}")

    def create_sales_order(self, data: dict):
        return self._post("pedidos-venda", data)

    def update_sales_order(self, id: str, data: dict):
        return self._put(f"pedidos-venda/{id}", data)

    def delete_sales_order(self, id: str):
        return self._delete(f"pedidos-venda/{id}")

    # ── Pedidos de Compra ────────────────────────────────────────────────────
    def list_purchase_orders(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("pedidos-compra", f"offset={offset}&limit={limit}")

    def get_purchase_order(self, id: str):
        return self._get(f"pedidos-compra/{id}")

    def create_purchase_order(self, data: dict):
        return self._post("pedidos-compra", data)

    # ── Notas Fiscais ────────────────────────────────────────────────────────
    def list_invoices(self, limit=50, page=1, from_date=None, to_date=None):
        offset = (page - 1) * limit
        params = f"offset={offset}&limit={limit}"
        if from_date:
            params += f"&data_de={from_date}"
        if to_date:
            params += f"&data_ate={to_date}"
        return self._get("notas-fiscais", params)

    def get_invoice(self, id: str):
        return self._get(f"notas-fiscais/{id}")

    def emit_invoice(self, data: dict):
        return self._post("notas-fiscais", data)

    # ── Categorias Financeiras ───────────────────────────────────────────────
    def list_financial_categories(self):
        return self._get("categorias-financeiras")

    def create_financial_category(self, data: dict):
        return self._post("categorias-financeiras", data)

    # ── Centros de Custo ─────────────────────────────────────────────────────
    def list_cost_centers(self):
        return self._get("centros-custo")

    def create_cost_center(self, data: dict):
        return self._post("centros-custo", data)

    # ── Transportadoras ──────────────────────────────────────────────────────
    def list_carriers(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("transportadoras", f"offset={offset}&limit={limit}")

    def get_carrier(self, id: str):
        return self._get(f"transportadoras/{id}")

    # ── Vendedores ───────────────────────────────────────────────────────────
    def list_sellers(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("vendedores", f"offset={offset}&limit={limit}")

    def get_seller(self, id: str):
        return self._get(f"vendedores/{id}")

    # ── Orçamentos ───────────────────────────────────────────────────────────
    def list_quotes(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("orcamentos", f"offset={offset}&limit={limit}")

    def get_quote(self, id: str):
        return self._get(f"orcamentos/{id}")

    def create_quote(self, data: dict):
        return self._post("orcamentos", data)

    # ── Ordens de Serviço ────────────────────────────────────────────────────
    def list_service_orders(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("ordens-servico", f"offset={offset}&limit={limit}")

    def get_service_order(self, id: str):
        return self._get(f"ordens-servico/{id}")

    def create_service_order(self, data: dict):
        return self._post("ordens-servico", data)

    # ── Contas a Pagar/Receber — extras ──────────────────────────────────────
    def get_payable(self, id: str):
        return self._get(f"contas-pagar/{id}")

    def delete_payable(self, id: str):
        return self._delete(f"contas-pagar/{id}")

    def get_receivable(self, id: str):
        return self._get(f"contas-receber/{id}")

    def delete_receivable(self, id: str):
        return self._delete(f"contas-receber/{id}")


if __name__ == "__main__":
    try:
        client = VHSYSClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
