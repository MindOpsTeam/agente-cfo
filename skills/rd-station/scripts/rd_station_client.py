#!/usr/bin/env python3
"""RD Station CRM Client — Agente CFO skill."""

import os
import sys

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

    def company_info(self):
        try:
            data = self._get("users")
            users = data if isinstance(data, list) else data.get("users", []) if isinstance(data, dict) else []
            if users:
                return {"name": users[0].get("name", "N/A")}
        except Exception:
            pass
        return {"name": "N/A"}


if __name__ == "__main__":
    try:
        client = RDStationClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
