#!/usr/bin/env python3
"""Tiny ERP Client (API v2) — Agente CFO skill."""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseERPClient, http_request, emit, emit_error, now_iso, make_list_response


def _convert_date_br(date_br):
    """Convert DD/MM/YYYY to YYYY-MM-DD."""
    if not date_br or "/" not in date_br:
        return date_br or ""
    parts = date_br.split("/")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_br


class TinyClient(BaseERPClient):
    SKILL_NAME = "tiny"
    BASE_URL = "https://api.tiny.com.br/api2"

    def _validate_env(self):
        if not os.environ.get("TINY_TOKEN"):
            raise RuntimeError("TINY_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["TINY_TOKEN"]

    def _get(self, endpoint, extra_params=""):
        url = f"{self.BASE_URL}/{endpoint}?token={self.token}&formato=JSON{extra_params}"
        data = http_request("GET", url)
        retorno = data.get("retorno", data) if isinstance(data, dict) else data
        if isinstance(retorno, dict) and retorno.get("status") == "Erro":
            raise RuntimeError(f"Tiny API: {retorno.get('erros', retorno)}")
        return retorno

    def get_balance(self):
        return {"balance_brl": None, "as_of": now_iso(), "note": "Saldo nao disponivel via Tiny API v2"}

    def list_payables(self, from_date=None, to_date=None, limit=50, page=1):
        params = f"&situacao=aberto&pagina={page}"
        data = self._get("contas.pagar.pesquisa.php", params)
        items = []
        records = data.get("contas_pagar", []) or []
        for wrapper in records:
            r = wrapper.get("conta_pagar", wrapper) if isinstance(wrapper, dict) else wrapper
            items.append({
                "id": str(r.get("id", "")),
                "due_date": _convert_date_br(r.get("data_vencimento", "")),
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": r.get("nome_fornecedor", ""),
                "status": "paid" if r.get("situacao", "").lower() in ("pago", "liquidado") else "pending",
                "category": None,
                "raw": r,
            })
        total = int(data.get("numero_paginas", 1) or 1)
        return make_list_response(items, page=page, total_pages=total, total_count=len(items))

    def list_receivables(self, from_date=None, to_date=None, limit=50, page=1):
        params = f"&pagina={page}"
        data = self._get("contas.receber.pesquisa.php", params)
        items = []
        records = data.get("contas_receber", []) or []
        for wrapper in records:
            r = wrapper.get("conta_receber", wrapper) if isinstance(wrapper, dict) else wrapper
            items.append({
                "id": str(r.get("id", "")),
                "due_date": _convert_date_br(r.get("data_vencimento", "")),
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": r.get("nome_cliente", ""),
                "status": "received" if r.get("situacao", "").lower() in ("recebido", "liquidado", "pago") else "pending",
                "category": None,
                "raw": r,
            })
        total = int(data.get("numero_paginas", 1) or 1)
        return make_list_response(items, page=page, total_pages=total, total_count=len(items))

    def company_info(self):
        try:
            data = self._get("info.php")
            info = data.get("info", {}) if isinstance(data, dict) else {}
            return {"name": info.get("nome_empresa", "N/A"), "cnpj": info.get("cnpj", None), "segment": "ERP"}
        except Exception:
            return {"name": "N/A", "cnpj": None, "segment": "ERP"}


if __name__ == "__main__":
    try:
        client = TinyClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
