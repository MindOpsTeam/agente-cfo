"""Action: crm_create_task — cria tarefa no CRM."""
from __future__ import annotations
import subprocess
from . import Action


class CRMCreateTask(Action):
    type = "crm_create_task"
    require_confirmation_default = False

    def execute(self, spec: dict, run_context: dict) -> dict:
        scripts_dir = run_context.get("scripts_dir", "")
        title = spec.get("title", "")
        due_date = spec.get("due_date", "")

        if not title:
            return {"success": False, "output": {}, "error": "title obrigatório"}

        cmd = [
            "python3", f"{scripts_dir}/crm_gateway.py",
            "create_task", "--title", title,
        ]
        if due_date:
            cmd += ["--due_date", due_date]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return {
                    "success": False,
                    "output": {"title": title},
                    "error": f"crm_gateway create_task falhou: {result.stderr[:200]}",
                }
            return {
                "success": True,
                "output": {"title": title, "due_date": due_date, "response": result.stdout[:200]},
                "error": None,
            }
        except Exception as e:
            return {"success": False, "output": {"title": title}, "error": str(e)}
