#!/usr/bin/env python3
"""RD Station CRM Client — Agente CFO skill."""

import os
import sys

import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseCRMClient, http_request, emit, emit_error, now_iso, make_deal_item, make_list_response


class RDStationClient(BaseCRMClient):
    SKILL_NAME = "rd-station"

    def _validate_env(self):
        if not os.environ.get("RDSTATION_TOKEN"):
            raise RuntimeError("RDSTATION_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["RDSTATION_TOKEN"]
        self.base_url = os.environ.get("RDSTATION_BASE_URL", "https://crm.rdstation.com/api/v1")

    def _get(self, path, params=""):
        url = f"{self.base_url}/{path}?token={self.token}"
        if params:
            url += f"&{params}"
        return http_request("GET", url)

    def _map_status(self, deal):
        if deal.get("win"):
            return "won"
        if deal.get("lost"):
            return "lost"
        return "open"

    def list_deals(self, status="open", limit=50, page=1):
        params = f"limit={limit}&page={page}"
        data = self._get("deals", params)
        items = []
        records = data.get("deals", []) if isinstance(data, dict) else []
        for d in records:
            deal_stage = d.get("deal_stage", {}) or {}
            user = d.get("user", {}) or {}
            deal_status = self._map_status(d)
            if status != "all" and deal_status != status:
                continue
            amount = d.get("amount_montly") or d.get("amount_total") or d.get("amount_unique") or 0
            items.append(make_deal_item(
                id=str(d.get("id", "")),
                title=d.get("name", ""),
                amount_brl=float(amount or 0),
                stage=deal_stage.get("name", ""),
                status=deal_status,
                expected_close_date=d.get("close_at"),
                owner=user.get("name"),
                raw=d,
            ))
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def _put(self, path, body: dict):
        url = f"{self.base_url}/{path}?token={self.token}"
        return http_request("PUT", url, headers={"Content-Type": "application/json"},
                            body=_json.dumps(body).encode())

    def _post_json(self, path, body: dict):
        url = f"{self.base_url}/{path}?token={self.token}"
        return http_request("POST", url, headers={"Content-Type": "application/json"},
                            body=_json.dumps(body).encode())

    def move_deal(self, id: str, to_stage: str) -> dict:
        raw = self._put(f"deals/{id}", {"deal_stage_id": to_stage})
        return {"success": True, "action": "move_deal", "id": id,
                "after": {"stage_id": to_stage}, "raw": raw}

    def update_deal(self, id: str, amount: float | None = None, close_date: str | None = None) -> dict:
        body: dict = {}
        if amount is not None:
            body["amount_total"] = amount
        if close_date:
            body["close_at"] = close_date
        raw = self._put(f"deals/{id}", body)
        return {"success": True, "action": "update_deal", "id": id, "after": body, "raw": raw}

    def create_deal(self, title: str, amount: float | None = None, pipeline: str | None = None) -> dict:
        body: dict = {"name": title}
        if amount is not None:
            body["amount_total"] = amount
        if pipeline:
            body["deal_pipeline_id"] = pipeline
        raw = self._post_json("deals", body)
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_deal", "id": str(new_id), "raw": raw}

    def mark_deal_won(self, id: str) -> dict:
        raw = self._put(f"deals/{id}", {"win": True})
        return {"success": True, "action": "mark_deal_won", "id": id,
                "after": {"status": "won"}, "raw": raw}

    def mark_deal_lost(self, id: str, reason: str = "") -> dict:
        body: dict = {"lost": True}
        if reason:
            body["lost_reason"] = reason
        raw = self._put(f"deals/{id}", body)
        return {"success": True, "action": "mark_deal_lost", "id": id,
                "after": {"status": "lost", "reason": reason}, "raw": raw}

    def _delete(self, path):
        url = f"{self.base_url}/{path}?token={self.token}"
        return http_request("DELETE", url)

    def company_info(self):
        try:
            data = self._get("users")
            users = data if isinstance(data, list) else data.get("users", []) if isinstance(data, dict) else []
            if users:
                return {"name": users[0].get("name", "N/A")}
        except Exception:
            pass
        return {"name": "N/A"}

    def add_deal_note(self, id: str, note: str) -> dict:
        raw = self._post_json(f"deals/{id}/notes", {"text": note})
        return {"success": True, "action": "add_note", "deal_id": id, "raw": raw}

    # ── Contatos ─────────────────────────────────────────────────────────────
    def list_contacts(self, limit=50, page=1, search=None):
        params = f"limit={limit}&page={page}"
        if search:
            params += f"&name={search}"
        return self._get("contacts", params)

    def get_contact(self, id: str):
        return self._get(f"contacts/{id}")

    def create_contact(self, data: dict):
        return self._post_json("contacts", data)

    def update_contact(self, id: str, data: dict):
        return self._put(f"contacts/{id}", data)

    def delete_contact(self, id: str):
        return self._delete(f"contacts/{id}")

    # ── Empresas/Organizations ───────────────────────────────────────────────
    def list_organizations(self, limit=50, page=1, search=None):
        params = f"limit={limit}&page={page}"
        if search:
            params += f"&name={search}"
        return self._get("organizations", params)

    def get_organization(self, id: str):
        return self._get(f"organizations/{id}")

    def create_organization(self, data: dict):
        return self._post_json("organizations", data)

    def update_organization(self, id: str, data: dict):
        return self._put(f"organizations/{id}", data)

    def delete_organization(self, id: str):
        return self._delete(f"organizations/{id}")

    # ── Pipelines/Funis ──────────────────────────────────────────────────────
    def list_pipelines(self):
        return self._get("deal_pipelines")

    # ── Stages/Etapas ────────────────────────────────────────────────────────
    def list_stages(self, pipeline_id=None):
        params = f"deal_pipeline_id={pipeline_id}" if pipeline_id else ""
        return self._get("deal_stages", params)

    # ── Atividades/Tasks ─────────────────────────────────────────────────────
    def list_activities(self, deal_id=None, limit=50, page=1):
        params = f"limit={limit}&page={page}"
        if deal_id:
            params += f"&deal_id={deal_id}"
        return self._get("activities", params)

    def create_activity(self, data: dict):
        return self._post_json("activities", data)

    # ── Campos customizados ──────────────────────────────────────────────────
    def list_custom_fields(self):
        return self._get("deal_custom_fields")

    # ── Usuários ─────────────────────────────────────────────────────────────
    def list_users(self):
        return self._get("users")

    # ── Produtos ─────────────────────────────────────────────────────────────
    def list_products(self, limit=50, page=1):
        return self._get("deal_products", f"limit={limit}&page={page}")

    def get_deal(self, id: str):
        return self._get(f"deals/{id}")

    # ── Origens de lead (sources) ────────────────────────────────────────────
    def list_sources(self):
        return self._get("deal_sources")


if __name__ == "__main__":
    try:
        client = RDStationClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
