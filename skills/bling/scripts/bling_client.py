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


if __name__ == "__main__":
    try:
        client = BlingClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
