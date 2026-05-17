#!/usr/bin/env python3
"""Bling ERP v3 Client (OAuth 2.0) — Agente CFO skill."""

import base64
import json
import os
import sys
import time

import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseERPClient, http_request, emit, emit_error, now_iso, make_list_response

SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/bling.env")


def _save_tokens(access_token, refresh_token, expiry):
    """Update tokens in secrets file."""
    lines = []
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BLING_ACCESS_TOKEN="):
                    continue
                if line.startswith("BLING_REFRESH_TOKEN="):
                    continue
                if line.startswith("BLING_TOKEN_EXPIRY="):
                    continue
                if line:
                    lines.append(line)
    lines.append(f"BLING_ACCESS_TOKEN={access_token}")
    lines.append(f"BLING_REFRESH_TOKEN={refresh_token}")
    lines.append(f"BLING_TOKEN_EXPIRY={int(expiry)}")

    # Simple file locking
    lock_path = SECRETS_FILE + ".lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        time.sleep(1)
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            os.unlink(lock_path)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)

    try:
        with open(SECRETS_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(SECRETS_FILE, 0o600)
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass

    os.environ["BLING_ACCESS_TOKEN"] = access_token
    os.environ["BLING_REFRESH_TOKEN"] = refresh_token
    os.environ["BLING_TOKEN_EXPIRY"] = str(int(expiry))


class BlingClient(BaseERPClient):
    SKILL_NAME = "bling"
    BASE_URL = "https://api.bling.com.br/Api/v3"

    def _validate_env(self):
        for var in ("BLING_CLIENT_ID", "BLING_CLIENT_SECRET", "BLING_ACCESS_TOKEN", "BLING_REFRESH_TOKEN"):
            if not os.environ.get(var):
                raise RuntimeError(f"{var} nao definido. Execute connect.sh.")
        self._ensure_token()

    def _ensure_token(self):
        expiry = int(os.environ.get("BLING_TOKEN_EXPIRY", "0") or "0")
        if time.time() + 300 > expiry:
            self._refresh()

    def _refresh(self):
        client_id = os.environ["BLING_CLIENT_ID"]
        client_secret = os.environ["BLING_CLIENT_SECRET"]
        refresh_token = os.environ["BLING_REFRESH_TOKEN"]
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        body = f"grant_type=refresh_token&refresh_token={refresh_token}".encode()
        data = http_request("POST", f"{self.BASE_URL}/oauth/token", headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }, body=body)
        if "access_token" not in data:
            raise RuntimeError(f"Falha no refresh token: {data}")
        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", refresh_token)
        expires_in = int(data.get("expires_in", 7200))
        new_expiry = time.time() + expires_in
        _save_tokens(new_access, new_refresh, new_expiry)

    def _headers(self):
        return {
            "Authorization": f"Bearer {os.environ['BLING_ACCESS_TOKEN']}",
            "Content-Type": "application/json",
        }

    def _get(self, path, params=""):
        self._ensure_token()
        url = f"{self.BASE_URL}/{path}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self._headers())

    def get_balance(self):
        data = self._get("contas-correntes")
        contas = data.get("data", []) if isinstance(data, dict) else []
        saldo = sum(float(c.get("saldo", 0) or 0) for c in contas)
        return {"balance_brl": round(saldo, 2), "as_of": now_iso()}

    def list_payables(self, from_date=None, to_date=None, limit=50, page=1):
        params = f"pagina={page}&limite={min(limit, 100)}&situacoes[]=1&situacoes[]=2"
        if from_date:
            params += f"&dataVencimentoInicio={from_date}"
        if to_date:
            params += f"&dataVencimentoFinal={to_date}"
        data = self._get("contas-pagar", params)
        items = []
        records = data.get("data", []) if isinstance(data, dict) else []
        for r in records:
            fornecedor = r.get("fornecedor", {}) or {}
            sit = int(r.get("situacao", 1) or 1)
            items.append({
                "id": str(r.get("id", "")),
                "due_date": (r.get("dataVencimento", "") or "")[:10],
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": fornecedor.get("nome", ""),
                "status": "paid" if sit == 3 else "pending",
                "category": None,
                "raw": r,
            })
        total = len(items)
        return make_list_response(items, page=page, total_count=total)

    def list_receivables(self, from_date=None, to_date=None, limit=50, page=1):
        params = f"pagina={page}&limite={min(limit, 100)}&situacoes[]=1"
        if from_date:
            params += f"&dataVencimentoInicio={from_date}"
        if to_date:
            params += f"&dataVencimentoFinal={to_date}"
        data = self._get("contas-receber", params)
        items = []
        records = data.get("data", []) if isinstance(data, dict) else []
        for r in records:
            contato = r.get("contato", {}) or {}
            sit = int(r.get("situacao", 1) or 1)
            items.append({
                "id": str(r.get("id", "")),
                "due_date": (r.get("dataVencimento", "") or "")[:10],
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": contato.get("nome", ""),
                "status": "received" if sit == 3 else "pending",
                "category": None,
                "raw": r,
            })
        total = len(items)
        return make_list_response(items, page=page, total_count=total)

    def _post(self, path, body: dict):
        self._ensure_token()
        url = f"{self.BASE_URL}/{path}"
        return http_request("POST", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    def pay_payable(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._post(f"contas-pagar/{id}/baixas", {
            "data": today, "valor": 0,  # valor 0 = baixa total
        })
        return {"success": True, "action": "pay_payable", "id": id,
                "before": {"status": "pending"}, "after": {"status": "paid", "paid_at": today}, "raw": raw}

    def mark_received(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._post(f"contas-receber/{id}/baixas", {
            "data": today, "valor": 0,
        })
        return {"success": True, "action": "mark_received", "id": id,
                "before": {"status": "pending"}, "after": {"status": "received", "received_at": today}, "raw": raw}

    def create_payable(self, amount: float, due_date: str, supplier: str, **kwargs) -> dict:
        body = {
            "valor": amount,
            "dataVencimento": due_date,
            "fornecedor": {"nome": supplier},
        }
        if kwargs.get("description"):
            body["historico"] = kwargs["description"]
        raw = self._post("contas-pagar", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_payable", "id": str(new_id), "raw": raw}

    def create_receivable(self, amount: float, due_date: str, customer: str, **kwargs) -> dict:
        body = {
            "valor": amount,
            "dataVencimento": due_date,
            "contato": {"nome": customer},
        }
        if kwargs.get("description"):
            body["historico"] = kwargs["description"]
        raw = self._post("contas-receber", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_receivable", "id": str(new_id), "raw": raw}

    def company_info(self):
        try:
            data = self._get("empresas")
            empresas = data.get("data", []) if isinstance(data, dict) else []
            if empresas:
                e = empresas[0]
                return {"name": e.get("nome", "N/A"), "cnpj": e.get("cnpj"), "segment": "ERP"}
        except Exception:
            pass
        return {"name": "N/A", "cnpj": None, "segment": "ERP"}

    # ── PUT / DELETE helpers ────────────────────────────────────────────────
    def _put(self, path, body: dict):
        self._ensure_token()
        url = f"{self.BASE_URL}/{path}"
        return http_request("PUT", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    def _delete(self, path):
        self._ensure_token()
        url = f"{self.BASE_URL}/{path}"
        return http_request("DELETE", url, headers=self._headers())

    # ── Produtos ────────────────────────────────────────────────────────────
    def list_products(self, page=1, limit=100, nome=None):
        params = f"pagina={page}&limite={min(limit, 100)}"
        if nome:
            params += f"&nome={nome}"
        data = self._get("produtos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_product(self, id: str):
        data = self._get(f"produtos/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_product(self, body: dict):
        raw = self._post("produtos", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_product", "id": str(new_id), "raw": raw}

    def update_product(self, id: str, body: dict):
        raw = self._put(f"produtos/{id}", body)
        return {"success": True, "action": "update_product", "id": id, "raw": raw}

    def delete_product(self, id: str):
        raw = self._delete(f"produtos/{id}")
        return {"success": True, "action": "delete_product", "id": id, "raw": raw}

    # ── Pedidos de Venda ────────────────────────────────────────────────────
    def list_sales_orders(self, page=1, limit=100, from_date=None, to_date=None):
        params = f"pagina={page}&limite={min(limit, 100)}"
        if from_date:
            params += f"&dataInicio={from_date}"
        if to_date:
            params += f"&dataFim={to_date}"
        data = self._get("pedidos/vendas", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_sales_order(self, id: str):
        data = self._get(f"pedidos/vendas/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_sales_order(self, body: dict):
        raw = self._post("pedidos/vendas", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_sales_order", "id": str(new_id), "raw": raw}

    # ── NF-e ────────────────────────────────────────────────────────────────
    def list_nfe(self, page=1, limit=100, from_date=None, to_date=None):
        params = f"pagina={page}&limite={min(limit, 100)}"
        if from_date:
            params += f"&dataEmissaoInicio={from_date}"
        if to_date:
            params += f"&dataEmissaoFinal={to_date}"
        data = self._get("nfe", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_nfe(self, id: str):
        data = self._get(f"nfe/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_nfe(self, body: dict):
        raw = self._post("nfe", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_nfe", "id": str(new_id), "raw": raw}

    def transmit_nfe(self, id: str):
        raw = self._post(f"nfe/{id}/transmitir", {})
        return {"success": True, "action": "transmit_nfe", "id": id, "raw": raw}

    # ── NFC-e ───────────────────────────────────────────────────────────────
    def list_nfce(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("nfce", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_nfce(self, id: str):
        data = self._get(f"nfce/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    # ── Contatos (Clientes / Fornecedores) ──────────────────────────────────
    def list_contacts(self, page=1, limit=100, nome=None, tipo=None):
        params = f"pagina={page}&limite={min(limit, 100)}"
        if nome:
            params += f"&nome={nome}"
        if tipo:
            params += f"&tipo={tipo}"
        data = self._get("contatos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_contact(self, id: str):
        data = self._get(f"contatos/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_contact(self, body: dict):
        raw = self._post("contatos", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_contact", "id": str(new_id), "raw": raw}

    def update_contact(self, id: str, body: dict):
        raw = self._put(f"contatos/{id}", body)
        return {"success": True, "action": "update_contact", "id": id, "raw": raw}

    # ── Estoque ─────────────────────────────────────────────────────────────
    def get_stock(self, product_id: str):
        data = self._get(f"estoques/saldos", f"idsProdutos[]={product_id}")
        items = data.get("data", []) if isinstance(data, dict) else []
        return items[0] if items else {"product_id": product_id, "saldo": 0}

    def adjust_stock(self, product_id: str, quantity: float, operation: str = "B", notes: str = ""):
        """operation: B=Balanço, E=Entrada, S=Saída"""
        body = {
            "produto": {"id": int(product_id)},
            "quantidade": quantity,
            "operacao": operation,
        }
        if notes:
            body["observacoes"] = notes
        raw = self._post("estoques", body)
        return {"success": True, "action": "adjust_stock", "product_id": product_id, "raw": raw}

    # ── Categorias ──────────────────────────────────────────────────────────
    def list_categories(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("categorias/produtos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def list_overdue(self) -> dict:
        """Filtra payables + receivables vencidos (due_date < hoje, status nao pago/recebido).

        Retorna lista padronizada com campos extras: description, days_overdue, record_type.
        Itera todas as paginas para nao perder registros.
        """
        from datetime import date

        today = date.today()
        today_str = today.isoformat()
        overdue: list = []

        def _fetch_all_payables():
            page = 1
            while True:
                resp = self.list_payables(limit=100, page=page)
                items = resp.get("items", [])
                for item in items:
                    if item.get("status") == "pending":
                        due = item.get("due_date", "9999-99-99")
                        if due and due < today_str:
                            try:
                                days_overdue = (today - date.fromisoformat(due)).days
                            except Exception:
                                days_overdue = 0
                            overdue.append({
                                "id": item["id"],
                                "description": item.get("counterparty", ""),
                                "amount": item.get("amount_brl", 0.0),
                                "due_date": due,
                                "days_overdue": days_overdue,
                                "record_type": "pay",
                                "raw": item,
                            })
                total_pages = resp.get("total_pages", 1)
                if page >= total_pages or len(items) < 100:
                    break
                page += 1

        def _fetch_all_receivables():
            page = 1
            while True:
                resp = self.list_receivables(limit=100, page=page)
                items = resp.get("items", [])
                for item in items:
                    if item.get("status") == "pending":
                        due = item.get("due_date", "9999-99-99")
                        if due and due < today_str:
                            try:
                                days_overdue = (today - date.fromisoformat(due)).days
                            except Exception:
                                days_overdue = 0
                            overdue.append({
                                "id": item["id"],
                                "description": item.get("counterparty", ""),
                                "amount": item.get("amount_brl", 0.0),
                                "due_date": due,
                                "days_overdue": days_overdue,
                                "record_type": "recv",
                                "raw": item,
                            })
                total_pages = resp.get("total_pages", 1)
                if page >= total_pages or len(items) < 100:
                    break
                page += 1

        _fetch_all_payables()
        _fetch_all_receivables()
        overdue.sort(key=lambda x: x["due_date"])
        return make_list_response(overdue, total_count=len(overdue))

    def cancel_payable(self, id: str) -> dict:
        """Cancela conta a pagar via DELETE /contas-pagar/{id}.

        A API Bling v3 suporta exclusao de titulos nao liquidados via DELETE.
        """
        raw = self._delete(f"contas-pagar/{id}")
        return {"success": True, "action": "cancel_payable", "id": id, "raw": raw}

    # ── Contas a pagar — extras ─────────────────────────────────────────────
    def get_payable(self, id: str):
        data = self._get(f"contas-pagar/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def delete_payable(self, id: str):
        raw = self._delete(f"contas-pagar/{id}")
        return {"success": True, "action": "delete_payable", "id": id, "raw": raw}

    # ── Contas a receber — extras ───────────────────────────────────────────
    def get_receivable(self, id: str):
        data = self._get(f"contas-receber/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def delete_receivable(self, id: str):
        raw = self._delete(f"contas-receber/{id}")
        return {"success": True, "action": "delete_receivable", "id": id, "raw": raw}

    # ── Formas de Pagamento ─────────────────────────────────────────────────
    def list_payment_methods(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("formas-pagamentos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── Contas Correntes ────────────────────────────────────────────────────
    def list_bank_accounts(self):
        data = self._get("contas-correntes")
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=1, total_count=len(items))

    # ── Contatos extras ─────────────────────────────────────────────────────
    def delete_contact(self, id: str):
        raw = self._delete(f"contatos/{id}")
        return {"success": True, "action": "delete_contact", "id": id, "raw": raw}

    # ── Produtos extras ────────────────────────────────────────────────────
    def list_product_situations(self):
        data = self._get("produtos/situacoes")
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=1, total_count=len(items))

    # ── Pedidos de Venda extras ────────────────────────────────────────────
    def update_sales_order(self, id: str, body: dict):
        raw = self._put(f"pedidos/vendas/{id}", body)
        return {"success": True, "action": "update_sales_order", "id": id, "raw": raw}

    def delete_sales_order(self, id: str):
        raw = self._delete(f"pedidos/vendas/{id}")
        return {"success": True, "action": "delete_sales_order", "id": id, "raw": raw}

    # ── NF-e extras ────────────────────────────────────────────────────────
    def cancel_nfe(self, id: str):
        raw = self._post(f"nfe/{id}/cancelar", {})
        return {"success": True, "action": "cancel_nfe", "id": id, "raw": raw}

    def get_nfe_xml(self, id: str):
        data = self._get(f"nfe/{id}/xml")
        return data

    # ── NFC-e extras ───────────────────────────────────────────────────────
    def create_nfce(self, body: dict):
        raw = self._post("nfce", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_nfce", "id": str(new_id), "raw": raw}

    def transmit_nfce(self, id: str):
        raw = self._post(f"nfce/{id}/transmitir", {})
        return {"success": True, "action": "transmit_nfce", "id": id, "raw": raw}

    def cancel_nfce(self, id: str):
        raw = self._post(f"nfce/{id}/cancelar", {})
        return {"success": True, "action": "cancel_nfce", "id": id, "raw": raw}

    # ── Contas a pagar extras ──────────────────────────────────────────────
    def update_payable(self, id: str, body: dict):
        raw = self._put(f"contas-pagar/{id}", body)
        return {"success": True, "action": "update_payable", "id": id, "raw": raw}

    def reverse_payable(self, id: str):
        raw = self._post(f"contas-pagar/{id}/estornar", {})
        return {"success": True, "action": "reverse_payable", "id": id, "raw": raw}

    # ── Contas a receber extras ────────────────────────────────────────────
    def update_receivable(self, id: str, body: dict):
        raw = self._put(f"contas-receber/{id}", body)
        return {"success": True, "action": "update_receivable", "id": id, "raw": raw}

    def reverse_receivable(self, id: str):
        raw = self._post(f"contas-receber/{id}/estornar", {})
        return {"success": True, "action": "reverse_receivable", "id": id, "raw": raw}

    # ── Contas correntes extras ────────────────────────────────────────────
    def get_bank_account(self, id: str):
        data = self._get(f"contas-correntes/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def get_bank_account_balance(self, id: str):
        data = self._get(f"contas-correntes/{id}/saldo")
        return data.get("data", data) if isinstance(data, dict) else data

    # ── Fornecedores ───────────────────────────────────────────────────────
    def list_suppliers(self, page=1, limit=100, nome=None):
        params = f"pagina={page}&limite={min(limit, 100)}&tipo=F"
        if nome:
            params += f"&nome={nome}"
        data = self._get("contatos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_supplier(self, id: str):
        return self.get_contact(id)

    def create_supplier(self, body: dict):
        body.setdefault("tipo", "F")
        return self.create_contact(body)

    def update_supplier(self, id: str, body: dict):
        return self.update_contact(id, body)

    # ── Categorias financeiras ─────────────────────────────────────────────
    def list_financial_categories(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("categorias/receitas-despesas", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── Situacoes ──────────────────────────────────────────────────────────
    def list_module_situations(self, module: str = ""):
        params = f"modulo={module}" if module else ""
        data = self._get("situacoes/modulos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=1, total_count=len(items))

    # ── Campos customizados ────────────────────────────────────────────────
    def list_custom_fields(self, module: str = ""):
        params = f"modulo={module}" if module else ""
        data = self._get("campos-customizados", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=1, total_count=len(items))

    # ── Depositos ──────────────────────────────────────────────────────────
    def list_warehouses(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("depositos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_warehouse(self, id: str):
        data = self._get(f"depositos/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    # ── Empresa detalhada ──────────────────────────────────────────────────
    def get_company_detail(self):
        data = self._get("empresas")
        empresas = data.get("data", []) if isinstance(data, dict) else []
        return empresas[0] if empresas else {}

    # ── Servicos ───────────────────────────────────────────────────────────
    def list_services(self, page=1, limit=100, nome=None):
        params = f"pagina={page}&limite={min(limit, 100)}"
        if nome:
            params += f"&nome={nome}"
        data = self._get("servicos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_service(self, id: str):
        data = self._get(f"servicos/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_service(self, body: dict):
        raw = self._post("servicos", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_service", "id": str(new_id), "raw": raw}

    # ── Logisticas ─────────────────────────────────────────────────────────
    def list_logistics(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("logisticas", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_logistics(self, id: str):
        data = self._get(f"logisticas/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    # ── Pedidos de Compra ──────────────────────────────────────────────────
    def list_purchase_orders(self, page=1, limit=100, from_date=None, to_date=None):
        params = f"pagina={page}&limite={min(limit, 100)}"
        if from_date:
            params += f"&dataInicio={from_date}"
        if to_date:
            params += f"&dataFim={to_date}"
        data = self._get("pedidos/compras", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_purchase_order(self, id: str):
        data = self._get(f"pedidos/compras/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_purchase_order(self, body: dict):
        raw = self._post("pedidos/compras", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_purchase_order", "id": str(new_id), "raw": raw}

    # ── Formatos ───────────────────────────────────────────────────────────
    def list_formats(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("formatos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── Webhooks ───────────────────────────────────────────────────────────
    def list_webhooks(self):
        data = self._get("callbacks")
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=1, total_count=len(items))

    def create_webhook(self, body: dict):
        raw = self._post("callbacks", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_webhook", "id": str(new_id), "raw": raw}

    def delete_webhook(self, id: str):
        raw = self._delete(f"callbacks/{id}")
        return {"success": True, "action": "delete_webhook", "id": id, "raw": raw}

    # ── Estoque movimentacoes ──────────────────────────────────────────────
    def list_stock_movements(self, page=1, limit=100, product_id=None):
        params = f"pagina={page}&limite={min(limit, 100)}"
        if product_id:
            params += f"&idsProdutos[]={product_id}"
        data = self._get("estoques/movimentacoes", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── Estoque saldos ─────────────────────────────────────────────────────
    def list_stock_balances(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("estoques/saldos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── NF-e de Servico (NFS-e) ────────────────────────────────────────────
    def list_nfse(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("nfse", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_nfse(self, id: str):
        data = self._get(f"nfse/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_nfse(self, body: dict):
        raw = self._post("nfse", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_nfse", "id": str(new_id), "raw": raw}

    def transmit_nfse(self, id: str):
        raw = self._post(f"nfse/{id}/transmitir", {})
        return {"success": True, "action": "transmit_nfse", "id": id, "raw": raw}

    def cancel_nfse(self, id: str):
        raw = self._post(f"nfse/{id}/cancelar", {})
        return {"success": True, "action": "cancel_nfse", "id": id, "raw": raw}

    # ── Vendedores ─────────────────────────────────────────────────────────
    def list_sellers(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("vendedores", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_seller(self, id: str):
        data = self._get(f"vendedores/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_seller(self, body: dict):
        raw = self._post("vendedores", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_seller", "id": str(new_id), "raw": raw}

    # ── Natureza de operacao ───────────────────────────────────────────────
    def list_nature_operations(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("naturezas-operacoes", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── Formas de recebimento ──────────────────────────────────────────────
    def list_receipt_methods(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("formas-recebimentos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── Pedidos venda situacoes ────────────────────────────────────────────
    def list_sales_order_situations(self):
        data = self._get("pedidos/vendas/situacoes")
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=1, total_count=len(items))

    # ── Borderos ───────────────────────────────────────────────────────────
    def list_borderos(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("borderos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_bordero(self, id: str):
        data = self._get(f"borderos/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    # ── Transferencias ─────────────────────────────────────────────────────
    def list_transfers(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("transferencias", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def create_transfer(self, body: dict):
        raw = self._post("transferencias", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_transfer", "id": str(new_id), "raw": raw}

    # ── Homologacao ────────────────────────────────────────────────────────
    def list_homologations(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("homologacoes", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    # ── Contratos ──────────────────────────────────────────────────────────
    def list_contracts(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("contratos", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_contract(self, id: str):
        data = self._get(f"contratos/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_contract(self, body: dict):
        raw = self._post("contratos", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_contract", "id": str(new_id), "raw": raw}

    # ── Propostas comerciais ───────────────────────────────────────────────
    def list_proposals(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("propostas-comerciais", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_proposal(self, id: str):
        data = self._get(f"propostas-comerciais/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_proposal(self, body: dict):
        raw = self._post("propostas-comerciais", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_proposal", "id": str(new_id), "raw": raw}

    # ── Ordem de producao ──────────────────────────────────────────────────
    def list_production_orders(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("ordens-producao", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_production_order(self, id: str):
        data = self._get(f"ordens-producao/{id}")
        return data.get("data", data) if isinstance(data, dict) else data

    def create_production_order(self, body: dict):
        raw = self._post("ordens-producao", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_production_order", "id": str(new_id), "raw": raw}

    # ── Notas de compra ────────────────────────────────────────────────────
    def list_purchase_notes(self, page=1, limit=100):
        params = f"pagina={page}&limite={min(limit, 100)}"
        data = self._get("notas-compras", params)
        items = data.get("data", []) if isinstance(data, dict) else []
        return make_list_response(items, page=page, total_count=len(items))

    def get_purchase_note(self, id: str):
        data = self._get(f"notas-compras/{id}")
        return data.get("data", data) if isinstance(data, dict) else data


if __name__ == "__main__":
    try:
        client = BlingClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
