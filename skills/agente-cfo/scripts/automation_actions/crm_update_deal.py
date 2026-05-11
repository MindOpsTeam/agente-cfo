"""Action: crm_update_deal — atualiza campos de um deal no CRM."""
from __future__ import annotations
import subprocess
from . import Action


class CRMUpdateDeal(Action):
    type = "crm_update_deal"
    require_confirmation_default = True

    def execute(self, spec: dict, run_context: dict) -> dict:
        scripts_dir = run_context.get("scripts_dir", "")
        deal_id = spec.get("deal_id", "")
        fields = spec.get("fields", {})

        if not deal_id:
            return {"success": False, "output": {}, "error": "deal_id obrigatório"}
        if not fields:
            return {"success": False, "output": {}, "error": "fields obrigatório"}

        errors = []
        updated = []

        for key, val in fields.items():
            try:
                result = subprocess.run(
                    [
                        "python3", f"{scripts_dir}/crm_gateway.py",
                        "update_deal", "--id", str(deal_id),
                        "--field", str(key), "--value", str(val),
                    ],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    errors.append(f"{key}: exit {result.returncode} — {result.stderr[:100]}")
                else:
                    updated.append(key)
            except Exception as e:
                errors.append(f"{key}: {e}")

        success = len(errors) == 0
        return {
            "success": success,
            "output": {"deal_id": deal_id, "updated_fields": updated, "errors": errors},
            "error": "; ".join(errors) if errors else None,
        }
