#!/usr/bin/env python3
"""Mercado Livre E-commerce Client (OAuth 2.0) — Agente CFO skill.

Auth: OAuth 2.0 Authorization Code + automatic refresh token.
Base URL: https://api.mercadolibre.com
Docs: https://developers.mercadolivre.com.br/
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

SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/mercado-livre.env")
BASE_URL = "https://api.mercadolibre.com"
TOKEN_URL = f"{BASE_URL}/oauth/token"


def _save_tokens(access_token: str, refresh_token: str, user_id: str, expiry: float) -> None:
    lines: list[str] = []
    skip = {"ML_ACCESS_TOKEN", "ML_REFRESH_TOKEN", "ML_TOKEN_EXPIRY"}
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                s = line.strip()
                key = s.split("=", 1)[0] if "=" in s else ""
                if s and not s.startswith("#") and key not in skip:
                    lines.append(s)
    lines += [
        f"ML_ACCESS_TOKEN={access_token}",
        f"ML_REFRESH_TOKEN={refresh_token}",
        f"ML_USER_ID={user_id}",
        f"ML_TOKEN_EXPIRY={int(expiry)}",
    ]
    lock = SECRETS_FILE + ".lock"
    for _ in range(3):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(0.5)
    try:
        with open(SECRETS_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(SECRETS_FILE, 0o600)
    finally:
        try:
            os.unlink(lock)
        except OSError:
            pass
    os.environ["ML_ACCESS_TOKEN"] = access_token
    os.environ["ML_REFRESH_TOKEN"] = refresh_token
    os.environ["ML_USER_ID"] = user_id
    os.environ["ML_TOKEN_EXPIRY"] = str(int(expiry))


# Status mapping
_FROM_ML = {
    "confirmed": "pending",
    "payment_required": "pending",
    "payment_in_process": "pending",
    "paid": "paid",
    "ready_to_ship": "paid",
    "shipped": "shipped",
    "delivered": "delivered",
    "cancelled": "cancelled",
    "invalid": "cancelled",
}


class MercadoLivreClient(BaseEcommerceClient):
    SKILL_NAME = "mercado-livre"

    def _validate_env(self) -> None:
        for v in ("ML_CLIENT_ID", "ML_CLIENT_SECRET", "ML_ACCESS_TOKEN", "ML_REFRESH_TOKEN"):
            if not os.environ.get(v):
                raise RuntimeError(f"{v} nao definido. Execute connect.sh.")
        self.user_id = os.environ.get("ML_USER_ID", "")
        self._ensure_token()

    def _ensure_token(self) -> None:
        expiry = int(os.environ.get("ML_TOKEN_EXPIRY", "0") or "0")
        if time.time() + 300 > expiry:
            self._refresh()

    def _refresh(self) -> None:
        body = (
            f"grant_type=refresh_token"
            f"&client_id={os.environ['ML_CLIENT_ID']}"
            f"&client_secret={os.environ['ML_CLIENT_SECRET']}"
            f"&refresh_token={os.environ['ML_REFRESH_TOKEN']}"
        ).encode()
        data = http_request("POST", TOKEN_URL, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }, body=body)
        if "access_token" not in data:
            raise RuntimeError(f"Falha no refresh token ML: {data}")
        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", os.environ["ML_REFRESH_TOKEN"])
        user_id = str(data.get("user_id", os.environ.get("ML_USER_ID", "")))
        expires_in = int(data.get("expires_in", 21600))
        _save_tokens(new_access, new_refresh, user_id, time.time() + expires_in)
        self.user_id = user_id

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {os.environ['ML_ACCESS_TOKEN']}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: str = "") -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self._headers())

    def _put(self, path: str, body: dict) -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}"
        return http_request("PUT", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    def _post(self, path: str, body: dict) -> dict:
        self._ensure_token()
        url = f"{BASE_URL}/{path.lstrip('/')}"
        return http_request("POST", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ensure_user_id(self) -> str:
        if not self.user_id:
            data = self._get("users/me")
            self.user_id = str(data.get("id", ""))
            os.environ["ML_USER_ID"] = self.user_id
        return self.user_id

    def _to_order_item(self, o: dict) -> dict:
        raw_status = o.get("status", "")
        status = _FROM_ML.get(raw_status, "pending")
        buyer = o.get("buyer") or {}
        cname = buyer.get("nickname") or buyer.get("first_name", "")
        amount = float((o.get("total_amount") or o.get("paid_amount") or 0.0))
        shipping = o.get("shipping") or {}
        tracking = None
        if isinstance(shipping, dict):
            tracking = shipping.get("tracking_number")
        items_list = o.get("order_items") or []
        return make_order_item(
            id=str(o.get("id", "")),
            status=status,
            amount_brl=amount,
            customer_name=cname,
            created_at=o.get("date_created", ""),
            items_count=len(items_list) if items_list else 1,
            tracking_code=tracking,
            raw=o,
        )

    def _to_product_item(self, p: dict) -> dict:
        price = float(p.get("price") or 0.0)
        stock = 0
        avail = p.get("available_quantity")
        if avail is not None:
            stock = int(avail)
        else:
            attr = p.get("attributes") or []
            for a in attr:
                if a.get("id") == "STOCK_QUANTITY":
                    stock = int(a.get("value_name", 0) or 0)
                    break
        active = (p.get("status", "") == "active")
        return make_product_item(
            id=str(p.get("id", "")),
            name=p.get("title", ""),
            sku=p.get("seller_custom_field"),
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
        uid = self._ensure_user_id()
        params = f"seller={uid}&limit={min(limit, 50)}&sort=date_desc"
        # ML status filter
        ml_status_map = {
            "paid": "paid", "pending": "confirmed",
            "shipped": "shipped", "delivered": "delivered",
            "cancelled": "cancelled",
        }
        if status != "all" and status in ml_status_map:
            params += f"&order.status={ml_status_map[status]}"
        if since:
            params += f"&order.date_created.from={since}T00:00:00.000-03:00"
        data = self._get("orders/search", params)
        results = data.get("results") or []
        items = [self._to_order_item(o) for o in results]
        total = (data.get("paging") or {}).get("total", len(items))
        return make_list_response(items, total_count=total)

    def get_order(self, id: str) -> dict:
        data = self._get(f"orders/{id}")
        return self._to_order_item(data)

    def list_products(
        self,
        limit: int = 50,
        in_stock_only: bool = False,
    ) -> dict:
        uid = self._ensure_user_id()
        params = f"status=active&limit={min(limit, 50)}"
        data = self._get(f"users/{uid}/items/search", params)
        item_ids = data.get("results") or []
        if not item_ids:
            return make_list_response([])
        # Fetch details in batch (ML allows up to 20 per call)
        items = []
        for i in range(0, len(item_ids), 20):
            batch = item_ids[i:i+20]
            ids_param = ",".join(batch)
            detail = self._get(f"items", f"ids={ids_param}")
            for entry in (detail if isinstance(detail, list) else []):
                body = entry.get("body") or {}
                if body:
                    p = self._to_product_item(body)
                    if in_stock_only and p.get("stock_qty", 0) <= 0:
                        continue
                    items.append(p)
        total = (data.get("paging") or {}).get("total", len(items))
        return make_list_response(items, total_count=total)

    def get_product(self, id: str) -> dict:
        data = self._get(f"items/{id}")
        return self._to_product_item(data)

    def company_info(self) -> dict:
        try:
            data = self._get("users/me")
            return {
                "name": data.get("nickname") or data.get("first_name") or "N/A",
                "segment": "ecommerce",
                "user_id": str(data.get("id", "")),
            }
        except Exception:
            return {"name": "N/A", "segment": "ecommerce"}

    # ── Write operations ──────────────────────────────────────────────────────

    def update_stock(self, product_id: str, new_qty: int) -> dict:
        raw = self._put(f"items/{product_id}", {"available_quantity": new_qty})
        return {"success": True, "action": "update_stock", "product_id": product_id,
                "after": {"stock_qty": new_qty}, "raw": raw}

    def update_price(self, product_id: str, new_price: float) -> dict:
        raw = self._put(f"items/{product_id}", {"price": new_price})
        return {"success": True, "action": "update_price", "product_id": product_id,
                "after": {"price_brl": new_price}, "raw": raw}

    def mark_order_shipped(self, id: str, tracking_code: str = "") -> dict:
        # ML: updating shipment status requires shipment_id — best-effort
        order = self._get(f"orders/{id}")
        shipping = order.get("shipping") or {}
        ship_id = shipping.get("id") if isinstance(shipping, dict) else None
        if ship_id:
            body: dict = {"status": "shipped"}
            if tracking_code:
                body["tracking_number"] = tracking_code
            try:
                raw = self._put(f"shipments/{ship_id}", body)
                return {"success": True, "action": "mark_order_shipped", "id": id,
                        "shipment_id": ship_id, "tracking_code": tracking_code, "raw": raw}
            except Exception as e:
                return {"success": False, "action": "mark_order_shipped", "id": id,
                        "error": str(e), "note": "Atualize status manualmente no painel ML."}
        return {"success": False, "action": "mark_order_shipped", "id": id,
                "note": "shipment_id nao encontrado no pedido."}

    def cancel_order(self, id: str, reason: str = "") -> dict:
        body = {"status": "cancelled"}
        if reason:
            body["cancel_detail"] = {"description": reason}
        try:
            raw = self._put(f"orders/{id}", body)
            return {"success": True, "action": "cancel_order", "id": id, "raw": raw}
        except Exception as e:
            return {"success": False, "action": "cancel_order", "id": id, "error": str(e)}


if __name__ == "__main__":
    try:
        client = MercadoLivreClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
