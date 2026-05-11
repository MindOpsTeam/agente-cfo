"""Action: send_whatsapp — envia mensagem WhatsApp."""
from __future__ import annotations
import subprocess
from . import Action


class SendWhatsApp(Action):
    type = "send_whatsapp"
    require_confirmation_default = True

    def execute(self, spec: dict, run_context: dict) -> dict:
        scripts_dir = run_context.get("scripts_dir", "")
        to = spec.get("to", "owner")
        template = spec.get("template", "")

        # Substitui variáveis de contexto no template
        try:
            message = template.format(**run_context)
        except (KeyError, IndexError, ValueError):
            message = template

        if not message:
            return {"success": False, "output": {}, "error": "Template de mensagem vazio"}

        try:
            if to == "owner":
                result = subprocess.run(
                    ["bash", f"{scripts_dir}/_send_whatsapp.sh", message],
                    capture_output=True, text=True, timeout=30,
                )
            else:
                result = subprocess.run(
                    ["bash", f"{scripts_dir}/_send_whatsapp.sh", to, message],
                    capture_output=True, text=True, timeout=30,
                )

            if result.returncode != 0:
                return {
                    "success": False,
                    "output": {"to": to, "message": message},
                    "error": f"wacli send falhou (exit {result.returncode}): {result.stderr[:200]}",
                }

            return {
                "success": True,
                "output": {"to": to, "message": message},
                "error": None,
            }
        except Exception as e:
            return {"success": False, "output": {"to": to}, "error": str(e)}
