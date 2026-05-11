"""Action: cobranca_send — envia cobrança (payment link ou reminder)."""
from __future__ import annotations
import subprocess
from . import Action


class CobrancaSend(Action):
    type = "cobranca_send"
    require_confirmation_default = True

    def execute(self, spec: dict, run_context: dict) -> dict:
        scripts_dir = run_context.get("scripts_dir", "")
        invoice_id = spec.get("invoice_id", "")
        customer_id = spec.get("customer_id", "")
        message = spec.get("message", "")

        try:
            if invoice_id:
                result = subprocess.run(
                    [
                        "python3", f"{scripts_dir}/cobranca_gateway.py",
                        "send_payment_link", "--invoice_id", str(invoice_id),
                    ],
                    capture_output=True, text=True, timeout=30,
                )
            elif customer_id and message:
                result = subprocess.run(
                    [
                        "python3", f"{scripts_dir}/cobranca_gateway.py",
                        "send_reminder",
                        "--customer_id", str(customer_id),
                        "--message", str(message),
                    ],
                    capture_output=True, text=True, timeout=30,
                )
            else:
                return {
                    "success": False,
                    "output": {},
                    "error": "invoice_id ou (customer_id + message) obrigatório",
                }

            if result.returncode != 0:
                return {
                    "success": False,
                    "output": {"invoice_id": invoice_id, "customer_id": customer_id},
                    "error": f"cobranca_gateway falhou: {result.stderr[:200]}",
                }
            return {
                "success": True,
                "output": {
                    "invoice_id": invoice_id,
                    "customer_id": customer_id,
                    "response": result.stdout[:200],
                },
                "error": None,
            }
        except Exception as e:
            return {"success": False, "output": {}, "error": str(e)}
