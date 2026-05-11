"""Action: send_report — gera e envia relatório via WhatsApp."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from . import Action


class SendReport(Action):
    type = "send_report"
    require_confirmation_default = False

    def execute(self, spec: dict, run_context: dict) -> dict:
        scripts_dir = run_context.get("scripts_dir", "")
        report_type = spec.get("report_type", "dashboard")

        try:
            report_text = self._generate_report(report_type, scripts_dir, run_context)
        except Exception as e:
            return {"success": False, "output": {}, "error": f"Erro gerando relatório: {e}"}

        try:
            self._send_whatsapp(scripts_dir, report_text)
        except Exception as e:
            return {"success": False, "output": {"report": report_text}, "error": f"Erro enviando WhatsApp: {e}"}

        return {"success": True, "output": {"report_type": report_type, "report": report_text}, "error": None}

    def _generate_report(self, report_type: str, scripts_dir: str, run_context: dict) -> str:
        if report_type == "cash":
            return self._report_cash(scripts_dir)
        elif report_type == "pipeline":
            return self._report_pipeline(scripts_dir)
        elif report_type == "cobranca":
            return self._report_cobranca(scripts_dir)
        elif report_type == "dashboard":
            return self._report_dashboard(scripts_dir, run_context)
        else:
            return f"Tipo de relatório desconhecido: {report_type}"

    def _report_cash(self, scripts_dir: str) -> str:
        result = subprocess.run(
            ["python3", f"{scripts_dir}/erp_gateway.py", "get_cash_projection", "--days", "30"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return f"Erro ao gerar projeção de caixa: {result.stderr[:200]}"
        try:
            data = json.loads(result.stdout)
            balance = data.get("balance_brl", 0)
            incoming = data.get("incoming_brl", 0)
            outgoing = data.get("outgoing_brl", 0)
            projected = data.get("projected_balance_brl", balance + incoming - outgoing)
            return (
                f"*Relatório de Caixa (30 dias)*\n"
                f"Saldo atual: R$ {balance:,.2f}\n"
                f"A receber: R$ {incoming:,.2f}\n"
                f"A pagar: R$ {outgoing:,.2f}\n"
                f"Projeção: R$ {projected:,.2f}"
            )
        except (json.JSONDecodeError, ValueError):
            return result.stdout[:500] if result.stdout else "Sem dados de caixa disponíveis."

    def _report_pipeline(self, scripts_dir: str) -> str:
        result = subprocess.run(
            ["python3", f"{scripts_dir}/crm_gateway.py", "get_pipeline_projection"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return f"Erro ao gerar projeção de pipeline: {result.stderr[:200]}"
        try:
            data = json.loads(result.stdout)
            total = data.get("total_pipeline_brl", 0)
            deals_count = data.get("deals_count", 0)
            weighted = data.get("weighted_brl", 0)
            return (
                f"*Relatório de Pipeline*\n"
                f"Total pipeline: R$ {total:,.2f}\n"
                f"Deals abertos: {deals_count}\n"
                f"Valor ponderado: R$ {weighted:,.2f}"
            )
        except (json.JSONDecodeError, ValueError):
            return result.stdout[:500] if result.stdout else "Sem dados de pipeline disponíveis."

    def _report_cobranca(self, scripts_dir: str) -> str:
        result = subprocess.run(
            ["python3", f"{scripts_dir}/cobranca_gateway.py", "get_overdue_customers"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return f"Erro ao gerar relatório de cobrança: {result.stderr[:200]}"
        try:
            data = json.loads(result.stdout)
            items = data.get("items", [])
            if not items:
                return "*Relatório de Cobrança*\nNenhum inadimplente encontrado."
            lines = ["*Relatório de Cobrança — Top Devedores*"]
            total_overdue = 0.0
            for i, c in enumerate(items[:10], 1):
                name = c.get("customer_name", "?")
                amount = float(c.get("total_overdue_brl", 0))
                days = c.get("days_late", "?")
                total_overdue += amount
                lines.append(f"{i}. {name}: R$ {amount:,.2f} ({days}d)")
            lines.append(f"\nTotal inadimplência (top 10): R$ {total_overdue:,.2f}")
            return "\n".join(lines)
        except (json.JSONDecodeError, ValueError):
            return result.stdout[:500] if result.stdout else "Sem dados de cobrança disponíveis."

    def _report_dashboard(self, scripts_dir: str, run_context: dict) -> str:
        hooks_url = run_context.get("env", {}).get("HOOKS_URL", "")
        hooks_token = run_context.get("env", {}).get("HOOKS_TOKEN", "")
        if hooks_url and hooks_token:
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"{hooks_url}/hooks/agent",
                    data=json.dumps({
                        "message": "Execute: python3 dashboard_metrics.py e retorne o JSON completo",
                        "name": "AutomationDashboard",
                        "deliver": False,
                        "timeoutSeconds": 60,
                    }).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {hooks_token}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read().decode()
                    return f"*Dashboard Snapshot*\n{body[:800]}"
            except Exception:
                pass
        return "*Dashboard*\nSnapshot indisponível — configure HOOKS_URL."

    def _send_whatsapp(self, scripts_dir: str, message: str) -> None:
        subprocess.run(
            ["bash", f"{scripts_dir}/_send_whatsapp.sh", message],
            capture_output=True, timeout=30,
        )
