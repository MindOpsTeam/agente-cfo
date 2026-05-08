#!/usr/bin/env python3
"""HubSpot CRM Client — Agente CFO skill."""

import json
import os
import sys

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


if __name__ == "__main__":
    try:
        client = HubSpotClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
