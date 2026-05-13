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

    # ── DELETE helper ────────────────────────────────────────────────────────

    def _delete(self, path: str) -> dict:
        return http_request("DELETE", self._url(path), headers={
            "Accept": "application/json",
        })

    # ── Deal detalhe ─────────────────────────────────────────────────────────

    def get_deal(self, id: str) -> dict:
        raw = self._get(f"deals/{id}")
        d = raw.get("data") or {}
        stage_id = d.get("stage_id")
        stage_label = self._resolve_stage(stage_id) if stage_id else "unknown"
        return {
            "id": str(d.get("id", "")),
            "title": d.get("title", ""),
            "value": d.get("value"),
            "currency": d.get("currency"),
            "status": d.get("status"),
            "stage": stage_label,
            "expected_close_date": (d.get("expected_close_date") or "")[:10] or None,
            "person_id": d.get("person_id"),
            "org_id": d.get("org_id"),
            "raw": d,
        }

    def delete_deal(self, id: str) -> dict:
        raw = self._delete(f"deals/{id}")
        return {"success": True, "action": "delete_deal", "id": id, "raw": raw}

    # ── Persons (Contacts) ───────────────────────────────────────────────────

    def list_persons(self, limit: int = 50, start: int = 0) -> dict:
        raw = self._get("persons", f"limit={min(limit, 500)}&start={start}")
        items = [{"id": str(p.get("id", "")), "name": p.get("name", ""),
                  "email": (p.get("email") or [{}])[0].get("value", "") if isinstance(p.get("email"), list) else "",
                  "phone": (p.get("phone") or [{}])[0].get("value", "") if isinstance(p.get("phone"), list) else "",
                  "org_id": p.get("org_id")}
                 for p in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    def get_person(self, id: str) -> dict:
        raw = self._get(f"persons/{id}")
        return raw.get("data") or {}

    def create_person(self, name: str, email: str | None = None, phone: str | None = None, org_id: int | None = None) -> dict:
        body: dict = {"name": name}
        if email:
            body["email"] = [{"value": email, "primary": True}]
        if phone:
            body["phone"] = [{"value": phone, "primary": True}]
        if org_id:
            body["org_id"] = org_id
        raw = self._post("persons", body)
        return {"success": True, "action": "create_person", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def update_person(self, id: str, name: str | None = None, email: str | None = None, phone: str | None = None) -> dict:
        body: dict = {}
        if name:
            body["name"] = name
        if email:
            body["email"] = [{"value": email, "primary": True}]
        if phone:
            body["phone"] = [{"value": phone, "primary": True}]
        raw = self._put(f"persons/{id}", body)
        return {"success": True, "action": "update_person", "id": id, "raw": raw}

    def delete_person(self, id: str) -> dict:
        raw = self._delete(f"persons/{id}")
        return {"success": True, "action": "delete_person", "id": id, "raw": raw}

    # ── Organizations ────────────────────────────────────────────────────────

    def list_organizations(self, limit: int = 50, start: int = 0) -> dict:
        raw = self._get("organizations", f"limit={min(limit, 500)}&start={start}")
        items = [{"id": str(o.get("id", "")), "name": o.get("name", ""),
                  "address": o.get("address", "")}
                 for o in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    def get_organization(self, id: str) -> dict:
        raw = self._get(f"organizations/{id}")
        return raw.get("data") or {}

    def create_organization(self, name: str, address: str | None = None) -> dict:
        body: dict = {"name": name}
        if address:
            body["address"] = address
        raw = self._post("organizations", body)
        return {"success": True, "action": "create_org", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def update_organization(self, id: str, name: str | None = None, address: str | None = None) -> dict:
        body: dict = {}
        if name:
            body["name"] = name
        if address:
            body["address"] = address
        raw = self._put(f"organizations/{id}", body)
        return {"success": True, "action": "update_org", "id": id, "raw": raw}

    def delete_organization(self, id: str) -> dict:
        raw = self._delete(f"organizations/{id}")
        return {"success": True, "action": "delete_org", "id": id, "raw": raw}

    # ── Activities ───────────────────────────────────────────────────────────

    def list_activities(self, limit: int = 50, start: int = 0) -> dict:
        raw = self._get("activities", f"limit={min(limit, 500)}&start={start}")
        items = [{"id": str(a.get("id", "")), "type": a.get("type", ""),
                  "subject": a.get("subject", ""), "due_date": a.get("due_date"),
                  "done": a.get("done"), "deal_id": a.get("deal_id"),
                  "person_id": a.get("person_id")}
                 for a in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    def create_activity(self, subject: str, type: str = "task", due_date: str | None = None,
                        deal_id: int | None = None, person_id: int | None = None) -> dict:
        body: dict = {"subject": subject, "type": type}
        if due_date:
            body["due_date"] = due_date
        if deal_id:
            body["deal_id"] = deal_id
        if person_id:
            body["person_id"] = person_id
        raw = self._post("activities", body)
        return {"success": True, "action": "create_activity", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    # ── Products ─────────────────────────────────────────────────────────────

    def list_products(self, limit: int = 50, start: int = 0) -> dict:
        raw = self._get("products", f"limit={min(limit, 500)}&start={start}")
        items = [{"id": str(p.get("id", "")), "name": p.get("name", ""),
                  "code": p.get("code", ""), "unit": p.get("unit", ""),
                  "prices": p.get("prices")}
                 for p in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    def get_product(self, id: str) -> dict:
        raw = self._get(f"products/{id}")
        return raw.get("data") or {}

    def create_product(self, name: str, code: str | None = None, unit: str | None = None,
                       price: float | None = None) -> dict:
        body: dict = {"name": name}
        if code:
            body["code"] = code
        if unit:
            body["unit"] = unit
        if price is not None:
            body["prices"] = [{"price": price, "currency": "BRL"}]
        raw = self._post("products", body)
        return {"success": True, "action": "create_product", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    # ── Pipelines ────────────────────────────────────────────────────────────

    def list_pipelines(self) -> dict:
        raw = self._get("pipelines")
        items = [{"id": str(p.get("id", "")), "name": p.get("name", ""),
                  "active": p.get("active"), "deal_probability": p.get("deal_probability")}
                 for p in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    # ── Stages ───────────────────────────────────────────────────────────────

    def list_stages(self, pipeline_id: int | None = None) -> dict:
        params = ""
        if pipeline_id:
            params = f"pipeline_id={pipeline_id}"
        raw = self._get("stages", params)
        items = [{"id": str(s.get("id", "")), "name": s.get("name", ""),
                  "pipeline_id": s.get("pipeline_id"), "order_nr": s.get("order_nr")}
                 for s in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    # ── Notes ────────────────────────────────────────────────────────────────

    def list_notes(self, deal_id: int | None = None, person_id: int | None = None, limit: int = 50, start: int = 0) -> dict:
        params = f"limit={min(limit, 500)}&start={start}"
        if deal_id:
            params += f"&deal_id={deal_id}"
        if person_id:
            params += f"&person_id={person_id}"
        raw = self._get("notes", params)
        items = [{"id": str(n.get("id", "")), "content": n.get("content", ""),
                  "deal_id": n.get("deal_id"), "person_id": n.get("person_id"),
                  "org_id": n.get("org_id")}
                 for n in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    def create_note(self, content: str, deal_id: int | None = None, person_id: int | None = None,
                    org_id: int | None = None) -> dict:
        body: dict = {"content": content}
        if deal_id:
            body["deal_id"] = deal_id
        if person_id:
            body["person_id"] = person_id
        if org_id:
            body["org_id"] = org_id
        raw = self._post("notes", body)
        return {"success": True, "action": "create_note", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    # ── Users ────────────────────────────────────────────────────────────────

    def list_users(self) -> dict:
        raw = self._get("users")
        items = [{"id": str(u.get("id", "")), "name": u.get("name", ""),
                  "email": u.get("email", ""), "active": u.get("active_flag")}
                 for u in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    # ── Webhooks ─────────────────────────────────────────────────────────────

    def list_webhooks(self) -> dict:
        raw = self._get("webhooks")
        items = [{"id": str(w.get("id", "")), "subscription_url": w.get("subscription_url", ""),
                  "event_action": w.get("event_action"), "event_object": w.get("event_object")}
                 for w in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    def create_webhook(self, subscription_url: str, event_action: str, event_object: str) -> dict:
        body = {"subscription_url": subscription_url, "event_action": event_action, "event_object": event_object}
        raw = self._post("webhooks", body)
        return {"success": True, "action": "create_webhook", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def delete_webhook(self, id: str) -> dict:
        raw = self._delete(f"webhooks/{id}")
        return {"success": True, "action": "delete_webhook", "id": id, "raw": raw}

    # ── Goals ────────────────────────────────────────────────────────────────

    def list_goals(self) -> dict:
        raw = self._get("goals/find")
        items = [{"id": str(g.get("id", "")), "title": g.get("title", ""),
                  "goal_type": g.get("goal_type"), "expected_outcome": g.get("expected_outcome")}
                 for g in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}

    # ── Filters ──────────────────────────────────────────────────────────────

    def list_filters(self, type: str | None = None) -> dict:
        params = ""
        if type:
            params = f"type={type}"
        raw = self._get("filters", params)
        items = [{"id": str(f.get("id", "")), "name": f.get("name", ""),
                  "type": f.get("type"), "active_flag": f.get("active_flag")}
                 for f in (raw.get("data") or [])]
        return {"items": items, "count": len(items)}


if __name__ == "__main__":
    try:
        client = PipedriveClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
