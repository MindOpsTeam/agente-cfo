#!/usr/bin/env python3
"""ContaAzul ERP Client (OAuth 2.0) — Agente CFO skill.

Auth: OAuth 2.0 authorization code flow + automatic refresh token.
Base URL: https://api.contaazul.com  (API v1 nova — financeiro)
Docs: https://developers.contaazul.com/docs/financial-apis-openapi/v1
"""

import json as _json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import (
    BaseERPClient, http_request, emit, emit_error, now_iso,
    make_list_response, make_payable_item, make_receivable_item,
)

SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/contaazul.env")
BASE_URL = "https://api.contaazul.com"
TOKEN_URL = f"{BASE_URL}/auth/token"
AUTH_URL = f"{BASE_URL}/auth/authorize"


def _save_tokens(access_token: str, refresh_token: str, expiry: float) -> None:
    """Persist tokens back into secrets file."""
    lines: list[str] = []
    skip_keys = {"CONTAAZUL_ACCESS_TOKEN", "CONTAAZUL_REFRESH_TOKEN", "CONTAAZUL_TOKEN_EXPIRY"}
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                stripped = line.strip()
                key = stripped.split("=", 1)[0] if "=" in stripped else ""
                if stripped and not stripped.startswith("#") and key not in skip_keys:
                    lines.append(stripped)

    lines += [
        f"CONTAAZUL_ACCESS_TOKEN={access_token}",
        f"CONTAAZUL_REFRESH_TOKEN={refresh_token}",
        f"CONTAAZUL_TOKEN_EXPIRY={int(expiry)}",
    ]

    # Simple file lock
    lock_path = SECRETS_FILE + ".lock"
    for _ in range(3):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(0.5)
    else:
        try:
            os.unlink(lock_path)
        except OSError:
            pass

    try:
        with open(SECRETS_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(SECRETS_FILE, 0o600)
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass

    os.environ["CONTAAZUL_ACCESS_TOKEN"] = access_token
    os.environ["CONTAAZUL_REFRESH_TOKEN"] = refresh_token
    os.environ["CONTAAZUL_TOKEN_EXPIRY"] = str(int(expiry))


class ContaAzulClient(BaseERPClient):
    SKILL_NAME = "contaazul"

    def _validate_env(self) -> None:
        for var in ("CONTAAZUL_CLIENT_ID", "CONTAAZUL_CLIENT_SECRET",
                    "CONTAAZUL_ACCESS_TOKEN", "CONTAAZUL_REFRESH_TOKEN"):
            if not os.environ.get(var):
                raise RuntimeError(f"{var} nao definido. Execute connect.sh.")
        self._ensure_token()

    # ── OAuth token management ────────────────────────────────────────────────

    def _ensure_token(self) -> None:
        expiry = int(os.environ.get("CONTAAZUL_TOKEN_EXPIRY", "0") or "0")
        if time.time() + 300 > expiry:
            self._refresh()

    def _refresh(self) -> None:
        import base64
        client_id = os.environ["CONTAAZUL_CLIENT_ID"]
        client_secret = os.environ["CONTAAZUL_CLIENT_SECRET"]
        refresh_token = os.environ["CONTAAZUL_REFRESH_TOKEN"]
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        body = f"grant_type=refresh_token&refresh_token={refresh_token}".encode()
        data = http_request("POST", TOKEN_URL, headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }, body=body)
        if "access_token" not in data:
            raise RuntimeError(f"Falha no refresh token ContaAzul: {data}")
        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", refresh_token)
        expires_in = int(data.get("expires_in", 3600))
        _save_tokens(new_access, new_refresh, time.time() + expires_in)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {os.environ['CONTAAZUL_ACCESS_TOKEN']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: str = "") -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self._headers())

    def _post(self, path: str, body: dict) -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}"
        return http_request("POST", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    def _put(self, path: str, body: dict) -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}"
        return http_request("PUT", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    def _delete(self, path: str) -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}"
        return http_request("DELETE", url, headers=self._headers())

    def _patch(self, path: str, body: dict) -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}"
        return http_request("PATCH", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    # ── Status normalization ──────────────────────────────────────────────────

    @staticmethod
    def _norm_recv_status(s: str) -> str:
        """Map ContaAzul status → unified status (pending|received|overdue)."""
        s = (s or "").upper()
        if s in ("LIQUIDADO", "RECEBIDO", "PAGO"):
            return "received"
        if s in ("ATRASADO", "VENCIDO"):
            return "overdue"
        return "pending"   # ABERTO, AGUARDANDO, etc.

    @staticmethod
    def _norm_pay_status(s: str) -> str:
        """Map ContaAzul status → unified status (pending|paid|overdue)."""
        s = (s or "").upper()
        if s in ("LIQUIDADO", "PAGO"):
            return "paid"
        if s in ("ATRASADO", "VENCIDO"):
            return "overdue"
        return "pending"

    # ── BaseERPClient interface ───────────────────────────────────────────────

    def get_balance(self) -> dict:
        """Sum saldo-atual of all active financial accounts."""
        data = self._get("v1/conta-financeira", "status=ATIVO&tamanhoPagina=100")
        accounts = data.get("itens") or data.get("data") or data.get("content") or []
        if not isinstance(accounts, list):
            # Some versions return a flat list directly
            accounts = []

        total = 0.0
        for acc in accounts:
            acc_id = acc.get("id") or acc.get("idContaFinanceira")
            if not acc_id:
                continue
            try:
                bal = self._get(f"v1/conta-financeira/{acc_id}/saldo-atual")
                saldo = float(bal.get("saldoAtual") or bal.get("saldo") or bal.get("balance") or 0.0)
                total += saldo
            except Exception:
                pass  # skip unavailable accounts silently

        return {"balance_brl": round(total, 2), "as_of": now_iso()}

    def list_receivables(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict:
        params = f"pagina={page}&tamanhoPagina={min(limit, 100)}"
        if from_date:
            params += f"&dataVencimentoInicio={from_date}"
        if to_date:
            params += f"&dataVencimentoFim={to_date}"

        data = self._get(
            "v1/financeiro/eventos-financeiros/contas-a-receber/buscar", params
        )
        raw_items = data.get("itens") or data.get("data") or data.get("content") or []

        items = []
        for r in raw_items:
            # Handle both nested 'parcela' and flat structures
            parcela = r if "dataVencimento" in r else r.get("parcela", r)
            counterparty = (
                (r.get("contato") or {}).get("nome")
                or (r.get("cliente") or {}).get("nome")
                or r.get("descricao", "")
                or ""
            )
            status_raw = parcela.get("status") or r.get("status") or "ABERTO"
            items.append(make_receivable_item(
                id=str(r.get("id") or parcela.get("id") or ""),
                due_date=(parcela.get("dataVencimento") or "")[:10],
                amount_brl=float(parcela.get("valor") or r.get("valor") or 0.0),
                counterparty=counterparty,
                status=self._norm_recv_status(status_raw),
                raw=r,
            ))

        total_pages = data.get("totalPaginas") or data.get("totalPages") or 1
        total_count = data.get("total") or data.get("totalItens") or len(items)
        return make_list_response(items, page=page, total_pages=int(total_pages),
                                  total_count=int(total_count))

    def list_payables(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict:
        params = f"pagina={page}&tamanhoPagina={min(limit, 100)}"
        if from_date:
            params += f"&dataVencimentoInicio={from_date}"
        if to_date:
            params += f"&dataVencimentoFim={to_date}"

        data = self._get(
            "v1/financeiro/eventos-financeiros/contas-a-pagar/buscar", params
        )
        raw_items = data.get("itens") or data.get("data") or data.get("content") or []

        items = []
        for r in raw_items:
            parcela = r if "dataVencimento" in r else r.get("parcela", r)
            counterparty = (
                (r.get("contato") or {}).get("nome")
                or (r.get("fornecedor") or {}).get("nome")
                or r.get("descricao", "")
                or ""
            )
            status_raw = parcela.get("status") or r.get("status") or "ABERTO"
            items.append(make_payable_item(
                id=str(r.get("id") or parcela.get("id") or ""),
                due_date=(parcela.get("dataVencimento") or "")[:10],
                amount_brl=float(parcela.get("valor") or r.get("valor") or 0.0),
                counterparty=counterparty,
                status=self._norm_pay_status(status_raw),
                raw=r,
            ))

        total_pages = data.get("totalPaginas") or data.get("totalPages") or 1
        total_count = data.get("total") or data.get("totalItens") or len(items)
        return make_list_response(items, page=page, total_pages=int(total_pages),
                                  total_count=int(total_count))

    def company_info(self) -> dict:
        try:
            # Try to get company info from token introspection or profile endpoint
            data = self._get("v1/empresa")
            name = (
                data.get("nomeFantasia")
                or data.get("razaoSocial")
                or data.get("nome")
                or "N/A"
            )
            cnpj = data.get("cnpj") or data.get("cpfCnpj")
            return {"name": str(name), "cnpj": cnpj, "segment": "ERP"}
        except Exception:
            return {"name": "N/A", "cnpj": None, "segment": "ERP"}

    # ── Write operations ──────────────────────────────────────────────────────

    def pay_payable(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        # PATCH installment status to LIQUIDADO
        raw = self._patch(f"v1/financeiro/eventos-financeiros/parcelas/{id}", {
            "status": "LIQUIDADO",
            "dataPagamento": today,
        })
        return {
            "success": True, "action": "pay_payable", "id": id,
            "before": {"status": "pending"},
            "after": {"status": "paid", "paid_at": today},
            "raw": raw,
        }

    def mark_received(self, id: str) -> dict:
        from datetime import date
        today = date.today().isoformat()
        raw = self._patch(f"v1/financeiro/eventos-financeiros/parcelas/{id}", {
            "status": "LIQUIDADO",
            "dataPagamento": today,
        })
        return {
            "success": True, "action": "mark_received", "id": id,
            "before": {"status": "pending"},
            "after": {"status": "received", "received_at": today},
            "raw": raw,
        }

    def create_payable(self, amount: float, due_date: str, supplier: str, **kwargs) -> dict:
        body: dict = {
            "valor": amount,
            "condicaoPagamento": {
                "parcelas": [{"dataVencimento": due_date, "valor": amount}]
            },
            "descricao": kwargs.get("description") or supplier,
            "contato": {"nome": supplier},
        }
        if kwargs.get("category"):
            body["categoria"] = {"nome": kwargs["category"]}
        raw = self._post("v1/financeiro/eventos-financeiros/contas-a-pagar", body)
        new_id = str(raw.get("id") or "")
        return {"success": True, "action": "create_payable", "id": new_id, "raw": raw}

    def create_receivable(self, amount: float, due_date: str, customer: str, **kwargs) -> dict:
        body: dict = {
            "valor": amount,
            "condicaoPagamento": {
                "parcelas": [{"dataVencimento": due_date, "valor": amount}]
            },
            "descricao": kwargs.get("description") or customer,
            "contato": {"nome": customer},
        }
        if kwargs.get("category"):
            body["categoria"] = {"nome": kwargs["category"]}
        raw = self._post("v1/financeiro/eventos-financeiros/contas-a-receber", body)
        new_id = str(raw.get("id") or "")
        return {"success": True, "action": "create_receivable", "id": new_id, "raw": raw}

    def cancel_payable(self, id: str) -> dict:
        """ContaAzul não tem DELETE de parcela na v1 pública — marca como cancelado via PATCH."""
        try:
            raw = self._patch(f"v1/financeiro/eventos-financeiros/parcelas/{id}", {
                "status": "CANCELADO",
            })
            return {"success": True, "action": "cancel_payable", "id": id, "raw": raw}
        except Exception as e:
            return {"success": False, "action": "cancel_payable", "id": id,
                    "error": str(e), "note": "ContaAzul pode nao suportar cancelamento via API."}

    # ── Clientes ─────────────────────────────────────────────────────────────

    def list_customers(self, limit: int = 50, page: int = 1, search: str = "") -> dict:
        params = f"page={page}&size={min(limit, 100)}"
        if search:
            params += f"&search={search}"
        return self._get("v1/customers", params)

    def get_customer(self, id: str) -> dict:
        return self._get(f"v1/customers/{id}")

    def create_customer(self, name: str, **kwargs) -> dict:
        body: dict = {"name": name}
        for k in ("email", "document", "phone", "company_name", "notes"):
            if kwargs.get(k):
                body[k] = kwargs[k]
        raw = self._post("v1/customers", body)
        return {"success": True, "action": "create_customer", "id": str(raw.get("id", "")), "raw": raw}

    def update_customer(self, id: str, **kwargs) -> dict:
        body = {k: v for k, v in kwargs.items() if v is not None}
        raw = self._put(f"v1/customers/{id}", body)
        return {"success": True, "action": "update_customer", "id": id, "raw": raw}

    def delete_customer(self, id: str) -> dict:
        raw = self._delete(f"v1/customers/{id}")
        return {"success": True, "action": "delete_customer", "id": id, "raw": raw}

    # ── Produtos ─────────────────────────────────────────────────────────────

    def list_products(self, limit: int = 50, page: int = 1, search: str = "") -> dict:
        params = f"page={page}&size={min(limit, 100)}"
        if search:
            params += f"&search={search}"
        return self._get("v1/products", params)

    def get_product(self, id: str) -> dict:
        return self._get(f"v1/products/{id}")

    def create_product(self, name: str, value: float, **kwargs) -> dict:
        body: dict = {"name": name, "value": value}
        for k in ("cost", "code", "barcode", "net_weight", "gross_weight", "category_id"):
            if kwargs.get(k) is not None:
                body[k] = kwargs[k]
        raw = self._post("v1/products", body)
        return {"success": True, "action": "create_product", "id": str(raw.get("id", "")), "raw": raw}

    def update_product(self, id: str, **kwargs) -> dict:
        body = {k: v for k, v in kwargs.items() if v is not None}
        raw = self._put(f"v1/products/{id}", body)
        return {"success": True, "action": "update_product", "id": id, "raw": raw}

    # ── Pedidos de venda (Sales) ─────────────────────────────────────────────

    def list_sales(self, limit: int = 50, page: int = 1) -> dict:
        params = f"page={page}&size={min(limit, 100)}"
        return self._get("v1/sales", params)

    def get_sale(self, id: str) -> dict:
        return self._get(f"v1/sales/{id}")

    def create_sale(self, customer_id: str, products: list, **kwargs) -> dict:
        body: dict = {"customer_id": customer_id, "products": products}
        for k in ("emission", "discount", "notes", "payment_type"):
            if kwargs.get(k) is not None:
                body[k] = kwargs[k]
        raw = self._post("v1/sales", body)
        return {"success": True, "action": "create_sale", "id": str(raw.get("id", "")), "raw": raw}

    # ── Contas a pagar / receber — get e delete individuais ──────────────────

    def get_payable(self, id: str) -> dict:
        return self._get(f"v1/financeiro/eventos-financeiros/contas-a-pagar/{id}")

    def delete_payable(self, id: str) -> dict:
        raw = self._delete(f"v1/financeiro/eventos-financeiros/contas-a-pagar/{id}")
        return {"success": True, "action": "delete_payable", "id": id, "raw": raw}

    def get_receivable(self, id: str) -> dict:
        return self._get(f"v1/financeiro/eventos-financeiros/contas-a-receber/{id}")

    def delete_receivable(self, id: str) -> dict:
        raw = self._delete(f"v1/financeiro/eventos-financeiros/contas-a-receber/{id}")
        return {"success": True, "action": "delete_receivable", "id": id, "raw": raw}

    # ── NF-e ─────────────────────────────────────────────────────────────────

    def list_nfes(self, limit: int = 50, page: int = 1) -> dict:
        params = f"page={page}&size={min(limit, 100)}"
        return self._get("v1/nfes", params)

    def get_nfe(self, id: str) -> dict:
        return self._get(f"v1/nfes/{id}")

    def create_nfe(self, sale_id: str, **kwargs) -> dict:
        body: dict = {"sale_id": sale_id}
        for k in ("nature_of_operation", "notes"):
            if kwargs.get(k) is not None:
                body[k] = kwargs[k]
        raw = self._post("v1/nfes", body)
        return {"success": True, "action": "create_nfe", "id": str(raw.get("id", "")), "raw": raw}

    # ── Contas bancárias ─────────────────────────────────────────────────────

    def list_bank_accounts(self) -> dict:
        return self._get("v1/bankaccounts")

    # ── Categorias ───────────────────────────────────────────────────────────

    def list_categories(self) -> dict:
        return self._get("v1/categories")

    # ── Serviços ─────────────────────────────────────────────────────────────

    def list_services(self, limit: int = 50, page: int = 1, search: str = "") -> dict:
        params = f"page={page}&size={min(limit, 100)}"
        if search:
            params += f"&search={search}"
        return self._get("v1/services", params)

    def get_service(self, id: str) -> dict:
        return self._get(f"v1/services/{id}")


if __name__ == "__main__":
    try:
        client = ContaAzulClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
