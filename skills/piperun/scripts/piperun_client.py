#!/usr/bin/env python3
"""PipeRun CRM Client — Agente CFO skill."""

import os
import sys

import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseCRMClient, http_request, emit, emit_error, now_iso, make_deal_item, make_list_response


class PipeRunClient(BaseCRMClient):
    SKILL_NAME = "piperun"
    BASE_URL = "https://api.pipe.run/v1"

    def _validate_env(self):
        if not os.environ.get("PIPERUN_TOKEN"):
            raise RuntimeError("PIPERUN_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["PIPERUN_TOKEN"]

    def _get(self, path, params=""):
        url = f"{self.BASE_URL}/{path}{'?' + params if params else ''}"
        return http_request("GET", url, headers={"token": self.token})

    def _map_status(self, status_id):
        return {1: "open", 2: "won", 3: "lost"}.get(int(status_id), "open")

    def list_deals(self, status="open", limit=50, page=1):
        status_map = {"open": "1", "won": "2", "lost": "3"}
        params = f"show={limit}&page={page}"
        if status in status_map:
            params += f"&status={status_map[status]}"
        data = self._get("deals", params)
        items = []
        records = data.get("data", []) if isinstance(data, dict) else []
        for d in records:
            items.append(make_deal_item(
                id=str(d.get("id", "")),
                title=d.get("name", ""),
                amount_brl=float(d.get("value", 0) or 0),
                stage=d.get("step_name", ""),
                status=self._map_status(d.get("status_id", 1)),
                expected_close_date=d.get("close_date"),
                owner=d.get("owner", {}).get("name") if isinstance(d.get("owner"), dict) else None,
                raw=d,
            ))
        meta = data.get("meta", {}) if isinstance(data, dict) else {}
        total = meta.get("total", len(items))
        total_pages = meta.get("last_page", 1)
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def _put(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("PUT", url, headers={"token": self.token, "Content-Type": "application/json"},
                            body=_json.dumps(body).encode())

    def _post_json(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("POST", url, headers={"token": self.token, "Content-Type": "application/json"},
                            body=_json.dumps(body).encode())

    def move_deal(self, id: str, to_stage: str) -> dict:
        raw = self._put(f"deals/{id}", {"step_id": int(to_stage)})
        return {"success": True, "action": "move_deal", "id": id,
                "after": {"stage_id": to_stage}, "raw": raw}

    def update_deal(self, id: str, amount: float | None = None, close_date: str | None = None) -> dict:
        body: dict = {}
        if amount is not None:
            body["value"] = amount
        if close_date:
            body["close_date"] = close_date
        raw = self._put(f"deals/{id}", body)
        return {"success": True, "action": "update_deal", "id": id, "after": body, "raw": raw}

    def create_deal(self, title: str, amount: float | None = None, pipeline: str | None = None) -> dict:
        body: dict = {"name": title}
        if amount is not None:
            body["value"] = amount
        if pipeline:
            body["pipeline_id"] = int(pipeline)
        raw = self._post_json("deals", body)
        new_id = raw.get("data", {}).get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_deal", "id": str(new_id), "raw": raw}

    def add_deal_note(self, id: str, note: str) -> dict:
        raw = self._post_json(f"deals/{id}/notes", {"text": note})
        return {"success": True, "action": "add_deal_note", "id": id, "raw": raw}

    def mark_deal_won(self, id: str) -> dict:
        raw = self._put(f"deals/{id}", {"status_id": 2})
        return {"success": True, "action": "mark_deal_won", "id": id,
                "after": {"status": "won"}, "raw": raw}

    def mark_deal_lost(self, id: str, reason: str = "") -> dict:
        body: dict = {"status_id": 3}
        if reason:
            body["lost_reason"] = reason
        raw = self._put(f"deals/{id}", body)
        return {"success": True, "action": "mark_deal_lost", "id": id,
                "after": {"status": "lost", "reason": reason}, "raw": raw}

    def company_info(self):
        data = self._get("companies", "limit=1")
        companies = data.get("data", []) if isinstance(data, dict) else []
        if companies:
            return {"name": companies[0].get("name", "N/A")}
        return {"name": "N/A"}


if __name__ == "__main__":
    try:
        client = PipeRunClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
