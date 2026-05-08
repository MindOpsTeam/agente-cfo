"""
rule_overdue_critical — Conta vencida há mais de 7 dias.

Severity: warn  (crítico acima de 30 dias)
Cooldown: 168h (1 semana) por conta individual
Dependência: ERP

Comportamento:
  - Busca todas as contas a PAGAR e a RECEBER pendentes/vencidas
  - Filtra as vencidas há > OVERDUE_DAYS_THRESHOLD (default 7)
  - Re-alerta máximo 1x por semana por conta (dedup_key por ID)
  - Severity muda para "critical" se vencida há > 30 dias
"""
from __future__ import annotations
import os
from datetime import date, timedelta
from . import ProactiveRule, Alert

OVERDUE_DAYS_THRESHOLD = int(os.environ.get("CFO_OVERDUE_DAYS_THRESHOLD", "7"))
CRITICAL_DAYS_THRESHOLD = 30


class RuleOverdueCritical(ProactiveRule):
    name = "rule_overdue_critical"
    cooldown_hours = 168  # 1 semana por item

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if erp_client is None:
            return []

        alerts = []
        today = date.today()

        try:
            overdue_resp = erp_client.list_overdue()
        except NotImplementedError:
            return []
        except Exception:
            return []

        for item in overdue_resp.get("items", []):
            due_str = item.get("due_date", "")
            if not due_str:
                continue

            try:
                due_date = date.fromisoformat(due_str)
            except ValueError:
                continue

            days_late = (today - due_date).days
            if days_late < OVERDUE_DAYS_THRESHOLD:
                continue

            item_id = item.get("id", "")
            record_type = "recv" if item.get("status") in ("received",) else "pay"
            # Distinguir recebíveis de pagáveis pelo campo counterparty origem
            dedup_key = f"overdue:{record_type}_{item_id}"

            severity = "critical" if days_late > CRITICAL_DAYS_THRESHOLD else "warn"
            counterparty = item.get("counterparty", "desconhecido")
            amount = item.get("amount_brl", 0.0)

            summary = (
                f"Conta vencida há {days_late} dias: {counterparty}, "
                f"R$ {amount:,.2f} (vencimento {due_str}). "
                f"{'⚠️ Vencimento crítico.' if severity == 'critical' else ''}"
            ).strip()

            alerts.append(Alert(
                rule_name=self.name,
                severity=severity,
                summary=summary,
                raw_data={
                    "id": item_id,
                    "counterparty": counterparty,
                    "amount_brl": amount,
                    "due_date": due_str,
                    "days_late": days_late,
                    "category": item.get("category"),
                    "record_type": record_type,
                },
                dedup_key=dedup_key,
            ))

        return alerts
