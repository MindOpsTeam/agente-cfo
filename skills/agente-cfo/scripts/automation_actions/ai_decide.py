"""Action: ai_decide — delega decisão para a IA (Marcos CFO) via hooks/agent."""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
from . import Action


class AIDecide(Action):
    type = "ai_decide"
    require_confirmation_default = True

    def execute(self, spec: dict, run_context: dict) -> dict:
        env = run_context.get("env", {})
        hooks_url = env.get("HOOKS_URL", os.environ.get("HOOKS_URL", ""))
        hooks_token = env.get("HOOKS_TOKEN", os.environ.get("HOOKS_TOKEN", ""))

        if not hooks_url or not hooks_token:
            return {
                "success": False,
                "output": {},
                "error": "HOOKS_URL e HOOKS_TOKEN são obrigatórios para ai_decide",
            }

        context = spec.get("context", "")
        options = spec.get("options", [])
        options_text = "\n".join(f"- {opt}" for opt in options) if options else "Sem opções definidas."

        message = (
            f"Você é Marcos CFO. {context}\n\n"
            f"Opções disponíveis:\n{options_text}\n\n"
            f"Responda APENAS com o nome exato de uma das opções acima."
        )

        payload = json.dumps({
            "message": message,
            "name": "AutomationAIDecide",
            "deliver": False,
            "timeoutSeconds": 60,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{hooks_url}/hooks/agent",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {hooks_token}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=70) as resp:
                response_text = resp.read().decode().strip()
                return {
                    "success": True,
                    "output": {"decision": response_text, "raw": response_text},
                    "error": None,
                }
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            return {
                "success": False,
                "output": {},
                "error": f"hooks/agent HTTP {e.code}: {body}",
            }
        except Exception as e:
            return {"success": False, "output": {}, "error": str(e)}
