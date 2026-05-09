#!/usr/bin/env python3
"""Nuvemshop E-commerce Client (OAuth 2.0) — Agente CFO skill.

Auth: OAuth 2.0 Access Token (long-lived) no header Authentication: bearer <token>
Base URL: https://api.nuvemshop.com.br/v1/{store_id}/
Docs: https://tiendanube.github.io/api-documentation/
"""
import json as _json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import (
    BaseEcommerceClient, http_request, emit, emit_error, now_iso,
    make_order_item, make_product_item, make_list_response,
)

SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/nuvemshop.env")
AUTH_URL_BASE = "https://www.nuvemshop.com.br/apps"
TOKEN_URL = "https://www.nuvemshop.com.br/apps/authorize/token"

# Status mapping Nuvemshop → uniforme
_FROM_NS = {
    "open":      "pending",
    "closed":    "delivered",
    "cancelled": "cancelled",
    "pending":   "pending",
}

# Payment status
_PAY_NS = {
    "paid":    "paid",
    "pending": "pending",
    "voided":  "cancelled",
    "refunded": "cancelled",
    "abandoned": "cancelled",
    "authorized": "pending",
    "partially_refunded": "paid",
}


def _save_tokens(access_token: str, store_id: str) -> None:
    lines = []
    skip = {"NS_ACCESS_TOKEN", "NS_STORE_ID"}
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                s = line.strip()
                key = s.split("=", 1)[0] if "=" in s else ""
                if s and not s.startswith("#") and key not in skip:
                    lines.append(s)
    lines += [
        f"NS_ACCESS_TOKEN={access_token}",
        f"NS_STORE_ID={store_id}",
    ]
    with open(SECRETS_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(SECRETS_FILE, 0o600)
    os.environ["NS_ACCESS_TOKEN"] = access_token
    os.environ["NS_STORE_ID"] = store_id


class NuvemshopClient(BaseEcommerceClient):
    SKILL_NAME = "nuvemshop"

    def _validate_env(self) -> None:
        for v in ("NS_ACCESS_TOKEN", "NS_STORE_ID"):
            if not os.environ.get(v):
                raise RuntimeError(f"{v} nao definido. Execute connect.sh.")
        self.store_id = os.environ["NS_STORE_ID"]
        self.token = os.environ["NS_ACCESS_TOKEN"]
        self.base_url = f"https://api.nuvemshop.com.br/v1/{self.store_id}"
        self.headers = {
            "Authentication": f"bearer {self.token}",
            "User-Agent": "AgenteCFO/1.0 (agente-cfo@mindopsteam)",
            "Content-Type": "application/json",
        }

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, params: str = "") -> dict | list:
        url = f"{self.base_url}/{path.lstrip('/')}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self.headers)

    def _put(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("PUT", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("POST", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _to_order_item(self, o: dict) -> dict:
        # Nuvemshop: combine status + payment_status
        pay_status = _PAY_NS.get(o.get("payment_status", ""), "pending")
        order_status = _FROM_NS.get(o.get("status", "open"), "pending")

        if order_status == "cancelled" or pay_status == "cancelled":
            status = "cancelled"
        elif order_status == "delivered":
            status = "delivered"
        elif o.get("shipping_status") == "shipped":
            status = "shipped"
        elif pay_status == "paid":
            status = "paid"
        else:
            status = "pending"

        customer = o.get("customer") or {}
        cname = customer.get("name") or ""

        # Amount: total in pesos/reais
        total = float(o.get("total") or 0.0)

        # Tracking
        shipping_tracking = o.get("shipping_tracking_number")
        created = o.get("created_at", "")
        items_list = o.get("products") or []

        return make_order_item(
            id=str(o.get("id", "")),
            status=status,
            amount_brl=total,
            customer_name=cname,
            created_at=created,
            items_count=len(items_list) if items_list else 1,
            tracking_code=shipping_tracking,
            raw=o,
        )

    def _to_product_item(self, p: dict) -> dict:
        # Nuvemshop: product → variants for price/stock
        variants = p.get("variants") or []
        price = 0.0
        stock = 0
        sku = None
        if variants:
            first = variants[0]
            price = float(first.get("price") or 0.0)
            stock = sum(int(v.get("stock") or 0) for v in variants if v.get("stock") is not None)
            sku = first.get("sku")
        # Name: multilingual dict or string
        name_raw = p.get("name") or {}
        name = name_raw.get("pt", "") or name_raw.get("es", "") or str(name_raw) if isinstance(name_raw, dict) else str(name_raw)
        active = not bool(p.get("archived", False))
        return make_product_item(
            id=str(p.get("id", "")),
            name=name,
            sku=sku,
            price_brl=price,
            stock_qty=stock,
            active=active,
            raw=p,
        )

    # ── BaseEcommerceClient interface ─────────────────────────────────────────

    def list_orders(
        self,
        status: str = "paid",
        limit: int = 50,
        since: str | None = None,
    ) -> dict:
        params = f"per_page={min(limit, 200)}&page=1"
        # Nuvemshop filter by payment_status
        ns_pay = {"paid": "paid", "pending": "pending", "cancelled": "voided"}
        ns_ord = {"shipped": "open", "delivered": "closed", "cancelled": "cancelled"}
        if status == "paid":
            params += "&payment_status=paid"
        elif status in ns_pay:
            params += f"&payment_status={ns_pay[status]}"
        elif status in ns_ord:
            params += f"&status={ns_ord[status]}"
        # status="all" → no filter
        if since:
            params += f"&created_at_min={since}T00:00:00-03:00"
        data = self._get("orders", params)
        raw_items = data if isinstance(data, list) else data.get("orders", [])
        items = [self._to_order_item(o) for o in raw_items]
        return make_list_response(items, total_count=len(items))

    def get_order(self, id: str) -> dict:
        data = self._get(f"orders/{id}")
        if isinstance(data, list) and data:
            data = data[0]
        return self._to_order_item(data if isinstance(data, dict) else {})

    def list_products(
        self,
        limit: int = 50,
        in_stock_only: bool = False,
    ) -> dict:
        params = f"per_page={min(limit, 200)}&page=1"
        data = self._get("products", params)
        raw_items = data if isinstance(data, list) else data.get("products", [])
        items = []
        for p in raw_items:
            pi = self._to_product_item(p)
            if in_stock_only and pi.get("stock_qty", 0) <= 0:
                continue
            items.append(pi)
        return make_list_response(items, total_count=len(items))

    def get_product(self, id: str) -> dict:
        data = self._get(f"products/{id}")
        if isinstance(data, list) and data:
            data = data[0]
        return self._to_product_item(data if isinstance(data, dict) else {})

    def company_info(self) -> dict:
        try:
            data = self._get("store")
            if isinstance(data, list) and data:
                data = data[0]
            name_raw = (data if isinstance(data, dict) else {}).get("name") or {}
            name = name_raw.get("pt", "") or name_raw.get("es", "") or str(name_raw) if isinstance(name_raw, dict) else str(name_raw)
            return {"name": name or "N/A", "segment": "ecommerce", "store_id": self.store_id}
        except Exception:
            return {"name": "N/A", "segment": "ecommerce", "store_id": self.store_id}

    # ── Write operations ──────────────────────────────────────────────────────

    def update_stock(self, product_id: str, new_qty: int) -> dict:
        # Update stock on the first variant
        product = self.get_product(product_id)
        raw_product = product.get("raw") or {}
        variants = raw_product.get("variants") or []
        if not variants:
            return {"success": False, "action": "update_stock", "product_id": product_id,
                    "error": "Produto sem variantes encontrado."}
        variant_id = str(variants[0].get("id", ""))
        raw = self._put(f"products/{product_id}/variants/{variant_id}", {"stock": new_qty})
        return {"success": True, "action": "update_stock", "product_id": product_id,
                "variant_id": variant_id, "after": {"stock_qty": new_qty}, "raw": raw}

    def update_price(self, product_id: str, new_price: float) -> dict:
        product = self.get_product(product_id)
        raw_product = product.get("raw") or {}
        variants = raw_product.get("variants") or []
        if not variants:
            return {"success": False, "action": "update_price", "product_id": product_id,
                    "error": "Produto sem variantes encontrado."}
        variant_id = str(variants[0].get("id", ""))
        raw = self._put(f"products/{product_id}/variants/{variant_id}",
                        {"price": str(new_price)})
        return {"success": True, "action": "update_price", "product_id": product_id,
                "variant_id": variant_id, "after": {"price_brl": new_price}, "raw": raw}

    def mark_order_shipped(self, id: str, tracking_code: str = "") -> dict:
        body: dict = {"shipping_status": "shipped"}
        if tracking_code:
            body["shipping_tracking_number"] = tracking_code
        try:
            raw = self._put(f"orders/{id}", body)
            return {"success": True, "action": "mark_order_shipped", "id": id,
                    "tracking_code": tracking_code, "raw": raw}
        except Exception as e:
            return {"success": False, "action": "mark_order_shipped", "id": id, "error": str(e)}

    def cancel_order(self, id: str, reason: str = "") -> dict:
        try:
            raw = self._post(f"orders/{id}/cancel", {"reason": reason} if reason else {})
            return {"success": True, "action": "cancel_order", "id": id, "raw": raw}
        except Exception as e:
            return {"success": False, "action": "cancel_order", "id": id, "error": str(e)}


if __name__ == "__main__":
    try:
        client = NuvemshopClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
