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

    # ── Contas Bancárias ─────────────────────────────────────────────────────
    def list_bank_accounts(self):
        return self._get("contas")

    def get_bank_account(self, id: str):
        return self._get(f"contas/{id}")

    def create_bank_account(self, data: dict):
        return self._post("contas", data)

    def update_bank_account(self, id: str, data: dict):
        return self._put(f"contas/{id}", data)

    def delete_bank_account(self, id: str):
        return self._delete(f"contas/{id}")

    # ── Lançamentos extras ───────────────────────────────────────────────────
    def get_entry(self, id: str):
        return self._get(f"lancamentos/{id}")

    def update_entry(self, id: str, data: dict):
        return self._put(f"lancamentos/{id}", data)

    def delete_entry(self, id: str):
        return self._delete(f"lancamentos/{id}")

    # ── Categorias ───────────────────────────────────────────────────────────
    def list_categories(self):
        return self._get("categorias")

    def get_category(self, id: str):
        return self._get(f"categorias/{id}")

    def create_category(self, data: dict):
        return self._post("categorias", data)

    def update_category(self, id: str, data: dict):
        return self._put(f"categorias/{id}", data)

    def delete_category(self, id: str):
        return self._delete(f"categorias/{id}")

    # ── Centros de Custo ─────────────────────────────────────────────────────
    def list_cost_centers(self):
        return self._get("centros_custo")

    def get_cost_center(self, id: str):
        return self._get(f"centros_custo/{id}")

    def create_cost_center(self, data: dict):
        return self._post("centros_custo", data)

    def update_cost_center(self, id: str, data: dict):
        return self._put(f"centros_custo/{id}", data)

    def delete_cost_center(self, id: str):
        return self._delete(f"centros_custo/{id}")

    # ── Clientes ─────────────────────────────────────────────────────────────
    def list_customers(self, limit=50, page=1):
        return self._get("clientes", f"&registros_por_pagina={limit}&pagina={page}")

    def get_customer(self, id: str):
        return self._get(f"clientes/{id}")

    def create_customer(self, data: dict):
        return self._post("clientes", data)

    def update_customer(self, id: str, data: dict):
        return self._put(f"clientes/{id}", data)

    def delete_customer(self, id: str):
        return self._delete(f"clientes/{id}")

    # ── Fornecedores ─────────────────────────────────────────────────────────
    def list_suppliers(self, limit=50, page=1):
        return self._get("fornecedores", f"&registros_por_pagina={limit}&pagina={page}")

    def get_supplier(self, id: str):
        return self._get(f"fornecedores/{id}")

    def create_supplier(self, data: dict):
        return self._post("fornecedores", data)

    def update_supplier(self, id: str, data: dict):
        return self._put(f"fornecedores/{id}", data)

    def delete_supplier(self, id: str):
        return self._delete(f"fornecedores/{id}")

    # ── Formas de Pagamento ──────────────────────────────────────────────────
    def list_payment_methods(self):
        return self._get("formas_pagamento")

    # ── Tipos de Documento ───────────────────────────────────────────────────
    def list_document_types(self):
        return self._get("tipos_documento")


if __name__ == "__main__":
    try:
        client = GranatumClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
