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

    def pay_payable(self, id: str) -> dict:
        return {"error": "not_supported",
                "message": "Tiny v2 nao suporta baixa de contas a pagar via API. Faca manualmente em app.tiny.com.br."}

    def mark_received(self, id: str) -> dict:
        return {"error": "not_supported",
                "message": "Tiny v2 nao suporta baixa de contas a receber via API. Faca manualmente em app.tiny.com.br."}

    def create_payable(self, amount: float, due_date: str, supplier: str, **kwargs) -> dict:
        return {"error": "not_supported",
                "message": "Tiny v2 nao suporta criacao de contas a pagar via API. Faca manualmente em app.tiny.com.br."}

    def create_receivable(self, amount: float, due_date: str, customer: str, **kwargs) -> dict:
        return {"error": "not_supported",
                "message": "Tiny v2 nao suporta criacao de contas a receber via API. Faca manualmente em app.tiny.com.br."}

    def cancel_payable(self, id: str) -> dict:
        return {"error": "not_supported",
                "message": "Tiny v2 nao suporta exclusao de contas via API. Faca manualmente em app.tiny.com.br."}

    def company_info(self):
        try:
            data = self._get("info.php")
            info = data.get("info", {}) if isinstance(data, dict) else {}
            return {"name": info.get("nome_empresa", "N/A"), "cnpj": info.get("cnpj", None), "segment": "ERP"}
        except Exception:
            return {"name": "N/A", "cnpj": None, "segment": "ERP"}

    def _post(self, endpoint, body_xml: str):
        """POST com corpo XML urlencoded (padrão Tiny API v2)."""
        import json as _json
        url = f"{self.BASE_URL}/{endpoint}"
        form = urllib.parse.urlencode({"token": self.token, "formato": "JSON", "contato": body_xml})
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return http_request("POST", url, headers=headers, body=form.encode())

    def _post_form(self, endpoint, extra_fields: dict):
        fields = {"token": self.token, "formato": "JSON", **extra_fields}
        url = f"{self.BASE_URL}/{endpoint}"
        form = urllib.parse.urlencode(fields)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = http_request("POST", url, headers=headers, body=form.encode())
        retorno = data.get("retorno", data) if isinstance(data, dict) else data
        return retorno

    # ── Contatos (Clientes/Fornecedores) ─────────────────────────────────────
    def list_contacts(self, search=None, page=1):
        params = f"&pagina={page}"
        if search:
            params += f"&pesquisa={urllib.parse.quote(search)}"
        data = self._get("contatos.pesquisa.php", params)
        return data.get("contatos", data) if isinstance(data, dict) else data

    def get_contact(self, id: str):
        data = self._get(f"contato.obter.php", f"&id={id}")
        return data.get("contato", data) if isinstance(data, dict) else data

    def create_contact(self, contact_data: dict):
        import json as _json
        return self._post_form("contato.incluir.php", {"contato": _json.dumps({"contatos": [{"contato": contact_data}]})})

    def update_contact(self, contact_data: dict):
        import json as _json
        return self._post_form("contato.alterar.php", {"contato": _json.dumps({"contatos": [{"contato": contact_data}]})})

    # ── Produtos ─────────────────────────────────────────────────────────────
    def list_products(self, search=None, page=1):
        params = f"&pagina={page}"
        if search:
            params += f"&pesquisa={urllib.parse.quote(search)}"
        data = self._get("produtos.pesquisa.php", params)
        return data.get("produtos", data) if isinstance(data, dict) else data

    def get_product(self, id: str):
        data = self._get("produto.obter.php", f"&id={id}")
        return data.get("produto", data) if isinstance(data, dict) else data

    def create_product(self, product_data: dict):
        import json as _json
        return self._post_form("produto.incluir.php", {"produto": _json.dumps({"produtos": [{"produto": product_data}]})})

    def update_product(self, product_data: dict):
        import json as _json
        return self._post_form("produto.alterar.php", {"produto": _json.dumps({"produtos": [{"produto": product_data}]})})

    # ── Pedidos ──────────────────────────────────────────────────────────────
    def list_orders(self, search=None, page=1, situacao=None):
        params = f"&pagina={page}"
        if search:
            params += f"&pesquisa={urllib.parse.quote(search)}"
        if situacao:
            params += f"&situacao={situacao}"
        data = self._get("pedidos.pesquisa.php", params)
        return data.get("pedidos", data) if isinstance(data, dict) else data

    def get_order(self, id: str):
        data = self._get("pedido.obter.php", f"&id={id}")
        return data.get("pedido", data) if isinstance(data, dict) else data

    def create_order(self, order_data: dict):
        import json as _json
        return self._post_form("pedido.incluir.php", {"pedido": _json.dumps({"pedido": order_data})})

    def update_order_status(self, id: str, situacao: str):
        return self._post_form("pedido.alterar.situacao.php", {"id": id, "situacao": situacao})

    # ── Notas Fiscais ────────────────────────────────────────────────────────
    def list_invoices(self, search=None, page=1, situacao=None):
        params = f"&pagina={page}"
        if search:
            params += f"&pesquisa={urllib.parse.quote(search)}"
        if situacao:
            params += f"&situacao={situacao}"
        data = self._get("notas.fiscais.pesquisa.php", params)
        return data.get("notas_fiscais", data) if isinstance(data, dict) else data

    def get_invoice(self, id: str):
        data = self._get("nota.fiscal.obter.php", f"&id={id}")
        return data.get("nota_fiscal", data) if isinstance(data, dict) else data

    def get_invoice_xml(self, id: str):
        data = self._get("nota.fiscal.obter.xml.php", f"&id={id}")
        return data

    def emit_invoice(self, id: str):
        return self._post_form("nota.fiscal.emitir.php", {"id": id})

    # ── Estoque ──────────────────────────────────────────────────────────────
    def get_stock(self, id: str):
        data = self._get("produto.obter.estoque.php", f"&id={id}")
        return data.get("produto", data) if isinstance(data, dict) else data

    # ── Formas de Pagamento ──────────────────────────────────────────────────
    def list_payment_methods(self):
        data = self._get("formas.pagamento.pesquisa.php")
        return data.get("formas_pagamento", data) if isinstance(data, dict) else data

    # ── Listas de Preço ──────────────────────────────────────────────────────
    def list_price_lists(self, page=1):
        data = self._get("lista.precos.pesquisa.php", f"&pagina={page}")
        return data.get("listas_precos", data) if isinstance(data, dict) else data


if __name__ == "__main__":
    try:
        client = TinyClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
