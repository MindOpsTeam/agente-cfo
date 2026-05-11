"""Action: erp_create_invoice — cria conta a receber no ERP."""
from __future__ import annotations
import subprocess
from . import Action


class ERPCreateInvoice(Action):
    type = "erp_create_invoice"
    require_confirmation_default = True

    def execute(self, spec: dict, run_context: dict) -> dict:
        scripts_dir = run_context.get("scripts_dir", "")
        customer = spec.get("customer", "")
        amount = spec.get("amount", "")
        due_date = spec.get("due_date", "")

        if not customer or not amount or not due_date:
            return {
                "success": False,
                "output": {},
                "error": "customer, amount e due_date são obrigatórios",
            }

        try:
            result = subprocess.run(
                [
                    "python3", f"{scripts_dir}/erp_gateway.py",
                    "create_receivable",
                    "--customer", str(customer),
                    "--amount", str(amount),
                    "--due_date", str(due_date),
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "output": {"customer": customer, "amount": amount},
                    "error": f"erp_gateway create_receivable falhou: {result.stderr[:200]}",
                }
            return {
                "success": True,
                "output": {
                    "customer": customer,
                    "amount": amount,
                    "due_date": due_date,
                    "response": result.stdout[:200],
                },
                "error": None,
            }
        except Exception as e:
            return {"success": False, "output": {"customer": customer}, "error": str(e)}
