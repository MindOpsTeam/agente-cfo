#!/usr/bin/env python3
"""Nibo ERP Client — Agente CFO skill."""

import os
import sys

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

    def company_info(self):
        return {"name": "N/A", "cnpj": None, "segment": "ERP"}


if __name__ == "__main__":
    try:
        client = NiboClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
