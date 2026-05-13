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

    # ── Leads (Inbox) ───────────────────────────────────────────────────────
    def list_leads(self, limit=50, start=0):
        raw = self._get("leads", f"limit={min(limit, 500)}&start={start}")
        items = raw.get("data", []) or []
        return {"items": items, "count": len(items)}

    def get_lead(self, id: str):
        raw = self._get(f"leads/{id}")
        return raw.get("data") or {}

    def create_lead(self, title: str, person_id=None, organization_id=None, value=None):
        body = {"title": title}
        if person_id: body["person_id"] = int(person_id)
        if organization_id: body["organization_id"] = int(organization_id)
        if value: body["value"] = {"amount": value, "currency": "BRL"}
        raw = self._post("leads", body)
        return {"success": True, "action": "create_lead", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def update_lead(self, id: str, title=None, label_ids=None):
        body = {}
        if title: body["title"] = title
        if label_ids: body["label_ids"] = label_ids
        raw = http_request("PATCH", self._url(f"leads/{id}"), headers={"Content-Type": "application/json", "Accept": "application/json"}, body=_json.dumps(body).encode())
        return {"success": True, "action": "update_lead", "id": id, "raw": raw}

    def delete_lead(self, id: str):
        raw = self._delete(f"leads/{id}")
        return {"success": True, "action": "delete_lead", "id": id, "raw": raw}

    # ── Lead Labels ─────────────────────────────────────────────────────────
    def list_lead_labels(self):
        raw = self._get("leadLabels")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def create_lead_label(self, name: str, color: str = "blue"):
        raw = self._post("leadLabels", {"name": name, "color": color})
        return {"success": True, "action": "create_lead_label", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def update_lead_label(self, id: str, name: str = None, color: str = None):
        body = {}
        if name: body["name"] = name
        if color: body["color"] = color
        raw = self._put(f"leadLabels/{id}", body)
        return {"success": True, "action": "update_lead_label", "id": id, "raw": raw}

    def delete_lead_label(self, id: str):
        raw = self._delete(f"leadLabels/{id}")
        return {"success": True, "action": "delete_lead_label", "id": id, "raw": raw}

    # ── Persons (extend) ────────────────────────────────────────────────────
    def merge_persons(self, id: str, merge_with_id: str):
        raw = self._put(f"persons/{id}/merge", {"merge_with_id": int(merge_with_id)})
        return {"success": True, "action": "merge_persons", "id": id, "raw": raw}

    def list_person_deals(self, id: str, limit=50, start=0):
        raw = self._get(f"persons/{id}/deals", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_person_activities(self, id: str, limit=50, start=0):
        raw = self._get(f"persons/{id}/activities", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_person_files(self, id: str, limit=50, start=0):
        raw = self._get(f"persons/{id}/files", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_person_updates(self, id: str, limit=50, start=0):
        raw = self._get(f"persons/{id}/flow", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_person_followers(self, id: str):
        raw = self._get(f"persons/{id}/followers")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def add_person_follower(self, id: str, user_id: int):
        raw = self._post(f"persons/{id}/followers", {"user_id": user_id})
        return {"success": True, "action": "add_person_follower", "raw": raw}

    def delete_person_follower(self, id: str, follower_id: int):
        raw = self._delete(f"persons/{id}/followers/{follower_id}")
        return {"success": True, "action": "delete_person_follower", "raw": raw}

    # ── Organizations (extend) ──────────────────────────────────────────────
    def merge_organizations(self, id: str, merge_with_id: str):
        raw = self._put(f"organizations/{id}/merge", {"merge_with_id": int(merge_with_id)})
        return {"success": True, "action": "merge_orgs", "id": id, "raw": raw}

    def list_org_deals(self, id: str, limit=50, start=0):
        raw = self._get(f"organizations/{id}/deals", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_org_persons(self, id: str, limit=50, start=0):
        raw = self._get(f"organizations/{id}/persons", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_org_activities(self, id: str, limit=50, start=0):
        raw = self._get(f"organizations/{id}/activities", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_org_files(self, id: str, limit=50, start=0):
        raw = self._get(f"organizations/{id}/files", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_org_updates(self, id: str, limit=50, start=0):
        raw = self._get(f"organizations/{id}/flow", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_org_followers(self, id: str):
        raw = self._get(f"organizations/{id}/followers")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def add_org_follower(self, id: str, user_id: int):
        raw = self._post(f"organizations/{id}/followers", {"user_id": user_id})
        return {"success": True, "action": "add_org_follower", "raw": raw}

    # ── Deals (extend) ──────────────────────────────────────────────────────
    def merge_deals(self, id: str, merge_with_id: str):
        raw = self._put(f"deals/{id}/merge", {"merge_with_id": int(merge_with_id)})
        return {"success": True, "action": "merge_deals", "id": id, "raw": raw}

    def list_deal_followers(self, id: str):
        raw = self._get(f"deals/{id}/followers")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def add_deal_follower(self, id: str, user_id: int):
        raw = self._post(f"deals/{id}/followers", {"user_id": user_id})
        return {"success": True, "action": "add_deal_follower", "raw": raw}

    def list_deal_participants(self, id: str, limit=50, start=0):
        raw = self._get(f"deals/{id}/participants", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def add_deal_participant(self, id: str, person_id: int):
        raw = self._post(f"deals/{id}/participants", {"person_id": person_id})
        return {"success": True, "action": "add_deal_participant", "raw": raw}

    def delete_deal_participant(self, deal_id: str, participant_id: int):
        raw = self._delete(f"deals/{deal_id}/participants/{participant_id}")
        return {"success": True, "action": "delete_deal_participant", "raw": raw}

    def list_deal_updates(self, id: str, limit=50, start=0):
        raw = self._get(f"deals/{id}/flow", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_deal_files(self, id: str, limit=50, start=0):
        raw = self._get(f"deals/{id}/files", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_deal_activities(self, id: str, limit=50, start=0):
        raw = self._get(f"deals/{id}/activities", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_deal_products(self, id: str, limit=50, start=0):
        raw = self._get(f"deals/{id}/products", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def add_deal_product(self, id: str, product_id: int, item_price: float, quantity: int = 1):
        raw = self._post(f"deals/{id}/products", {"product_id": product_id, "item_price": item_price, "quantity": quantity})
        return {"success": True, "action": "add_deal_product", "raw": raw}

    def update_deal_product(self, deal_id: str, product_attachment_id: int, item_price: float = None, quantity: int = None):
        body = {}
        if item_price is not None: body["item_price"] = item_price
        if quantity is not None: body["quantity"] = quantity
        raw = self._put(f"deals/{deal_id}/products/{product_attachment_id}", body)
        return {"success": True, "action": "update_deal_product", "raw": raw}

    def delete_deal_product(self, deal_id: str, product_attachment_id: int):
        raw = self._delete(f"deals/{deal_id}/products/{product_attachment_id}")
        return {"success": True, "action": "delete_deal_product", "raw": raw}

    def list_deal_mail_messages(self, id: str, limit=50, start=0):
        raw = self._get(f"deals/{id}/mailMessages", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Activities (extend) ─────────────────────────────────────────────────
    def get_activity(self, id: str):
        raw = self._get(f"activities/{id}")
        return raw.get("data") or {}

    def update_activity(self, id: str, subject=None, done=None, due_date=None, type=None):
        body = {}
        if subject: body["subject"] = subject
        if done is not None: body["done"] = 1 if done else 0
        if due_date: body["due_date"] = due_date
        if type: body["type"] = type
        raw = self._put(f"activities/{id}", body)
        return {"success": True, "action": "update_activity", "id": id, "raw": raw}

    def delete_activity(self, id: str):
        raw = self._delete(f"activities/{id}")
        return {"success": True, "action": "delete_activity", "id": id, "raw": raw}

    def list_activity_types(self):
        raw = self._get("activityTypes")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Files ───────────────────────────────────────────────────────────────
    def list_files(self, limit=50, start=0):
        raw = self._get("files", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def get_file(self, id: str):
        raw = self._get(f"files/{id}")
        return raw.get("data") or {}

    def delete_file(self, id: str):
        raw = self._delete(f"files/{id}")
        return {"success": True, "action": "delete_file", "id": id, "raw": raw}

    # ── Filters (extend) ────────────────────────────────────────────────────
    def create_filter(self, name: str, type: str, conditions: dict):
        raw = self._post("filters", {"name": name, "type": type, "conditions": conditions})
        return {"success": True, "action": "create_filter", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def get_filter(self, id: str):
        raw = self._get(f"filters/{id}")
        return raw.get("data") or {}

    def update_filter(self, id: str, name=None, conditions=None):
        body = {}
        if name: body["name"] = name
        if conditions: body["conditions"] = conditions
        raw = self._put(f"filters/{id}", body)
        return {"success": True, "action": "update_filter", "id": id, "raw": raw}

    def delete_filter(self, id: str):
        raw = self._delete(f"filters/{id}")
        return {"success": True, "action": "delete_filter", "id": id, "raw": raw}

    # ── Call Logs ───────────────────────────────────────────────────────────
    def list_call_logs(self, limit=50, start=0):
        raw = self._get("callLogs", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def create_call_log(self, subject: str, duration: int, outcome: str, to_phone: str, from_phone: str = "", deal_id=None, person_id=None, org_id=None):
        body = {"subject": subject, "duration": duration, "outcome": outcome, "to_phone_number": to_phone}
        if from_phone: body["from_phone_number"] = from_phone
        if deal_id: body["deal_id"] = int(deal_id)
        if person_id: body["person_id"] = int(person_id)
        if org_id: body["org_id"] = int(org_id)
        raw = self._post("callLogs", body)
        return {"success": True, "action": "create_call_log", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def get_call_log(self, id: str):
        raw = self._get(f"callLogs/{id}")
        return raw.get("data") or {}

    def delete_call_log(self, id: str):
        raw = self._delete(f"callLogs/{id}")
        return {"success": True, "action": "delete_call_log", "id": id, "raw": raw}

    # ── Mailbox ─────────────────────────────────────────────────────────────
    def list_mail_threads(self, limit=50, start=0, folder="inbox"):
        raw = self._get("mailbox/mailThreads", f"limit={min(limit, 500)}&start={start}&folder={folder}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_mail_messages(self, thread_id: str):
        raw = self._get(f"mailbox/mailThreads/{thread_id}/mailMessages")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def get_mail_message(self, id: str):
        raw = self._get(f"mailbox/mailMessages/{id}")
        return raw.get("data") or {}

    # ── Custom Fields ───────────────────────────────────────────────────────
    def list_deal_fields(self):
        raw = self._get("dealFields")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_person_fields(self):
        raw = self._get("personFields")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_org_fields(self):
        raw = self._get("organizationFields")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_activity_fields(self):
        raw = self._get("activityFields")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_product_fields(self):
        raw = self._get("productFields")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Products (extend) ───────────────────────────────────────────────────
    def update_product(self, id: str, name=None, code=None, unit=None, price=None):
        body = {}
        if name: body["name"] = name
        if code: body["code"] = code
        if unit: body["unit"] = unit
        if price is not None: body["prices"] = [{"price": price, "currency": "BRL"}]
        raw = self._put(f"products/{id}", body)
        return {"success": True, "action": "update_product", "id": id, "raw": raw}

    def delete_product(self, id: str):
        raw = self._delete(f"products/{id}")
        return {"success": True, "action": "delete_product", "id": id, "raw": raw}

    def list_product_deals(self, id: str, limit=50, start=0):
        raw = self._get(f"products/{id}/deals", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def list_product_files(self, id: str, limit=50, start=0):
        raw = self._get(f"products/{id}/files", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Roles ───────────────────────────────────────────────────────────────
    def list_roles(self):
        raw = self._get("roles")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    def create_role(self, name: str, parent_role_id=None):
        body = {"name": name}
        if parent_role_id: body["parent_role_id"] = int(parent_role_id)
        raw = self._post("roles", body)
        return {"success": True, "action": "create_role", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def get_role(self, id: str):
        raw = self._get(f"roles/{id}")
        return raw.get("data") or {}

    def update_role(self, id: str, name: str):
        raw = self._put(f"roles/{id}", {"name": name})
        return {"success": True, "action": "update_role", "id": id, "raw": raw}

    def delete_role(self, id: str):
        raw = self._delete(f"roles/{id}")
        return {"success": True, "action": "delete_role", "id": id, "raw": raw}

    def list_role_assignments(self, id: str):
        raw = self._get(f"roles/{id}/assignments")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Recents ─────────────────────────────────────────────────────────────
    def get_recents(self, since_timestamp: str, items: str = "deal", limit=50, start=0):
        raw = self._get("recents", f"since_timestamp={since_timestamp}&items={items}&limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Item Search ─────────────────────────────────────────────────────────
    def search_items(self, term: str, item_types: str = "deal", limit=50, start=0):
        raw = self._get("itemSearch", f"term={term}&item_types={item_types}&limit={min(limit, 500)}&start={start}")
        data = raw.get("data", {}) or {}
        items = data.get("items", []) if isinstance(data, dict) else []
        return {"items": items, "count": len(items)}

    # ── Notes (extend) ──────────────────────────────────────────────────────
    def get_note(self, id: str):
        raw = self._get(f"notes/{id}")
        return raw.get("data") or {}

    def update_note(self, id: str, content: str):
        raw = self._put(f"notes/{id}", {"content": content})
        return {"success": True, "action": "update_note", "id": id, "raw": raw}

    def delete_note(self, id: str):
        raw = self._delete(f"notes/{id}")
        return {"success": True, "action": "delete_note", "id": id, "raw": raw}

    # ── User detail ─────────────────────────────────────────────────────────
    def get_user(self, id: str):
        raw = self._get(f"users/{id}")
        return raw.get("data") or {}

    # ── Currencies ──────────────────────────────────────────────────────────
    def list_currencies(self):
        raw = self._get("currencies")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Pipelines (extend) ──────────────────────────────────────────────────
    def get_pipeline(self, id: str):
        raw = self._get(f"pipelines/{id}")
        return raw.get("data") or {}

    def get_pipeline_deals(self, id: str, limit=50, start=0):
        raw = self._get(f"pipelines/{id}/deals", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Pipelines (write) ───────────────────────────────────────────────────
    def create_pipeline(self, name: str, deal_probability: int = 1, active: bool = True):
        body = {"name": name, "deal_probability": 1 if deal_probability else 0, "active": active}
        raw = self._post("pipelines", body)
        return {"success": True, "action": "create_pipeline", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def update_pipeline(self, id: str, name=None, deal_probability=None, active=None):
        body = {}
        if name: body["name"] = name
        if deal_probability is not None: body["deal_probability"] = deal_probability
        if active is not None: body["active"] = active
        raw = self._put(f"pipelines/{id}", body)
        return {"success": True, "action": "update_pipeline", "id": id, "raw": raw}

    def delete_pipeline(self, id: str):
        raw = self._delete(f"pipelines/{id}")
        return {"success": True, "action": "delete_pipeline", "id": id, "raw": raw}

    # ── Stages (write) ──────────────────────────────────────────────────────
    def get_stage(self, id: str):
        raw = self._get(f"stages/{id}")
        return raw.get("data") or {}

    def create_stage(self, name: str, pipeline_id: int, order_nr: int = None):
        body = {"name": name, "pipeline_id": pipeline_id}
        if order_nr is not None: body["order_nr"] = order_nr
        raw = self._post("stages", body)
        return {"success": True, "action": "create_stage", "id": str((raw.get("data") or {}).get("id", "")), "raw": raw}

    def update_stage(self, id: str, name=None, order_nr=None, pipeline_id=None):
        body = {}
        if name: body["name"] = name
        if order_nr is not None: body["order_nr"] = order_nr
        if pipeline_id: body["pipeline_id"] = pipeline_id
        raw = self._put(f"stages/{id}", body)
        return {"success": True, "action": "update_stage", "id": id, "raw": raw}

    def delete_stage(self, id: str):
        raw = self._delete(f"stages/{id}")
        return {"success": True, "action": "delete_stage", "id": id, "raw": raw}

    def list_stage_deals(self, id: str, limit=50, start=0):
        raw = self._get(f"stages/{id}/deals", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Lead Sources ────────────────────────────────────────────────────────
    def list_lead_sources(self):
        raw = self._get("leadSources")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Person emails (mailMessages) ────────────────────────────────────────
    def list_person_mail_messages(self, id: str, limit=50, start=0):
        raw = self._get(f"persons/{id}/mailMessages", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}

    # ── Org mail messages ───────────────────────────────────────────────────
    def list_org_mail_messages(self, id: str, limit=50, start=0):
        raw = self._get(f"organizations/{id}/mailMessages", f"limit={min(limit, 500)}&start={start}")
        return {"items": raw.get("data", []) or [], "count": len(raw.get("data", []) or [])}


if __name__ == "__main__":
    try:
        client = PipedriveClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
