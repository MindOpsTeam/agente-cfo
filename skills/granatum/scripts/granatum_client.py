#!/usr/bin/env python3
"""Granatum ERP Client — Agente CFO skill."""

import os
import sys
import time

import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseERPClient, http_request, emit, emit_error, now_iso, make_list_response


class GranatumClient(BaseERPClient):
    SKILL_NAME = "granatum"
    BASE_URL = "https://api.granatum.com.br/v1"

    def _validate_env(self):
        if not os.environ.get("GRANATUM_ACCESS_TOKEN"):
            raise RuntimeError("GRANATUM_ACCESS_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["GRANATUM_ACCESS_TOKEN"]

    def _url(self, path, extra_params=""):
        sep = "&" if "?" in path else "?"
        return f"{self.BASE_URL}/{path}{sep}access_token={self.token}{extra_params}"

    def _get(self, path, extra_params=""):
        url = self._url(path, extra_params)
        return http_request("GET", url)

    def get_balance(self):
        contas = self._get("contas")
        if isinstance(contas, list):
            saldo = sum(float(c.get("saldo_atual", 0) or 0) for c in contas)
        else:
            saldo = 0.0
        return {"balance_brl": round(saldo, 2), "as_of": now_iso()}

    def list_payables(self, from_date=None, to_date=None, limit=50, page=1):
        params = "&tipo_lancamento_id=2"
        params += f"&registros_por_pagina={limit}&pagina={page}"
        if from_date:
            params += f"&data_vencimento_de={from_date}"
        if to_date:
            params += f"&data_vencimento_ate={to_date}"
        data = self._get("lancamentos", params)
        items = []
        records = data if isinstance(data, list) else []
        for r in records:
            status = "paid" if r.get("data_pagamento") else "pending"
            items.append({
                "id": str(r.get("id", "")),
                "due_date": r.get("data_vencimento", ""),
                "amount_brl": abs(float(r.get("valor", 0) or 0)),
                "counterparty": r.get("descricao", ""),
                "status": status,
                "category": r.get("categoria", {}).get("descricao") if isinstance(r.get("categoria"), dict) else None,
                "raw": r,
            })
        return make_list_response(items, page=page, total_count=len(items))

    def list_receivables(self, from_date=None, to_date=None, limit=50, page=1):
        params = "&tipo_lancamento_id=1"
        params += f"&registros_por_pagina={limit}&pagina={page}"
        if from_date:
            params += f"&data_vencimento_de={from_date}"
        if to_date:
            params += f"&data_vencimento_ate={to_date}"
        data = self._get("lancamentos", params)
        items = []
        records = data if isinstance(data, list) else []
        for r in records:
            status = "received" if r.get("data_pagamento") else "pending"
            items.append({
                "id": str(r.get("id", "")),
                "due_date": r.get("data_vencimento", ""),
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": r.get("descricao", ""),
                "status": status,
                "category": r.get("categoria", {}).get("descricao") if isinstance(r.get("categoria"), dict) else None,
                "raw": r,
            })
        return make_list_response(items, page=page, total_count=len(items))

    def _put(self, path, body: dict):
        url = self._url(path)
        return http_request("PUT", url, headers={"Content-Type": "application/json"},
                            body=_json.dumps(body).encode())

    def _post(self, path, body: dict):
        url = self._url(path)
        return http_request("POST", url, headers={"Content-Type": "application/json"},
                            body=_json.dumps(body).encode())

    def _delete(self, path):
        url = self._url(path)
        return http_request("DELETE", url)

    def pay_payable(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._put(f"lancamentos/{id}", {"data_pagamento": today})
        return {"success": True, "action": "pay_payable", "id": id,
                "before": {"status": "pending"}, "after": {"status": "paid", "paid_at": today}, "raw": raw}

    def mark_received(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._put(f"lancamentos/{id}", {"data_pagamento": today})
        return {"success": True, "action": "mark_received", "id": id,
                "before": {"status": "pending"}, "after": {"status": "received", "received_at": today}, "raw": raw}

    def create_payable(self, amount: float, due_date: str, supplier: str, **kwargs) -> dict:
        body = {
            "valor": -abs(amount),
            "data_vencimento": due_date,
            "descricao": supplier,
            "tipo_lancamento_id": 2,
        }
        if kwargs.get("category"):
            body["categoria"] = {"descricao": kwargs["category"]}
        raw = self._post("lancamentos", body)
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_payable", "id": str(new_id), "raw": raw}

    def create_receivable(self, amount: float, due_date: str, customer: str, **kwargs) -> dict:
        body = {
            "valor": abs(amount),
            "data_vencimento": due_date,
            "descricao": customer,
            "tipo_lancamento_id": 1,
        }
        raw = self._post("lancamentos", body)
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_receivable", "id": str(new_id), "raw": raw}

    def cancel_payable(self, id: str) -> dict:
        raw = self._delete(f"lancamentos/{id}")
        return {"success": True, "action": "cancel_payable", "id": id, "raw": raw}

    def company_info(self):
        return {"name": "N/A", "cnpj": None, "segment": "ERP"}


if __name__ == "__main__":
    try:
        client = GranatumClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
