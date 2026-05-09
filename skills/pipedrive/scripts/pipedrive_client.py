#!/usr/bin/env python3
"""Pipedrive CRM Client — Agente CFO skill.

Auth: API token (header ?api_token=<token> ou Authorization: Bearer).
Base URL: https://<companydomain>.pipedrive.com/api/v1
"""

import json as _json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import (
    BaseCRMClient, http_request, emit, emit_error, now_iso,
    make_deal_item, make_list_response,
)

STAGES_CACHE = os.path.expanduser("~/.openclaw/secrets/pipedrive_stages.json")


class PipedriveClient(BaseCRMClient):
    SKILL_NAME = "pipedrive"

    def _validate_env(self):
        if not os.environ.get("PIPEDRIVE_API_TOKEN"):
            raise RuntimeError("PIPEDRIVE_API_TOKEN nao definido. Execute connect.sh.")
        domain = os.environ.get("PIPEDRIVE_COMPANY_DOMAIN", "")
        if not domain:
            raise RuntimeError("PIPEDRIVE_COMPANY_DOMAIN nao definido. Execute connect.sh.")
        self.token = os.environ["PIPEDRIVE_API_TOKEN"]
        self.base_url = f"https://{domain}.pipedrive.com/api/v1"
        self._stages: dict[str, str] = self._load_stages()

    # ── Stage cache ───────────────────────────────────────────────────────────

    def _load_stages(self) -> dict:
        if os.path.exists(STAGES_CACHE):
            try:
                with open(STAGES_CACHE) as f:
                    return _json.load(f)
            except Exception:
                pass
        return {}

    def _save_stages(self, stages: dict) -> None:
        try:
            os.makedirs(os.path.dirname(STAGES_CACHE), exist_ok=True)
            with open(STAGES_CACHE, "w") as f:
                _json.dump(stages, f, indent=2)
        except Exception:
            pass

    def fetch_stages(self) -> dict:
        """Fetch all pipeline stages from Pipedrive and cache them."""
        data = self._get("stages")
        stages: dict[str, str] = {}
        for s in (data.get("data") or []):
            stage_id = str(s.get("id", ""))
            stage_name = s.get("name", stage_id)
            stages[stage_id] = stage_name
        self._stages = stages
        self._save_stages(stages)
        return stages

    def _resolve_stage(self, stage_id) -> str:
        sid = str(stage_id)
        if sid in self._stages:
            return self._stages[sid]
        # lazy-load once
        if not self._stages:
            self.fetch_stages()
        return self._stages.get(sid, sid)

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _url(self, path: str, extra_params: str = "") -> str:
        sep = "&" if "?" in path else "?"
        base = f"{self.base_url}/{path.lstrip('/')}{sep}api_token={self.token}"
        if extra_params:
            base += "&" + extra_params
        return base

    def _get(self, path: str, extra_params: str = "") -> dict:
        return http_request("GET", self._url(path, extra_params), headers={
            "Accept": "application/json",
        })

    def _post(self, path: str, body: dict) -> dict:
        return http_request("POST", self._url(path), headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        }, body=_json.dumps(body).encode())

    def _put(self, path: str, body: dict) -> dict:
        return http_request("PUT", self._url(path), headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        }, body=_json.dumps(body).encode())

    # ── Pipedrive status mapping ──────────────────────────────────────────────

    @staticmethod
    def _pd_status(status: str) -> str:
        """Translate our status to Pipedrive's status param."""
        mapping = {"open": "open", "won": "won", "lost": "lost", "all": "all_not_deleted"}
        return mapping.get(status, "open")

    # ── BaseCRMClient interface ───────────────────────────────────────────────

    def list_deals(self, status: str = "open", limit: int = 50, page: int = 1) -> dict:
        start = (page - 1) * limit
        pd_status = self._pd_status(status)
        data = self._get(
            "deals",
            f"status={pd_status}&limit={min(limit, 500)}&start={start}"
            "&fields=id,title,value,currency,stage_id,status,expected_close_date,user_id"
        )
        items = []
        for d in (data.get("data") or []):
            deal_status_raw = d.get("status", "open")
            if deal_status_raw == "open":
                deal_status = "open"
            elif deal_status_raw == "won":
                deal_status = "won"
            elif deal_status_raw == "lost":
                deal_status = "lost"
            else:
                deal_status = "open"

            if status != "all" and deal_status != status:
                continue

            stage_id = d.get("stage_id")
            stage_label = self._resolve_stage(stage_id) if stage_id else "unknown"

            close_date = (d.get("expected_close_date") or "")[:10] or None
            amount = d.get("value")
            owner_id = (d.get("user_id") or {}).get("id") if isinstance(d.get("user_id"), dict) else d.get("user_id")

            items.append(make_deal_item(
                id=str(d.get("id", "")),
                title=d.get("title", ""),
                amount_brl=float(amount) if amount is not None else None,
                stage=stage_label,
                status=deal_status,
                expected_close_date=close_date,
                owner=str(owner_id) if owner_id else None,
                raw=d,
            ))

        pagination = data.get("additional_data", {}).get("pagination", {}) if isinstance(data, dict) else {}
        total = pagination.get("total_count") or len(items)
        total_pages = max(1, -(-total // limit))  # ceil division
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def company_info(self) -> dict:
        try:
            data = self._get("users/me")
            user = data.get("data") or {}
            company = user.get("company_name") or user.get("name", "N/A")
            return {"name": company, "segment": "CRM"}
        except Exception:
            return {"name": "N/A"}

    # ── Write operations ──────────────────────────────────────────────────────

    def move_deal(self, id: str, to_stage: str) -> dict:
        """Move deal to stage. to_stage can be stage ID (numeric) or name."""
        # If to_stage is not numeric, try to resolve by name
        stage_id = to_stage
        if not to_stage.isdigit():
            if not self._stages:
                self.fetch_stages()
            for sid, sname in self._stages.items():
                if sname.lower() == to_stage.lower():
                    stage_id = sid
                    break
        raw = self._put(f"deals/{id}", {"stage_id": int(stage_id)})
        return {
            "success": True, "action": "move_deal", "id": id,
            "after": {"stage_id": stage_id, "stage": self._resolve_stage(stage_id)},
            "raw": raw,
        }

    def update_deal(self, id: str, amount: float | None = None, close_date: str | None = None) -> dict:
        body: dict = {}
        if amount is not None:
            body["value"] = amount
        if close_date:
            body["expected_close_date"] = close_date
        raw = self._put(f"deals/{id}", body)
        return {"success": True, "action": "update_deal", "id": id, "after": body, "raw": raw}

    def create_deal(self, title: str, amount: float | None = None, pipeline: str | None = None) -> dict:
        body: dict = {"title": title}
        if amount is not None:
            body["value"] = amount
        if pipeline:
            # accept pipeline_id (numeric) or name
            body["pipeline_id"] = int(pipeline) if str(pipeline).isdigit() else pipeline
        raw = self._post("deals", body)
        deal_data = raw.get("data") or {}
        new_id = str(deal_data.get("id", ""))
        return {"success": True, "action": "create_deal", "id": new_id, "raw": raw}

    def add_deal_note(self, id: str, note: str) -> dict:
        raw = self._post("notes", {
            "content": note,
            "deal_id": int(id),
            "pinned_to_deal_flag": "0",
        })
        note_data = raw.get("data") or {}
        return {"success": True, "action": "add_deal_note", "deal_id": id,
                "note_id": str(note_data.get("id", "")), "raw": raw}

    def mark_deal_won(self, id: str) -> dict:
        raw = self._put(f"deals/{id}", {"status": "won"})
        return {"success": True, "action": "mark_deal_won", "id": id,
                "after": {"status": "won"}, "raw": raw}

    def mark_deal_lost(self, id: str, reason: str = "") -> dict:
        body: dict = {"status": "lost"}
        if reason:
            body["lost_reason"] = reason
        raw = self._put(f"deals/{id}", body)
        return {"success": True, "action": "mark_deal_lost", "id": id,
                "after": {"status": "lost", "reason": reason}, "raw": raw}


if __name__ == "__main__":
    try:
        client = PipedriveClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
