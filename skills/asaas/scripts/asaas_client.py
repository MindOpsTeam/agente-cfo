#!/usr/bin/env python3
"""Asaas Cobrança Client — Agente CFO skill.

Auth: header access_token: <token>
Base URL: https://www.asaas.com/api/v3 (prod) | https://sandbox.asaas.com/api/v3 (sandbox)
Docs: https://docs.asaas.com/
"""
import json as _json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import (
    BaseCobrancaClient, http_request, emit, emit_error, now_iso,
    make_invoice_item, make_list_response,
)

SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/asaas.env")

# ── Status mapping ────────────────────────────────────────────────────────────
_TO_ASAAS = {
    "open":      "PENDING",
    "overdue":   "OVERDUE",
    "paid":      "RECEIVED",
    "cancelled": "CANCELLED",
}
_FROM_ASAAS = {
    "PENDING":          "open",
    "OVERDUE":          "overdue",
    "RECEIVED":         "paid",
    "RECEIVED_IN_CASH": "paid",
    "CONFIRMED":        "paid",
    "REFUNDED":         "cancelled",
    "REFUND_REQUESTED": "cancelled",
    "CANCELLED":        "cancelled",
    "CHARGEBACK_REQUESTED": "cancelled",
    "CHARGEBACK_DISPUTE":   "cancelled",
    "AWAITING_CHARGEBACK_REVERSAL": "cancelled",
    "DUNNING_REQUESTED": "overdue",
    "DUNNING_RECEIVED":  "paid",
    "AWAITING_RISK_ANALYSIS": "open",
}


class AsaasClient(BaseCobrancaClient):
    SKILL_NAME = "asaas"

    def _validate_env(self) -> None:
        if not os.environ.get("ASAAS_API_TOKEN"):
            raise RuntimeError("ASAAS_API_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["ASAAS_API_TOKEN"]
        env = os.environ.get("ASAAS_ENV", "prod").lower()
        if env == "sandbox":
            self.base_url = "https://sandbox.asaas.com/api/v3"
        else:
            self.base_url = "https://www.asaas.com/api/v3"
        self.headers = {
            "access_token": self.token,
            "Content-Type": "application/json",
        }

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: str = "") -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self.headers)

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("POST", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def _delete(self, path: str) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("DELETE", url, headers=self.headers)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _payment_url(self, p: dict) -> str | None:
        return (
            p.get("invoiceUrl")
            or p.get("bankSlipUrl")
            or p.get("pixQrCodeUrl")
            or p.get("transactionReceiptUrl")
        )

    def _to_invoice_item(self, p: dict) -> dict:
        raw_status = p.get("status", "PENDING")
        status = _FROM_ASAAS.get(raw_status, "open")
        cid = p.get("customer", "")
        # Asaas may embed customerObject in list responses
        cobj = p.get("customerObject") or {}
        cname = cobj.get("name", "")
        if not cname and cid:
            try:
                c = self.get_customer(cid)
                cname = c.get("name", "")
            except Exception:
                pass
        return make_invoice_item(
            id=str(p.get("id", "")),
            customer_id=cid,
            customer_name=cname,
            due_date=(p.get("dueDate") or "")[:10],
            amount_brl=float(p.get("value", 0.0)),
            status=status,
            payment_url=self._payment_url(p),
            description=p.get("description"),
            raw=p,
        )

    # ── BaseCobrancaClient interface ──────────────────────────────────────────

    def list_invoices(
        self,
        status: str = "open",
        customer_id: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict:
        offset = (page - 1) * limit
        params = f"limit={min(limit, 100)}&offset={offset}"
        if status != "all" and status in _TO_ASAAS:
            params += f"&status={_TO_ASAAS[status]}"
        if customer_id:
            params += f"&customer={customer_id}"
        data = self._get("payments", params)
        items = [self._to_invoice_item(p) for p in (data.get("data") or [])]
        total = data.get("totalCount", len(items))
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def get_invoice(self, id: str) -> dict:
        data = self._get(f"payments/{id}")
        return self._to_invoice_item(data)

    def get_customer(self, id: str) -> dict:
        data = self._get(f"customers/{id}")
        return {
            "id": str(data.get("id", id)),
            "name": data.get("name", ""),
            "phone": data.get("mobilePhone") or data.get("phone"),
            "email": data.get("email"),
            "cpf_cnpj": data.get("cpfCnpj"),
            "raw": data,
        }

    def get_payment_methods(self) -> dict:
        return {"methods": ["pix", "boleto", "credit_card"]}

    def company_info(self) -> dict:
        try:
            data = self._get("myAccount")
            name = data.get("tradingName") or data.get("name") or "N/A"
            return {"name": str(name), "segment": "cobranca", "raw": data}
        except Exception:
            return {"name": "N/A", "segment": "cobranca"}

    # ── Write operations ──────────────────────────────────────────────────────

    def send_payment_link(
        self,
        invoice_id: str,
        channel: str = "whatsapp",
        custom_message: str | None = None,
    ) -> dict:
        """Tenta notificação nativa do Asaas; fallback retorna payment_url."""
        payment_url = None
        try:
            inv = self.get_invoice(invoice_id)
            payment_url = inv.get("payment_url")
        except Exception:
            pass

        # Asaas tem POST /payments/{id}/sendInvoiceByEmail — para WhatsApp não há endpoint nativo
        # Tenta via notificações
        try:
            self._post(f"payments/{invoice_id}/sendInvoiceByEmail", {})
        except Exception:
            pass

        return {
            "success": True,
            "action": "send_payment_link",
            "invoice_id": invoice_id,
            "payment_url": payment_url,
            "channel": channel,
            "note": "Link disponível em payment_url. Canal WhatsApp: envie via wacli ao telefone do cliente.",
        }

    def mark_invoice_paid_manually(self, id: str) -> dict:
        today = date.today().isoformat()
        raw = self._post(f"payments/{id}/receiveInCash", {
            "paymentDate": today,
            "value": 0,  # 0 = valor integral
            "notifyCustomer": False,
        })
        return {
            "success": True, "action": "mark_invoice_paid_manually", "id": id,
            "before": {"status": "open/overdue"},
            "after": {"status": "paid", "paid_at": today},
            "raw": raw,
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
            "customer": customer_id,
            "billingType": "UNDEFINED",
            "value": amount,
            "dueDate": due_date,
            "description": description or "Cobrança gerada pelo Agente CFO",
        }
        raw = self._post("payments", body)
        new_id = str(raw.get("id", ""))
        return {"success": True, "action": "create_invoice", "id": new_id, "raw": raw}

    def cancel_invoice(self, id: str) -> dict:
        raw = self._delete(f"payments/{id}")
        return {"success": True, "action": "cancel_invoice", "id": id, "raw": raw}

    def send_reminder(self, customer_id: str, message: str) -> dict:
        return {
            "success": False,
            "note": "Asaas nao tem endpoint de mensagem livre por cliente. "
                    "Use send_payment_link --invoice_id <id> para enviar link de pagamento.",
            "customer_id": customer_id,
        }

    def _put(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("PUT", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    # ── Clientes ─────────────────────────────────────────────────────────────
    def list_customers(self, limit=50, page=1, search=None):
        offset = (page - 1) * limit
        params = f"limit={min(limit, 100)}&offset={offset}"
        if search:
            params += f"&name={search}"
        return self._get("customers", params)

    def create_customer(self, data: dict):
        return self._post("customers", data)

    def update_customer(self, id: str, data: dict):
        return self._put(f"customers/{id}", data)

    def delete_customer(self, id: str):
        return self._delete(f"customers/{id}")

    # ── Assinaturas ──────────────────────────────────────────────────────────
    def list_subscriptions(self, limit=50, page=1, customer_id=None):
        offset = (page - 1) * limit
        params = f"limit={min(limit, 100)}&offset={offset}"
        if customer_id:
            params += f"&customer={customer_id}"
        return self._get("subscriptions", params)

    def get_subscription(self, id: str):
        return self._get(f"subscriptions/{id}")

    def create_subscription(self, data: dict):
        return self._post("subscriptions", data)

    def update_subscription(self, id: str, data: dict):
        return self._put(f"subscriptions/{id}", data)

    def delete_subscription(self, id: str):
        return self._delete(f"subscriptions/{id}")

    # ── Notificações ─────────────────────────────────────────────────────────
    def list_notifications(self, customer_id: str):
        return self._get(f"customers/{customer_id}/notifications")

    def update_notification(self, notification_id: str, data: dict):
        return self._put(f"notifications/{notification_id}", data)

    # ── Split de pagamento ───────────────────────────────────────────────────
    def list_payment_splits(self, payment_id: str):
        return self._get(f"payments/{payment_id}/splits")

    # ── Antecipação ──────────────────────────────────────────────────────────
    def request_anticipation(self, data: dict):
        return self._post("anticipations", data)

    def list_anticipations(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("anticipations", f"limit={min(limit, 100)}&offset={offset}")

    # ── Transferências ───────────────────────────────────────────────────────
    def list_transfers(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("transfers", f"limit={min(limit, 100)}&offset={offset}")

    def create_transfer(self, data: dict):
        return self._post("transfers", data)

    # ── Extrato ──────────────────────────────────────────────────────────────
    def get_financial_statement(self, from_date=None, to_date=None):
        params = ""
        if from_date:
            params += f"startDate={from_date}"
        if to_date:
            params += f"&finishDate={to_date}" if params else f"finishDate={to_date}"
        return self._get("financialTransactions", params)

    # ── Webhooks ─────────────────────────────────────────────────────────────
    def list_webhooks(self):
        return self._get("webhook")

    def create_webhook(self, data: dict):
        return self._post("webhook", data)

    # ── Subcontas ────────────────────────────────────────────────────────────
    def list_subaccounts(self, limit=50, page=1):
        offset = (page - 1) * limit
        return self._get("accounts", f"limit={min(limit, 100)}&offset={offset}")

    def create_subaccount(self, data: dict):
        return self._post("accounts", data)

    # ── PIX ──────────────────────────────────────────────────────────────────
    def create_pix_key(self, data: dict):
        return self._post("pix/addressKeys", data)

    def list_pix_keys(self):
        return self._get("pix/addressKeys")

    def get_pix_qrcode(self, payment_id: str):
        return self._get(f"payments/{payment_id}/pixQrCode")


if __name__ == "__main__":
    try:
        client = AsaasClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
