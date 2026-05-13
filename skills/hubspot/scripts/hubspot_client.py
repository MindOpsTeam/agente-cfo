#!/usr/bin/env python3
"""HubSpot CRM Client — Agente CFO skill."""

import json
import os
import sys

import json as _json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseCRMClient, http_request, emit, emit_error, now_iso, make_deal_item, make_list_response

STAGES_CACHE = os.path.expanduser("~/.openclaw/secrets/hubspot_stages.json")


class HubSpotClient(BaseCRMClient):
    SKILL_NAME = "hubspot"
    BASE_URL = "https://api.hubapi.com"

    def _validate_env(self):
        if not os.environ.get("HUBSPOT_TOKEN"):
            raise RuntimeError("HUBSPOT_TOKEN nao definido. Execute connect.sh.")
        self.token = os.environ["HUBSPOT_TOKEN"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        self._stages = self._load_stages()

    def _load_stages(self):
        if os.path.exists(STAGES_CACHE):
            try:
                with open(STAGES_CACHE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_stages(self, stages):
        try:
            os.makedirs(os.path.dirname(STAGES_CACHE), exist_ok=True)
            with open(STAGES_CACHE, "w") as f:
                json.dump(stages, f, indent=2)
        except Exception:
            pass

    def _fetch_stages(self):
        data = http_request("GET", f"{self.BASE_URL}/crm/v3/pipelines/deals", headers=self.headers)
        stages = {}
        results = data.get("results", []) if isinstance(data, dict) else []
        for pipeline in results:
            for stage in pipeline.get("stages", []):
                stages[stage.get("id", "")] = stage.get("label", stage.get("id", ""))
        self._stages = stages
        self._save_stages(stages)
        return stages

    def _get(self, path):
        url = f"{self.BASE_URL}/{path}"
        return http_request("GET", url, headers=self.headers)

    def _resolve_stage(self, stage_id):
        if stage_id in self._stages:
            return self._stages[stage_id]
        if not self._stages:
            self._fetch_stages()
        return self._stages.get(stage_id, stage_id)

    def list_deals(self, status="open", limit=50, page=1):
        props = "dealname,amount,dealstage,closedate,hubspot_owner_id"
        path = f"crm/v3/objects/deals?limit={limit}&properties={props}"
        data = self._get(path)
        items = []
        results = data.get("results", []) if isinstance(data, dict) else []
        for d in results:
            p = d.get("properties", {}) or {}
            stage_id = p.get("dealstage", "")
            stage_label = self._resolve_stage(stage_id)
            hs_closed = stage_label.lower() in ("closed won", "closedwon", "ganho", "fechado")
            hs_lost = stage_label.lower() in ("closed lost", "closedlost", "perdido")
            if hs_closed:
                deal_status = "won"
            elif hs_lost:
                deal_status = "lost"
            else:
                deal_status = "open"
            if status != "all" and deal_status != status:
                continue
            items.append(make_deal_item(
                id=str(d.get("id", "")),
                title=p.get("dealname", ""),
                amount_brl=float(p.get("amount", 0) or 0),
                stage=stage_label,
                status=deal_status,
                expected_close_date=(p.get("closedate", "") or "")[:10] or None,
                owner=p.get("hubspot_owner_id"),
                raw=d,
            ))
        total = data.get("total", len(items)) if isinstance(data, dict) else len(items)
        return make_list_response(items, page=page, total_count=total)

    def _patch(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("PATCH", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def _post_json(self, path, body: dict):
        url = f"{self.BASE_URL}/{path}"
        return http_request("POST", url, headers=self.headers,
                            body=_json.dumps(body).encode())

    def move_deal(self, id: str, to_stage: str) -> dict:
        raw = self._patch(f"crm/v3/objects/deals/{id}", {"properties": {"dealstage": to_stage}})
        return {"success": True, "action": "move_deal", "id": id,
                "after": {"stage": to_stage}, "raw": raw}

    def update_deal(self, id: str, amount: float | None = None, close_date: str | None = None) -> dict:
        props: dict = {}
        if amount is not None:
            props["amount"] = str(amount)
        if close_date:
            props["closedate"] = close_date
        raw = self._patch(f"crm/v3/objects/deals/{id}", {"properties": props})
        return {"success": True, "action": "update_deal", "id": id, "after": props, "raw": raw}

    def create_deal(self, title: str, amount: float | None = None, pipeline: str | None = None) -> dict:
        props: dict = {"dealname": title}
        if amount is not None:
            props["amount"] = str(amount)
        if pipeline:
            props["pipeline"] = pipeline
        raw = self._post_json("crm/v3/objects/deals", {"properties": props})
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": "create_deal", "id": str(new_id), "raw": raw}

    def add_deal_note(self, id: str, note: str) -> dict:
        note_body = {
            "properties": {"hs_note_body": note, "hs_timestamp": now_iso()},
            "associations": [{
                "to": {"id": int(id)},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}],
            }],
        }
        raw = self._post_json("crm/v3/objects/notes", note_body)
        return {"success": True, "action": "add_deal_note", "id": id, "raw": raw}

    def mark_deal_won(self, id: str) -> dict:
        raw = self._patch(f"crm/v3/objects/deals/{id}", {"properties": {"dealstage": "closedwon"}})
        return {"success": True, "action": "mark_deal_won", "id": id,
                "after": {"status": "won"}, "raw": raw}

    def mark_deal_lost(self, id: str, reason: str = "") -> dict:
        props: dict = {"dealstage": "closedlost"}
        if reason:
            props["closed_lost_reason"] = reason
        raw = self._patch(f"crm/v3/objects/deals/{id}", {"properties": props})
        return {"success": True, "action": "mark_deal_lost", "id": id,
                "after": {"status": "lost", "reason": reason}, "raw": raw}

    def company_info(self):
        try:
            data = self._get("crm/v3/owners?limit=1")
            results = data.get("results", []) if isinstance(data, dict) else []
            if results:
                owner = results[0]
                name = f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip()
                return {"name": name or "N/A"}
        except Exception:
            pass
        return {"name": "N/A"}

    # ── Generic CRM object helpers ─────────────────────────────────────────

    def _list_objects(self, object_type: str, properties: str | None = None, limit: int = 50) -> dict:
        path = f"crm/v3/objects/{object_type}?limit={limit}"
        if properties:
            path += f"&properties={properties}"
        data = self._get(path)
        results = data.get("results", []) if isinstance(data, dict) else []
        return {"items": results, "total": data.get("total", len(results)) if isinstance(data, dict) else len(results)}

    def _get_object(self, object_type: str, obj_id: str, properties: str | None = None) -> dict:
        path = f"crm/v3/objects/{object_type}/{obj_id}"
        if properties:
            path += f"?properties={properties}"
        return self._get(path)

    def _create_object(self, object_type: str, properties: dict) -> dict:
        raw = self._post_json(f"crm/v3/objects/{object_type}", {"properties": properties})
        new_id = raw.get("id", "") if isinstance(raw, dict) else ""
        return {"success": True, "action": f"create_{object_type}", "id": str(new_id), "raw": raw}

    def _update_object(self, object_type: str, obj_id: str, properties: dict) -> dict:
        raw = self._patch(f"crm/v3/objects/{object_type}/{obj_id}", {"properties": properties})
        return {"success": True, "action": f"update_{object_type}", "id": obj_id, "raw": raw}

    def _delete_object(self, object_type: str, obj_id: str) -> dict:
        url = f"{self.BASE_URL}/crm/v3/objects/{object_type}/{obj_id}"
        http_request("DELETE", url, headers=self.headers)
        return {"success": True, "action": f"delete_{object_type}", "id": obj_id}

    # ── Contacts ───────────────────────────────────────────────────────────

    def list_contacts(self, limit: int = 50) -> dict:
        return self._list_objects("contacts", properties="firstname,lastname,email,phone,company", limit=limit)

    def get_contact(self, contact_id: str) -> dict:
        return self._get_object("contacts", contact_id, properties="firstname,lastname,email,phone,company,lifecyclestage")

    def create_contact(self, email: str, firstname: str | None = None, lastname: str | None = None, phone: str | None = None) -> dict:
        props: dict = {"email": email}
        if firstname:
            props["firstname"] = firstname
        if lastname:
            props["lastname"] = lastname
        if phone:
            props["phone"] = phone
        return self._create_object("contacts", props)

    def update_contact(self, contact_id: str, properties: dict) -> dict:
        return self._update_object("contacts", contact_id, properties)

    def delete_contact(self, contact_id: str) -> dict:
        return self._delete_object("contacts", contact_id)

    # ── Companies ──────────────────────────────────────────────────────────

    def list_companies(self, limit: int = 50) -> dict:
        return self._list_objects("companies", properties="name,domain,industry,city,phone", limit=limit)

    def get_company(self, company_id: str) -> dict:
        return self._get_object("companies", company_id, properties="name,domain,industry,city,phone,numberofemployees")

    def create_company(self, name: str, domain: str | None = None, industry: str | None = None) -> dict:
        props: dict = {"name": name}
        if domain:
            props["domain"] = domain
        if industry:
            props["industry"] = industry
        return self._create_object("companies", props)

    def update_company(self, company_id: str, properties: dict) -> dict:
        return self._update_object("companies", company_id, properties)

    def delete_company(self, company_id: str) -> dict:
        return self._delete_object("companies", company_id)

    # ── Deals (complementary) ──────────────────────────────────────────────

    def get_deal(self, deal_id: str) -> dict:
        return self._get_object("deals", deal_id, properties="dealname,amount,dealstage,closedate,pipeline,hubspot_owner_id")

    # ── Tickets ────────────────────────────────────────────────────────────

    def list_tickets(self, limit: int = 50) -> dict:
        return self._list_objects("tickets", properties="subject,content,hs_pipeline_stage,hs_ticket_priority,createdate", limit=limit)

    def get_ticket(self, ticket_id: str) -> dict:
        return self._get_object("tickets", ticket_id, properties="subject,content,hs_pipeline_stage,hs_ticket_priority,createdate")

    def create_ticket(self, subject: str, content: str | None = None, priority: str | None = None) -> dict:
        props: dict = {"subject": subject}
        if content:
            props["content"] = content
        if priority:
            props["hs_ticket_priority"] = priority
        return self._create_object("tickets", props)

    # ── Line Items ─────────────────────────────────────────────────────────

    def list_line_items(self, limit: int = 50) -> dict:
        return self._list_objects("line_items", properties="name,quantity,price,amount", limit=limit)

    # ── Notes ──────────────────────────────────────────────────────────────

    def list_notes(self, limit: int = 50) -> dict:
        return self._list_objects("notes", properties="hs_note_body,hs_timestamp", limit=limit)

    def create_note(self, body: str, contact_id: str | None = None, deal_id: str | None = None) -> dict:
        note_body: dict = {
            "properties": {"hs_note_body": body, "hs_timestamp": now_iso()},
        }
        associations = []
        if contact_id:
            associations.append({
                "to": {"id": int(contact_id)},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
            })
        if deal_id:
            associations.append({
                "to": {"id": int(deal_id)},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}],
            })
        if associations:
            note_body["associations"] = associations
        raw = self._post_json("crm/v3/objects/notes", note_body)
        return {"success": True, "action": "create_note", "id": str(raw.get("id", "") if isinstance(raw, dict) else ""), "raw": raw}

    # ── Calls ──────────────────────────────────────────────────────────────

    def list_calls(self, limit: int = 50) -> dict:
        return self._list_objects("calls", properties="hs_call_title,hs_call_body,hs_call_duration,hs_call_status,hs_timestamp", limit=limit)

    def create_call(self, title: str, body: str | None = None, duration_ms: int | None = None, contact_id: str | None = None) -> dict:
        props: dict = {"hs_call_title": title, "hs_timestamp": now_iso(), "hs_call_status": "COMPLETED"}
        if body:
            props["hs_call_body"] = body
        if duration_ms is not None:
            props["hs_call_duration"] = str(duration_ms)
        call_body: dict = {"properties": props}
        if contact_id:
            call_body["associations"] = [{
                "to": {"id": int(contact_id)},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 194}],
            }]
        raw = self._post_json("crm/v3/objects/calls", call_body)
        return {"success": True, "action": "create_call", "id": str(raw.get("id", "") if isinstance(raw, dict) else ""), "raw": raw}

    # ── Emails ─────────────────────────────────────────────────────────────

    def list_emails(self, limit: int = 50) -> dict:
        return self._list_objects("emails", properties="hs_email_subject,hs_email_text,hs_email_status,hs_timestamp", limit=limit)

    # ── Meetings ───────────────────────────────────────────────────────────

    def list_meetings(self, limit: int = 50) -> dict:
        return self._list_objects("meetings", properties="hs_meeting_title,hs_meeting_body,hs_meeting_start_time,hs_meeting_end_time", limit=limit)

    # ── Tasks ──────────────────────────────────────────────────────────────

    def list_tasks(self, limit: int = 50) -> dict:
        return self._list_objects("tasks", properties="hs_task_subject,hs_task_body,hs_task_status,hs_task_priority,hs_timestamp", limit=limit)

    def create_task(self, subject: str, body: str | None = None, priority: str | None = None, due_date: str | None = None) -> dict:
        props: dict = {"hs_task_subject": subject, "hs_task_status": "NOT_STARTED", "hs_timestamp": now_iso()}
        if body:
            props["hs_task_body"] = body
        if priority:
            props["hs_task_priority"] = priority
        if due_date:
            props["hs_due_date"] = due_date
        return self._create_object("tasks", props)

    # ── Pipelines ──────────────────────────────────────────────────────────

    def list_pipelines(self, object_type: str = "deals") -> dict:
        data = self._get(f"crm/v3/pipelines/{object_type}")
        results = data.get("results", []) if isinstance(data, dict) else []
        return {"items": results, "total": len(results)}

    # ── Owners ─────────────────────────────────────────────────────────────

    def list_owners(self, limit: int = 100) -> dict:
        data = self._get(f"crm/v3/owners?limit={limit}")
        results = data.get("results", []) if isinstance(data, dict) else []
        return {"items": results, "total": len(results)}

    # ── Properties ─────────────────────────────────────────────────────────

    def list_properties(self, object_type: str = "deals") -> dict:
        data = self._get(f"crm/v3/properties/{object_type}")
        results = data.get("results", []) if isinstance(data, dict) else []
        return {"items": results, "total": len(results)}


if __name__ == "__main__":
    try:
        client = HubSpotClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
