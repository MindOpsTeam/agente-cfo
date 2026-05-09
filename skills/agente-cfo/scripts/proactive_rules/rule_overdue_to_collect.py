"""
rule_overdue_to_collect — Sugere ao dono cobrar cliente inadimplente via plataforma de cobrança.

Trigger: cliente com total_overdue_brl > CFO_COLLECT_MIN_BRL (default R$ 500)
         e oldest_due_date há > CFO_COLLECT_MIN_DAYS (default 15 dias) atrás.
Severity: info
Cooldown: 168h por cliente (1 semana — não spam)
Dependência: plataforma de cobrança (Asaas ou Iugu via CFO_COBRANCA_NAME)

Nota de governança:
  Esta regra SUGERE ao dono. Marcos NUNCA envia cobrança ao terceiro sem
  confirmação explícita do dono (protocolo de cobrança ativa em conversa.md).
  O alerta apenas notifica o dono que há inadimplência cobrável.
"""
from __future__ import annotations
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from . import ProactiveRule, Alert

SKILLS_ROOT = Path.home() / ".openclaw" / "workspace" / "skills"

_MIN_BRL = float(os.environ.get("CFO_COLLECT_MIN_BRL", "500"))
_MIN_DAYS = int(os.environ.get("CFO_COLLECT_MIN_DAYS", "15"))


def _load_cobranca_client():
    """Carrega o client de cobrança configurado em CFO_COBRANCA_NAME."""
    import importlib
    cobranca_name = os.environ.get("CFO_COBRANCA_NAME", "nenhum")
    if cobranca_name == "nenhum":
        return None
    skill_dir = SKILLS_ROOT / cobranca_name / "scripts"
    if not skill_dir.exists():
        return None
    for p in [str(skill_dir), str(SKILLS_ROOT / "_lib")]:
        if p not in sys.path:
            sys.path.insert(0, p)
    module_name = f"{cobranca_name.replace('-', '_')}_client"
    class_name = cobranca_name.replace("-", "_").replace("_", " ").title().replace(" ", "") + "Client"
    try:
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        return cls()
    except Exception:
        return None


class RuleOverdueToCollect(ProactiveRule):
    name = "rule_overdue_to_collect"
    cooldown_hours = 168  # 1 semana por cliente

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        cobranca_client = _load_cobranca_client()
        if cobranca_client is None:
            return []

        try:
            resp = cobranca_client.get_overdue_customers()
        except (NotImplementedError, Exception):
            return []

        today = date.today()
        cutoff_date = (today - timedelta(days=_MIN_DAYS)).isoformat()

        alerts: list[Alert] = []
        for c in resp.get("items", []):
            total = float(c.get("total_overdue_brl", 0.0))
            oldest = c.get("oldest_due_date", "")
            cid = c.get("customer_id", "")
            cname = c.get("customer_name", "?")

            # Filtros: valor mínimo + antiguidade mínima
            if total < _MIN_BRL:
                continue
            if not oldest or oldest > cutoff_date:
                continue

            try:
                days_late = (today - date.fromisoformat(oldest)).days
            except Exception:
                days_late = 0

            dedup_key = f"overdue_to_collect:{cid}"
            phone_hint = f" (📱 {c.get('phone')})" if c.get("phone") else ""

            summary = (
                f"{cname}{phone_hint} está há {days_late} dias com "
                f"R$ {total:,.2f} em aberto ({c.get('invoice_count', 1)} fatura(s)). "
                f"Quer que eu mande uma mensagem de cobrança? "
                f"Responda: 'Cobra {cname}' ou acesse o painel."
            )

            alerts.append(Alert(
                rule_name=self.name,
                severity="info",
                summary=summary,
                raw_data={
                    "customer_id": cid,
                    "customer_name": cname,
                    "total_overdue_brl": round(total, 2),
                    "oldest_due_date": oldest,
                    "days_late": days_late,
                    "invoice_count": c.get("invoice_count", 1),
                    "phone": c.get("phone"),
                    "email": c.get("email"),
                    "cobranca_skill": os.environ.get("CFO_COBRANCA_NAME", ""),
                },
                dedup_key=dedup_key,
            ))

        return alerts
