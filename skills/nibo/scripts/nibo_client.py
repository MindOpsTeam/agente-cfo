#!/usr/bin/env python3
"""Nibo ERP Client — Agente CFO skill."""

import os
import sys

import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseERPClient, http_request, emit, emit_error, now_iso, make_list_response


class NiboClient(BaseERPClient):
    SKILL_NAME = "nibo"
    BASE_URL = "https://api.nibo.com.br/empresas/v1"

    def _validate_env(self):
        if not os.environ.get("NIBO_API_TOKEN"):
            raise RuntimeError("NIBO_API_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["NIBO_API_TOKEN"]
        self.headers = {
            "ApiToken": self.token,
            "Content-Type": "application/json",
        }

    def _get(self, path):
        url = f"{self.BASE_URL}/{path}"
        return http_request("GET", url, headers=self.headers)

    def get_balance(self):
        data = self._get("bankAccounts")
        contas = data.get("items", data) if isinstance(data, dict) else data
        if isinstance(contas, list):
            saldo = sum(float(c.get("balance", 0) or 0) for c in contas)
        else:
            saldo = 0.0
        return {"balance_brl": round(saldo, 2), "as_of": now_iso()}

    def list_payables(self, from_date=None, to_date=None, limit=50, page=1):
        skip = (page - 1) * limit
        path = f"schedules/debit?$orderby=dueDate&$top={limit}&$skip={skip}"
        if from_date and to_date:
            path += f"&$filter=dueDate ge {from_date} and dueDate le {to_date}"
        elif from_date:
            path += f"&$filter=dueDate ge {from_date}"
        elif to_date:
            path += f"&$filter=dueDate le {to_date}"
        data = self._get(path)
        items = []
        records = data.get("items", data) if isinstance(data, dict) else data
        if isinstance(records, list):
            for r in records:
                stakeholder = r.get("stakeholder", {}) or {}
                items.append({
                    "id": str(r.get("id", "")),
                    "due_date": (r.get("dueDate", "") or "")[:10],
                    "amount_brl": float(r.get("value", 0) or 0),
                    "counterparty": stakeholder.get("name", ""),
                    "status": "paid" if r.get("isPaid") else "pending",
                    "category": None,
                    "raw": r,
                })
        total = data.get("count", len(items)) if isinstance(data, dict) else len(items)
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def list_receivables(self, from_date=None, to_date=None, limit=50, page=1):
        skip = (page - 1) * limit
        path = f"schedules/credit?$orderby=dueDate&$top={limit}&$skip={skip}"
        if from_date and to_date:
            path += f"&$filter=dueDate ge {from_date} and dueDate le {to_date}"
        elif from_date:
            path += f"&$filter=dueDate ge {from_date}"
        elif to_date:
            path += f"&$filter=dueDate le {to_date}"
        data = self._get(path)
        items = []
        records = data.get("items", data) if isinstance(data, dict) else data
        if isinstance(records, list):
            for r in records:
                stakeholder = r.get("stakeholder", {}) or {}
                items.append({
                    "id": str(r.get("id", "")),
                    "due_date": (r.get("dueDate", "") or "")[:10],
                    "amount_brl": float(r.get("value", 0) or 0),
                    "counterparty": stakeholder.get("name", ""),
                    "status": "received" if r.get("isReceived") else "pending",
                    "category": None,
                    "raw": r,
                })
        total = data.get("count", len(items)) if isinstance(data, dict) else len(items)
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def _post(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("POST", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def pay_payable(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._post(f"schedules/debit/{id}/pay", {"date": today})
        return {"success": True, "action": "pay_payable", "id": id,
                "before": {"status": "pending"}, "after": {"status": "paid", "paid_at": today}, "raw": raw}

    def mark_received(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._post(f"schedules/credit/{id}/receive", {"date": today})
        return {"success": True, "action": "mark_received", "id": id,
                "before": {"status": "pending"}, "after": {"status": "received", "received_at": today}, "raw": raw}

    def create_payable(self, amount: float, due_date: str, supplier: str, **kwargs) -> dict:
        body = {
            "value": amount,
            "dueDate": due_date,
            "stakeholder": {"name": supplier},
        }
        if kwargs.get("description"):
            body["description"] = kwargs["description"]
        raw = self._post("schedules/debit", body)
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_payable", "id": str(new_id), "raw": raw}

    def create_receivable(self, amount: float, due_date: str, customer: str, **kwargs) -> dict:
        body = {
            "value": amount,
            "dueDate": due_date,
            "stakeholder": {"name": customer},
        }
        if kwargs.get("description"):
            body["description"] = kwargs["description"]
        raw = self._post("schedules/credit", body)
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_receivable", "id": str(new_id), "raw": raw}

    def _put(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("PUT", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def _delete(self, path):
        url = f"{self.BASE_URL}/{path}"
        return http_request("DELETE", url, headers=self.headers)

    def company_info(self):
        return {"name": "N/A", "cnpj": None, "segment": "ERP"}

    # ── Contas Bancárias ─────────────────────────────────────────────────────
    def list_bank_accounts(self):
        return self._get("bankAccounts")

    def get_bank_account(self, id: str):
        return self._get(f"bankAccounts/{id}")

    # ── Categorias ───────────────────────────────────────────────────────────
    def list_categories(self):
        return self._get("categories")

    def get_category(self, id: str):
        return self._get(f"categories/{id}")

    def create_category(self, data: dict):
        return self._post("categories", data)

    def update_category(self, id: str, data: dict):
        return self._put(f"categories/{id}", data)

    def delete_category(self, id: str):
        return self._delete(f"categories/{id}")

    # ── Centros de Custo ─────────────────────────────────────────────────────
    def list_cost_centers(self):
        return self._get("costCenters")

    def get_cost_center(self, id: str):
        return self._get(f"costCenters/{id}")

    def create_cost_center(self, data: dict):
        return self._post("costCenters", data)

    def update_cost_center(self, id: str, data: dict):
        return self._put(f"costCenters/{id}", data)

    def delete_cost_center(self, id: str):
        return self._delete(f"costCenters/{id}")

    # ── Clientes ─────────────────────────────────────────────────────────────
    def list_customers(self, limit=50, page=1, search=None):
        skip = (page - 1) * limit
        path = f"customers?$top={limit}&$skip={skip}"
        if search:
            path += f"&$filter=contains(name,'{search}')"
        return self._get(path)

    def get_customer(self, id: str):
        return self._get(f"customers/{id}")

    def create_customer(self, data: dict):
        return self._post("customers", data)

    def update_customer(self, id: str, data: dict):
        return self._put(f"customers/{id}", data)

    def delete_customer(self, id: str):
        return self._delete(f"customers/{id}")

    # ── Fornecedores ─────────────────────────────────────────────────────────
    def list_suppliers(self, limit=50, page=1, search=None):
        skip = (page - 1) * limit
        path = f"suppliers?$top={limit}&$skip={skip}"
        if search:
            path += f"&$filter=contains(name,'{search}')"
        return self._get(path)

    def get_supplier(self, id: str):
        return self._get(f"suppliers/{id}")

    def create_supplier(self, data: dict):
        return self._post("suppliers", data)

    def update_supplier(self, id: str, data: dict):
        return self._put(f"suppliers/{id}", data)

    def delete_supplier(self, id: str):
        return self._delete(f"suppliers/{id}")

    # ── Contas a Pagar/Receber extras ────────────────────────────────────────
    def get_payable(self, id: str):
        return self._get(f"schedules/debit/{id}")

    def delete_payable(self, id: str):
        return self._delete(f"schedules/debit/{id}")

    def get_receivable(self, id: str):
        return self._get(f"schedules/credit/{id}")

    def delete_receivable(self, id: str):
        return self._delete(f"schedules/credit/{id}")

    # ── Transferências ───────────────────────────────────────────────────────
    def list_transfers(self, limit=50, page=1):
        skip = (page - 1) * limit
        return self._get(f"transfers?$top={limit}&$skip={skip}")

    def create_transfer(self, data: dict):
        return self._post("transfers", data)

    # ── Conciliação ──────────────────────────────────────────────────────────
    def list_reconciliations(self, bank_account_id: str, limit=50, page=1):
        skip = (page - 1) * limit
        return self._get(f"bankAccounts/{bank_account_id}/reconciliations?$top={limit}&$skip={skip}")

    # ── Lançamentos / Extrato ────────────────────────────────────────────────
    def list_entries(self, limit=50, page=1, from_date=None, to_date=None):
        skip = (page - 1) * limit
        path = f"schedules?$top={limit}&$skip={skip}&$orderby=dueDate"
        filters = []
        if from_date:
            filters.append(f"dueDate ge {from_date}")
        if to_date:
            filters.append(f"dueDate le {to_date}")
        if filters:
            path += "&$filter=" + " and ".join(filters)
        return self._get(path)

    # ── Relatório DRE ────────────────────────────────────────────────────────
    def get_dre_report(self, from_date: str, to_date: str):
        return self._get(f"reports/dre?startDate={from_date}&endDate={to_date}")

    def get_cashflow_report(self, from_date: str, to_date: str):
        return self._get(f"reports/cashflow?startDate={from_date}&endDate={to_date}")


if __name__ == "__main__":
    try:
        client = NiboClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
