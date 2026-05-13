#!/usr/bin/env python3
"""Kommo CRM Client (formerly amoCRM) — Agente CFO skill."""
import json as _json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseCRMClient, http_request, emit, emit_error, now_iso, make_deal_item, make_list_response


class KommoClient(BaseCRMClient):
    SKILL_NAME = "kommo"

    def _validate_env(self):
        if not os.environ.get("KOMMO_SUBDOMAIN"):
            raise RuntimeError("KOMMO_SUBDOMAIN nao definido. Execute connect.sh.")
        if not os.environ.get("KOMMO_ACCESS_TOKEN"):
            raise RuntimeError("KOMMO_ACCESS_TOKEN nao definido. Execute connect.sh.")
        self.subdomain = os.environ["KOMMO_SUBDOMAIN"]
        self.token = os.environ["KOMMO_ACCESS_TOKEN"]
        self.base_url = f"https://{self.subdomain}.kommo.com/api/v4"

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: str = "") -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url += ("&" if "?" in url else "?") + params
        return http_request("GET", url, headers=self._headers())

    def _post(self, path: str, body) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("POST", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    def _patch(self, path: str, body) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("PATCH", url, headers=self._headers(),
                            body=_json.dumps(body).encode())

    def _delete(self, path: str) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        return http_request("DELETE", url, headers=self._headers())

    # ── Response helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_embedded(data: dict, key: str) -> list:
        """Extract items from Kommo's _embedded.{key} response format."""
        embedded = data.get("_embedded", {})
        return embedded.get(key, [])

    # ── BaseCRMClient interface (Leads = Deals) ──────────────────────────────

    def list_deals(self, status: str = "open", limit: int = 50, page: int = 1) -> dict:
        params = f"limit={min(limit, 250)}&page={page}&with=contacts"
        if status == "won":
            params += "&filter[statuses][0][status_id]=142"
        elif status == "lost":
            params += "&filter[statuses][0][status_id]=143"
        # open = default (all non-closed); all = no filter
        raw = self._get("leads", params)
        leads = self._extract_embedded(raw, "leads")
        items = []
        for d in leads:
            s = d.get("status_id")
            if s == 142:
                deal_status = "won"
            elif s == 143:
                deal_status = "lost"
            else:
                deal_status = "open"
            if status not in ("all", deal_status) and status != "open":
                continue
            items.append(make_deal_item(
                id=str(d.get("id", "")),
                title=d.get("name", ""),
                amount_brl=float(d.get("price", 0)) if d.get("price") is not None else None,
                stage=str(d.get("status_id", "")),
                status=deal_status,
                expected_close_date=None,
                owner=str(d.get("responsible_user_id", "")) if d.get("responsible_user_id") else None,
                raw=d,
            ))
        total = raw.get("_total_items") or len(items)
        total_pages = max(1, -(-total // limit))
        return make_list_response(items, page=page, total_pages=total_pages, total_count=total)

    def get_lead(self, id: str) -> dict:
        raw = self._get(f"leads/{id}", "with=contacts")
        return raw

    def create_deal(self, title: str, amount: float | None = None, pipeline: str | None = None) -> dict:
        body: dict = {"name": title}
        if amount is not None:
            body["price"] = amount
        if pipeline:
            body["pipeline_id"] = int(pipeline)
        raw = self._post("leads", [body])
        embedded = self._extract_embedded(raw, "leads")
        new_id = str(embedded[0].get("id", "")) if embedded else ""
        return {"success": True, "action": "create_deal", "id": new_id, "raw": raw}

    def update_deal(self, id: str, amount: float | None = None, close_date: str | None = None) -> dict:
        body: dict = {"id": int(id)}
        if amount is not None:
            body["price"] = amount
        # Kommo doesn't have a native close_date field; store in custom field if needed
        raw = self._patch("leads", [body])
        return {"success": True, "action": "update_deal", "id": id, "raw": raw}

    def update_lead(self, id: str, name: str | None = None, price: float | None = None,
                    status_id: int | None = None, pipeline_id: int | None = None,
                    responsible_user_id: int | None = None) -> dict:
        body: dict = {"id": int(id)}
        if name is not None:
            body["name"] = name
        if price is not None:
            body["price"] = price
        if status_id is not None:
            body["status_id"] = status_id
        if pipeline_id is not None:
            body["pipeline_id"] = pipeline_id
        if responsible_user_id is not None:
            body["responsible_user_id"] = responsible_user_id
        raw = self._patch("leads", [body])
        return {"success": True, "action": "update_lead", "id": id, "raw": raw}

    def delete_lead(self, id: str) -> dict:
        raw = self._delete(f"leads/{id}")
        return {"success": True, "action": "delete_lead", "id": id, "raw": raw}

    def move_deal(self, id: str, to_stage: str) -> dict:
        body = {"id": int(id), "status_id": int(to_stage)}
        raw = self._patch("leads", [body])
        return {"success": True, "action": "move_deal", "id": id,
                "after": {"status_id": to_stage}, "raw": raw}

    def add_deal_note(self, id: str, note: str) -> dict:
        body = [{"note_type": "common", "params": {"text": note}}]
        raw = self._post(f"leads/{id}/notes", body)
        return {"success": True, "action": "add_deal_note", "deal_id": id, "raw": raw}

    def mark_deal_won(self, id: str) -> dict:
        body = [{"id": int(id), "status_id": 142}]
        raw = self._patch("leads", body)
        return {"success": True, "action": "mark_deal_won", "id": id,
                "after": {"status_id": 142}, "raw": raw}

    def mark_deal_lost(self, id: str, reason: str = "") -> dict:
        body: dict = {"id": int(id), "status_id": 143}
        if reason:
            body["loss_reason"] = [{"id": 0, "content": reason}]
        raw = self._patch("leads", [body])
        return {"success": True, "action": "mark_deal_lost", "id": id,
                "after": {"status_id": 143, "reason": reason}, "raw": raw}

    def company_info(self) -> dict:
        raw = self._get("account")
        return {
            "name": raw.get("name", "N/A"),
            "id": raw.get("id"),
            "subdomain": raw.get("subdomain"),
            "segment": "CRM",
            "raw": raw,
        }

    # ── Contacts ─────────────────────────────────────────────────────────────

    def list_contacts(self, limit: int = 50, page: int = 1) -> dict:
        raw = self._get("contacts", f"limit={min(limit, 250)}&page={page}")
        contacts = self._extract_embedded(raw, "contacts")
        items = []
        for c in contacts:
            emails = []
            phones = []
            for cf in (c.get("custom_fields_values") or []):
                code = cf.get("field_code", "")
                vals = cf.get("values", [])
                if code == "EMAIL":
                    emails = [v.get("value", "") for v in vals]
                elif code == "PHONE":
                    phones = [v.get("value", "") for v in vals]
            items.append({
                "id": str(c.get("id", "")),
                "name": c.get("name", ""),
                "email": emails[0] if emails else "",
                "phone": phones[0] if phones else "",
                "responsible_user_id": c.get("responsible_user_id"),
            })
        return {"items": items, "count": len(items)}

    def get_contact(self, id: str) -> dict:
        return self._get(f"contacts/{id}")

    def create_contact(self, name: str, email: str | None = None, phone: str | None = None) -> dict:
        body: dict = {"name": name}
        cfv = []
        if email:
            cfv.append({"field_code": "EMAIL", "values": [{"value": email, "enum_code": "WORK"}]})
        if phone:
            cfv.append({"field_code": "PHONE", "values": [{"value": phone, "enum_code": "WORK"}]})
        if cfv:
            body["custom_fields_values"] = cfv
        raw = self._post("contacts", [body])
        embedded = self._extract_embedded(raw, "contacts")
        new_id = str(embedded[0].get("id", "")) if embedded else ""
        return {"success": True, "action": "create_contact", "id": new_id, "raw": raw}

    def update_contact(self, id: str, name: str | None = None, email: str | None = None,
                       phone: str | None = None) -> dict:
        body: dict = {"id": int(id)}
        if name:
            body["name"] = name
        cfv = []
        if email:
            cfv.append({"field_code": "EMAIL", "values": [{"value": email, "enum_code": "WORK"}]})
        if phone:
            cfv.append({"field_code": "PHONE", "values": [{"value": phone, "enum_code": "WORK"}]})
        if cfv:
            body["custom_fields_values"] = cfv
        raw = self._patch("contacts", [body])
        return {"success": True, "action": "update_contact", "id": id, "raw": raw}

    # ── Companies ────────────────────────────────────────────────────────────

    def list_companies(self, limit: int = 50, page: int = 1) -> dict:
        raw = self._get("companies", f"limit={min(limit, 250)}&page={page}")
        companies = self._extract_embedded(raw, "companies")
        items = [{"id": str(c.get("id", "")), "name": c.get("name", "")}
                 for c in companies]
        return {"items": items, "count": len(items)}

    def get_company(self, id: str) -> dict:
        return self._get(f"companies/{id}")

    def create_company(self, name: str) -> dict:
        raw = self._post("companies", [{"name": name}])
        embedded = self._extract_embedded(raw, "companies")
        new_id = str(embedded[0].get("id", "")) if embedded else ""
        return {"success": True, "action": "create_company", "id": new_id, "raw": raw}

    def update_company(self, id: str, name: str | None = None) -> dict:
        body: dict = {"id": int(id)}
        if name:
            body["name"] = name
        raw = self._patch("companies", [body])
        return {"success": True, "action": "update_company", "id": id, "raw": raw}

    # ── Customers (segments) ─────────────────────────────────────────────────

    def list_customers(self, limit: int = 50, page: int = 1) -> dict:
        raw = self._get("customers", f"limit={min(limit, 250)}&page={page}")
        customers = self._extract_embedded(raw, "customers")
        items = [{"id": str(c.get("id", "")), "name": c.get("name", ""),
                  "status_id": c.get("status_id")}
                 for c in customers]
        return {"items": items, "count": len(items)}

    def get_customer(self, id: str) -> dict:
        return self._get(f"customers/{id}")

    def create_customer(self, name: str) -> dict:
        raw = self._post("customers", [{"name": name}])
        embedded = self._extract_embedded(raw, "customers")
        new_id = str(embedded[0].get("id", "")) if embedded else ""
        return {"success": True, "action": "create_customer", "id": new_id, "raw": raw}

    def update_customer(self, id: str, name: str | None = None) -> dict:
        body: dict = {"id": int(id)}
        if name:
            body["name"] = name
        raw = self._patch("customers", [body])
        return {"success": True, "action": "update_customer", "id": id, "raw": raw}

    # ── Tasks ────────────────────────────────────────────────────────────────

    def list_tasks(self, limit: int = 50, page: int = 1) -> dict:
        raw = self._get("tasks", f"limit={min(limit, 250)}&page={page}")
        tasks = self._extract_embedded(raw, "tasks")
        items = [{"id": str(t.get("id", "")), "text": t.get("text", ""),
                  "entity_id": t.get("entity_id"), "entity_type": t.get("entity_type"),
                  "complete_till": t.get("complete_till"),
                  "is_completed": t.get("is_completed")}
                 for t in tasks]
        return {"items": items, "count": len(items)}

    def create_task(self, text: str, entity_id: int | None = None, entity_type: str | None = None,
                    complete_till: int | None = None, task_type_id: int | None = None) -> dict:
        body: dict = {"text": text}
        if entity_id is not None:
            body["entity_id"] = entity_id
        if entity_type:
            body["entity_type"] = entity_type
        if complete_till is not None:
            body["complete_till"] = complete_till
        if task_type_id is not None:
            body["task_type_id"] = task_type_id
        raw = self._post("tasks", [body])
        embedded = self._extract_embedded(raw, "tasks")
        new_id = str(embedded[0].get("id", "")) if embedded else ""
        return {"success": True, "action": "create_task", "id": new_id, "raw": raw}

    def update_task(self, id: str, text: str | None = None, complete_till: int | None = None) -> dict:
        body: dict = {"id": int(id)}
        if text is not None:
            body["text"] = text
        if complete_till is not None:
            body["complete_till"] = complete_till
        raw = self._patch("tasks", [body])
        return {"success": True, "action": "update_task", "id": id, "raw": raw}

    def complete_task(self, id: str) -> dict:
        body = [{"id": int(id), "is_completed": True}]
        raw = self._patch("tasks", body)
        return {"success": True, "action": "complete_task", "id": id, "raw": raw}

    # ── Pipelines ────────────────────────────────────────────────────────────

    def list_pipelines(self) -> dict:
        raw = self._get("leads/pipelines")
        pipelines = self._extract_embedded(raw, "pipelines")
        items = [{"id": str(p.get("id", "")), "name": p.get("name", ""),
                  "is_main": p.get("is_main"), "sort": p.get("sort")}
                 for p in pipelines]
        return {"items": items, "count": len(items)}

    def get_pipeline(self, id: str) -> dict:
        return self._get(f"leads/pipelines/{id}")

    def list_pipeline_statuses(self, pipeline_id: str) -> dict:
        raw = self._get(f"leads/pipelines/{pipeline_id}/statuses")
        statuses = self._extract_embedded(raw, "statuses")
        items = [{"id": str(s.get("id", "")), "name": s.get("name", ""),
                  "sort": s.get("sort"), "color": s.get("color"),
                  "type": s.get("type")}
                 for s in statuses]
        return {"items": items, "count": len(items)}

    # ── Users ────────────────────────────────────────────────────────────────

    def list_users(self) -> dict:
        raw = self._get("users")
        users = self._extract_embedded(raw, "users")
        items = [{"id": str(u.get("id", "")), "name": u.get("name", ""),
                  "email": u.get("email", ""), "rights": u.get("rights")}
                 for u in users]
        return {"items": items, "count": len(items)}

    def get_user(self, id: str) -> dict:
        return self._get(f"users/{id}")

    # ── Account ──────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        return self._get("account")

    # ── Custom Fields ────────────────────────────────────────────────────────

    def list_custom_fields(self, entity_type: str) -> dict:
        raw = self._get(f"{entity_type}/custom_fields")
        fields = self._extract_embedded(raw, "custom_fields")
        items = [{"id": str(f.get("id", "")), "name": f.get("name", ""),
                  "type": f.get("type"), "code": f.get("code")}
                 for f in fields]
        return {"items": items, "count": len(items)}

    # ── Catalogs ─────────────────────────────────────────────────────────────

    def list_catalogs(self) -> dict:
        raw = self._get("catalogs")
        catalogs = self._extract_embedded(raw, "catalogs")
        items = [{"id": str(c.get("id", "")), "name": c.get("name", ""),
                  "type": c.get("type")}
                 for c in catalogs]
        return {"items": items, "count": len(items)}

    def get_catalog(self, id: str) -> dict:
        return self._get(f"catalogs/{id}")

    def list_catalog_elements(self, catalog_id: str, limit: int = 50, page: int = 1) -> dict:
        raw = self._get(f"catalogs/{catalog_id}/elements", f"limit={min(limit, 250)}&page={page}")
        elements = self._extract_embedded(raw, "elements")
        items = [{"id": str(e.get("id", "")), "name": e.get("name", ""),
                  "custom_fields_values": e.get("custom_fields_values")}
                 for e in elements]
        return {"items": items, "count": len(items)}

    # ── Events ───────────────────────────────────────────────────────────────

    def list_events(self, limit: int = 50, page: int = 1) -> dict:
        raw = self._get("events", f"limit={min(limit, 100)}&page={page}")
        events = self._extract_embedded(raw, "events")
        items = [{"id": str(e.get("id", "")), "type": e.get("type", ""),
                  "entity_id": e.get("entity_id"), "entity_type": e.get("entity_type"),
                  "created_at": e.get("created_at")}
                 for e in events]
        return {"items": items, "count": len(items)}

    # ── Calls ────────────────────────────────────────────────────────────────

    def log_call(self, direction: str, uniq: str, duration: int, source: str,
                 phone: str, entity_id: int | None = None, entity_type: str | None = None) -> dict:
        body: dict = {
            "direction": direction,
            "uniq": uniq,
            "duration": duration,
            "source": source,
            "phone": phone,
        }
        if entity_id is not None:
            body["entity_id"] = entity_id
        if entity_type:
            body["entity_type"] = entity_type
        raw = self._post("calls", [body])
        return {"success": True, "action": "log_call", "raw": raw}

    # ── Tags ─────────────────────────────────────────────────────────────────

    def list_tags(self, entity_type: str) -> dict:
        raw = self._get(f"{entity_type}/tags")
        tags = self._extract_embedded(raw, "tags")
        items = [{"id": str(t.get("id", "")), "name": t.get("name", ""),
                  "color": t.get("color")}
                 for t in tags]
        return {"items": items, "count": len(items)}

    # ── Webhooks ─────────────────────────────────────────────────────────────

    def list_webhooks(self) -> dict:
        raw = self._get("webhooks")
        webhooks = self._extract_embedded(raw, "webhooks")
        items = [{"id": str(w.get("id", "")), "destination": w.get("destination", ""),
                  "settings": w.get("settings")}
                 for w in webhooks]
        return {"items": items, "count": len(items)}

    def create_webhook(self, destination: str, settings: list | None = None) -> dict:
        body: dict = {"destination": destination}
        if settings:
            body["settings"] = settings
        raw = self._post("webhooks", body)
        return {"success": True, "action": "create_webhook", "raw": raw}

    def delete_webhook(self, id: str) -> dict:
        raw = self._delete(f"webhooks/{id}")
        return {"success": True, "action": "delete_webhook", "id": id, "raw": raw}

    # ── Notes (generic) ─────────────────────────────────────────────────────

    def list_notes(self, entity_type: str, entity_id: str, limit: int = 50, page: int = 1) -> dict:
        raw = self._get(f"{entity_type}/{entity_id}/notes", f"limit={min(limit, 250)}&page={page}")
        notes = self._extract_embedded(raw, "notes")
        items = [{"id": str(n.get("id", "")), "note_type": n.get("note_type", ""),
                  "text": (n.get("params") or {}).get("text", ""),
                  "created_at": n.get("created_at")}
                 for n in notes]
        return {"items": items, "count": len(items)}

    def create_note(self, entity_type: str, entity_id: str, text: str) -> dict:
        body = [{"note_type": "common", "params": {"text": text}}]
        raw = self._post(f"{entity_type}/{entity_id}/notes", body)
        return {"success": True, "action": "create_note", "entity_type": entity_type,
                "entity_id": entity_id, "raw": raw}

    # ── Links ────────────────────────────────────────────────────────────────

    def list_links(self, entity_type: str, entity_id: str) -> dict:
        raw = self._get(f"{entity_type}/{entity_id}/links")
        links = self._extract_embedded(raw, "links")
        items = [{"to_entity_id": l.get("to_entity_id"),
                  "to_entity_type": l.get("to_entity_type"),
                  "metadata": l.get("metadata")}
                 for l in links]
        return {"items": items, "count": len(items)}

    def add_link(self, entity_type: str, entity_id: str, to_entity_type: str, to_entity_id: int) -> dict:
        body = [{"to_entity_id": to_entity_id, "to_entity_type": to_entity_type}]
        raw = self._post(f"{entity_type}/{entity_id}/link", body)
        return {"success": True, "action": "add_link", "raw": raw}


if __name__ == "__main__":
    try:
        client = KommoClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
