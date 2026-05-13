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

    def _delete(self, path: str) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("DELETE", url, headers=self.headers)

    # ── Produtos (CRUD) ──────────────────────────────────────────────────────

    def create_product(self, name: str, price: float, **kwargs) -> dict:
        body = {"name": {"pt": name}, "variants": [{"price": str(price)}]}
        if kwargs.get("sku"):
            body["variants"][0]["sku"] = kwargs["sku"]
        if kwargs.get("stock"):
            body["variants"][0]["stock"] = kwargs["stock"]
        if kwargs.get("description"):
            body["description"] = {"pt": kwargs["description"]}
        if kwargs.get("category_ids"):
            body["categories"] = kwargs["category_ids"]
        raw = self._post("products", body)
        return {"success": True, "action": "create_product", "raw": raw}

    def update_product(self, product_id: str, **kwargs) -> dict:
        body = {}
        if kwargs.get("name"):
            body["name"] = {"pt": kwargs["name"]}
        if kwargs.get("description"):
            body["description"] = {"pt": kwargs["description"]}
        if kwargs.get("published") is not None:
            body["published"] = kwargs["published"]
        raw = self._put(f"products/{product_id}", body)
        return {"success": True, "action": "update_product", "product_id": product_id, "raw": raw}

    def delete_product(self, product_id: str) -> dict:
        try:
            raw = self._delete(f"products/{product_id}")
            return {"success": True, "action": "delete_product", "product_id": product_id, "raw": raw}
        except Exception as e:
            return {"success": False, "action": "delete_product", "product_id": product_id, "error": str(e)}

    # ── Variantes ─────────────────────────────────────────────────────────────

    def list_variants(self, product_id: str) -> dict:
        data = self._get(f"products/{product_id}/variants")
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    # ── Categorias ────────────────────────────────────────────────────────────

    def list_categories(self, limit: int = 50) -> dict:
        params = f"per_page={min(limit, 200)}&page=1"
        data = self._get("categories", params)
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    def get_category(self, category_id: str) -> dict:
        data = self._get(f"categories/{category_id}")
        if isinstance(data, list) and data:
            data = data[0]
        return data if isinstance(data, dict) else {}

    def create_category(self, name: str, **kwargs) -> dict:
        body: dict = {"name": {"pt": name}}
        if kwargs.get("parent_id"):
            body["parent"] = kwargs["parent_id"]
        raw = self._post("categories", body)
        return {"success": True, "action": "create_category", "raw": raw}

    # ── Clientes ──────────────────────────────────────────────────────────────

    def list_customers(self, limit: int = 50, since: str | None = None, q: str | None = None) -> dict:
        params = f"per_page={min(limit, 200)}&page=1"
        if since:
            params += f"&created_at_min={since}T00:00:00-03:00"
        if q:
            params += f"&q={q}"
        data = self._get("customers", params)
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    def get_customer(self, customer_id: str) -> dict:
        data = self._get(f"customers/{customer_id}")
        if isinstance(data, list) and data:
            data = data[0]
        return data if isinstance(data, dict) else {}

    def create_customer(self, name: str, email: str, **kwargs) -> dict:
        body: dict = {"name": name, "email": email}
        if kwargs.get("phone"):
            body["phone"] = kwargs["phone"]
        if kwargs.get("identification"):
            body["identification"] = kwargs["identification"]
        raw = self._post("customers", body)
        return {"success": True, "action": "create_customer", "raw": raw}

    def update_customer(self, customer_id: str, **kwargs) -> dict:
        body = {}
        for field in ("name", "email", "phone", "identification", "note"):
            if kwargs.get(field):
                body[field] = kwargs[field]
        raw = self._put(f"customers/{customer_id}", body)
        return {"success": True, "action": "update_customer", "customer_id": customer_id, "raw": raw}

    # ── Pedidos (extras) ──────────────────────────────────────────────────────

    def update_order(self, order_id: str, **kwargs) -> dict:
        body = {}
        if kwargs.get("owner"):
            body["owner"] = kwargs["owner"]
        if kwargs.get("note"):
            body["note"] = kwargs["note"]
        if kwargs.get("shipping_status"):
            body["shipping_status"] = kwargs["shipping_status"]
        raw = self._put(f"orders/{order_id}", body)
        return {"success": True, "action": "update_order", "order_id": order_id, "raw": raw}

    # ── Cupons ────────────────────────────────────────────────────────────────

    def list_coupons(self, limit: int = 50) -> dict:
        params = f"per_page={min(limit, 200)}&page=1"
        data = self._get("coupons", params)
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    def get_coupon(self, coupon_id: str) -> dict:
        data = self._get(f"coupons/{coupon_id}")
        if isinstance(data, list) and data:
            data = data[0]
        return data if isinstance(data, dict) else {}

    def create_coupon(self, code: str, value: float, coupon_type: str = "percentage", **kwargs) -> dict:
        body: dict = {"code": code, "value": str(value), "type": coupon_type}
        if kwargs.get("min_price"):
            body["min_price"] = str(kwargs["min_price"])
        if kwargs.get("max_uses"):
            body["max_uses"] = kwargs["max_uses"]
        if kwargs.get("start_date"):
            body["start_date"] = kwargs["start_date"]
        if kwargs.get("end_date"):
            body["end_date"] = kwargs["end_date"]
        if kwargs.get("categories"):
            body["categories"] = kwargs["categories"]
        raw = self._post("coupons", body)
        return {"success": True, "action": "create_coupon", "raw": raw}

    def delete_coupon(self, coupon_id: str) -> dict:
        try:
            raw = self._delete(f"coupons/{coupon_id}")
            return {"success": True, "action": "delete_coupon", "coupon_id": coupon_id, "raw": raw}
        except Exception as e:
            return {"success": False, "action": "delete_coupon", "coupon_id": coupon_id, "error": str(e)}

    # ── Páginas ───────────────────────────────────────────────────────────────

    def list_pages(self, limit: int = 50) -> dict:
        params = f"per_page={min(limit, 200)}&page=1"
        data = self._get("pages", params)
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    def get_page(self, page_id: str) -> dict:
        data = self._get(f"pages/{page_id}")
        if isinstance(data, list) and data:
            data = data[0]
        return data if isinstance(data, dict) else {}

    # ── Transacoes de Pedido ──────────────────────────────────────────────

    def list_order_transactions(self, order_id: str) -> dict:
        data = self._get(f"orders/{order_id}/transactions")
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    # ── Abandonos de carrinho ─────────────────────────────────────────────

    def list_abandoned_checkouts(self, limit: int = 50) -> dict:
        params = f"per_page={min(limit, 200)}&page=1"
        data = self._get("checkouts", params)
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    # ── Imagens de produto ────────────────────────────────────────────────

    def list_product_images(self, product_id: str) -> dict:
        data = self._get(f"products/{product_id}/images")
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    # ── Webhooks ──────────────────────────────────────────────────────────────

    def list_webhooks(self) -> dict:
        data = self._get("webhooks")
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    def create_webhook(self, url: str, event: str) -> dict:
        body = {"url": url, "event": event}
        raw = self._post("webhooks", body)
        return {"success": True, "action": "create_webhook", "raw": raw}

    def delete_webhook(self, webhook_id: str) -> dict:
        try:
            raw = self._delete(f"webhooks/{webhook_id}")
            return {"success": True, "action": "delete_webhook", "webhook_id": webhook_id, "raw": raw}
        except Exception as e:
            return {"success": False, "action": "delete_webhook", "webhook_id": webhook_id, "error": str(e)}

    # ── Metafields ────────────────────────────────────────────────────────────

    def list_metafields(self, resource: str = "store", resource_id: str | None = None) -> dict:
        if resource_id:
            path = f"{resource}/{resource_id}/metafields"
        else:
            path = f"{resource}/metafields"
        data = self._get(path)
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))

    # ── Frete / Shipping Carriers ─────────────────────────────────────────────

    def list_shipping_carriers(self) -> dict:
        data = self._get("shipping_carriers")
        items = data if isinstance(data, list) else []
        return make_list_response(items, total_count=len(items))


if __name__ == "__main__":
    try:
        client = NuvemshopClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
