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

    def company_info(self):
        return {"name": "N/A", "cnpj": None, "segment": "ERP"}


if __name__ == "__main__":
    try:
        client = VHSYSClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
