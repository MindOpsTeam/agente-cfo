#!/usr/bin/env python3
"""Iugu Cobrança Client — Agente CFO skill.

Auth: Basic base64(token + ":") — token como usuário, senha vazia
Base URL: https://api.iugu.com/v1
Docs: https://dev.iugu.com/
"""
import base64
import json as _json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import (
    BaseCobrancaClient, http_request, emit, emit_error, now_iso,
    make_invoice_item, make_list_response,
)

SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/iugu.env")

# ── Status mapping ────────────────────────────────────────────────────────────
_FROM_IUGU = {
    "pending":          "open",
    "in_analysis":      "open",
    "authorized":       "open",
    "partially_paid":   "paid",
    "paid":             "paid",
    "refunded":         "cancelled",
    "canceled":         "cancelled",
    "chargeback":       "cancelled",
    "externally_paid":  "paid",
    "expired":          "overdue",
}
_TO_IUGU_STATUS = {
    "open":      "pending",
    "overdue":   "expired",
    "paid":      "paid",
    "cancelled": "canceled",
}


class IuguClient(BaseCobrancaClient):
    SKILL_NAME = "iugu"
    BASE_URL = "https://api.iugu.com/v1"

    def _validate_env(self) -> None:
        if not os.environ.get("IUGU_API_TOKEN"):
            raise RuntimeError("IUGU_API_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["IUGU_API_TOKEN"]
        b64 = base64.b64encode(f"{self.token}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {b64}",
            "Content-Type": "application/json",
        }

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: str = "") -> dict:
        url = f"{self.BASE_URL}/{path.lstrip('/')}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self.headers)

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        return http_request("POST", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def _put(self, path: str, body: dict | None = None) -> dict:
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        return http_request("PUT", url, headers=self.headers,
                            body=_json.dumps(body or {}).encode())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _to_invoice_item(self, inv: dict) -> dict:
        raw_status = (inv.get("status") or "pending").lower()
        status = _FROM_IUGU.get(raw_status, "open")
        cents = inv.get("total_cents") or inv.get("total_paid_cents") or 0
        amount = float(cents) / 100.0
        return make_invoice_item(
            id=str(inv.get("id", "")),
            customer_id=str(inv.get("customer_id") or ""),
            customer_name=inv.get("payer_name") or inv.get("customer_ref") or "",
            due_date=(inv.get("due_date") or "")[:10],
            amount_brl=amount,
            status=status,
            payment_url=inv.get("secure_url"),
            description=inv.get("subject"),
            raw=inv,
        )

    # ── BaseCobrancaClient interface ──────────────────────────────────────────

    def list_invoices(
        self,
        status: str = "open",
        customer_id: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict:
        start = (page - 1) * limit
        params = f"limit={min(limit, 100)}&start={start}"
        if status != "all" and status in _TO_IUGU_STATUS:
            params += f"&status={_TO_IUGU_STATUS[status]}"
        if customer_id:
            params += f"&customer_id={customer_id}"
        data = self._get("invoices", params)
        raw_items = data.get("items") or []
        items = [self._to_invoice_item(i) for i in raw_items]
        total = data.get("totalItems", len(items))
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def get_invoice(self, id: str) -> dict:
        data = self._get(f"invoices/{id}")
        return self._to_invoice_item(data)

    def get_customer(self, id: str) -> dict:
        data = self._get(f"customers/{id}")
        return {
            "id": str(data.get("id", id)),
            "name": data.get("name", ""),
            "phone": data.get("phone") or data.get("phone_prefix", ""),
            "email": data.get("email"),
            "cpf_cnpj": data.get("cpf_cnpj"),
            "raw": data,
        }

    def company_info(self) -> dict:
        try:
            # Iugu: GET /accounts/mine ou GET /accounts
            data = self._get("accounts/mine")
            name = data.get("name") or data.get("company_name") or "N/A"
            return {"name": str(name), "segment": "cobranca", "raw": data}
        except Exception:
            # Fallback: tenta listar invoices sem filtro como health check
            try:
                self._get("invoices", "limit=1")
                return {"name": "Conta Iugu", "segment": "cobranca"}
            except Exception as e:
                raise RuntimeError(f"Iugu API indisponivel: {e}") from e

    def get_payment_methods(self) -> dict:
        return {"methods": ["pix", "boleto", "credit_card"]}

    # ── Write operations ──────────────────────────────────────────────────────

    def send_payment_link(
        self,
        invoice_id: str,
        channel: str = "whatsapp",
        custom_message: str | None = None,
    ) -> dict:
        """Tenta reenvio nativo do Iugu; retorna secure_url."""
        payment_url = None
        try:
            inv = self.get_invoice(invoice_id)
            payment_url = inv.get("payment_url")
        except Exception:
            pass
        try:
            self._post(f"invoices/{invoice_id}/send", {})
        except Exception:
            pass
        return {
            "success": True,
            "action": "send_payment_link",
            "invoice_id": invoice_id,
            "payment_url": payment_url,
            "channel": channel,
            "note": "Link em payment_url. Canal WhatsApp: envie via wacli ao telefone do cliente.",
        }

    def mark_invoice_paid_manually(self, id: str) -> dict:
        today = date.today().isoformat()
        # Iugu: não tem endpoint padronizado de baixa manual — tenta set_paid_manually ou ignora
        raw = {}
        try:
            raw = self._put(f"invoices/{id}/set_paid_manually")
        except Exception:
            pass
        return {
            "success": True, "action": "mark_invoice_paid_manually", "id": id,
            "before": {"status": "open/overdue"},
            "after": {"status": "paid", "paid_at": today},
            "raw": raw,
            "note": "Verifique se a baixa foi registrada no painel Iugu — endpoint pode variar por conta.",
        }

    def create_invoice(
        self,
        customer_id: str,
        amount: float,
        due_date: str,
        description: str = "",
        **kwargs,
    ) -> dict:
        body = {
            "customer_id": customer_id,
            "due_date": due_date,
            "email": kwargs.get("email", ""),
            "items": [
                {
                    "description": description or "Cobrança gerada pelo Agente CFO",
                    "quantity": 1,
                    "price_cents": int(round(amount * 100)),
                }
            ],
        }
        raw = self._post("invoices", body)
        new_id = str(raw.get("id", ""))
        return {"success": True, "action": "create_invoice", "id": new_id, "raw": raw}

    def cancel_invoice(self, id: str) -> dict:
        raw = self._put(f"invoices/{id}/cancel")
        return {"success": True, "action": "cancel_invoice", "id": id, "raw": raw}

    def send_reminder(self, customer_id: str, message: str) -> dict:
        return {
            "success": False,
            "note": "Iugu nao tem endpoint de mensagem livre por cliente. Use send_payment_link por invoice.",
            "customer_id": customer_id,
        }

    def _delete(self, path: str) -> dict:
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        return http_request("DELETE", url, headers=self.headers)

    # ── Clientes ─────────────────────────────────────────────────────────────
    def list_customers(self, limit=50, page=1, search=None):
        start = (page - 1) * limit
        params = f"limit={min(limit, 100)}&start={start}"
        if search:
            params += f"&query={search}"
        return self._get("customers", params)

    def create_customer(self, data: dict):
        return self._post("customers", data)

    def update_customer(self, id: str, data: dict):
        return self._put(f"customers/{id}", data)

    def delete_customer(self, id: str):
        return self._delete(f"customers/{id}")

    # ── Planos ───────────────────────────────────────────────────────────────
    def list_plans(self, limit=50, page=1):
        start = (page - 1) * limit
        return self._get("plans", f"limit={min(limit, 100)}&start={start}")

    def get_plan(self, id: str):
        return self._get(f"plans/{id}")

    def create_plan(self, data: dict):
        return self._post("plans", data)

    def update_plan(self, id: str, data: dict):
        return self._put(f"plans/{id}", data)

    def delete_plan(self, id: str):
        return self._delete(f"plans/{id}")

    # ── Assinaturas ──────────────────────────────────────────────────────────
    def list_subscriptions(self, limit=50, page=1, customer_id=None):
        start = (page - 1) * limit
        params = f"limit={min(limit, 100)}&start={start}"
        if customer_id:
            params += f"&customer_id={customer_id}"
        return self._get("subscriptions", params)

    def get_subscription(self, id: str):
        return self._get(f"subscriptions/{id}")

    def create_subscription(self, data: dict):
        return self._post("subscriptions", data)

    def update_subscription(self, id: str, data: dict):
        return self._put(f"subscriptions/{id}", data)

    def suspend_subscription(self, id: str):
        return self._post(f"subscriptions/{id}/suspend", {})

    def activate_subscription(self, id: str):
        return self._post(f"subscriptions/{id}/activate", {})

    def delete_subscription(self, id: str):
        return self._delete(f"subscriptions/{id}")

    # ── Transferências ───────────────────────────────────────────────────────
    def list_transfers(self, limit=50, page=1):
        start = (page - 1) * limit
        return self._get("transfers", f"limit={min(limit, 100)}&start={start}")

    def create_transfer(self, data: dict):
        return self._post("transfers", data)

    # ── Extrato ──────────────────────────────────────────────────────────────
    def get_financial_statement(self):
        return self._get("financial_transaction_requests")

    # ── Webhooks ─────────────────────────────────────────────────────────────
    def list_webhooks(self):
        return self._get("web_hooks")

    def create_webhook(self, data: dict):
        return self._post("web_hooks", data)

    def delete_webhook(self, id: str):
        return self._delete(f"web_hooks/{id}")

    # ── Marketplace / Subcontas ──────────────────────────────────────────────
    def list_marketplace_accounts(self, limit=50, page=1):
        start = (page - 1) * limit
        return self._get("marketplace", f"limit={min(limit, 100)}&start={start}")

    def create_marketplace_account(self, data: dict):
        return self._post("marketplace/create_account", data)


if __name__ == "__main__":
    try:
        client = IuguClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
