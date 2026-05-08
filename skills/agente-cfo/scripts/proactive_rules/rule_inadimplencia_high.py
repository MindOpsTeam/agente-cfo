"""
rule_inadimplencia_high — Taxa de inadimplência > 15% (total vencido / total a receber).

Severity: warn (>15%), critical (>30%)
Cooldown: 24h (global)
Dependência: ERP

Lógica:
  total_vencido  = recebíveis com status overdue OU (status pending E due_date < hoje)
  total_a_receber = todos os recebíveis pendentes + vencidos
  taxa = total_vencido / total_a_receber
"""
from __future__ import annotations
import os
from datetime import date
from . import ProactiveRule, Alert

INADIMPLENCIA_WARN_PCT = float(os.environ.get("CFO_INADIMPLENCIA_WARN_PCT", "15")) / 100.0
INADIMPLENCIA_CRITICAL_PCT = float(os.environ.get("CFO_INADIMPLENCIA_CRITICAL_PCT", "30")) / 100.0


class RuleInadimplenciaHigh(ProactiveRule):
    name = "rule_inadimplencia_high"
    cooldown_hours = 24

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if erp_client is None:
            return []

        today = date.today().isoformat()

        try:
            resp = erp_client.list_receivables(limit=500)
        except (NotImplementedError, Exception):
            return []

        items = [
            i for i in resp.get("items", [])
            if i.get("status") in ("pending", "overdue")
        ]
        if not items:
            return []

        total_a_receber = sum(float(i.get("amount_brl", 0.0)) for i in items)
        if total_a_receber <= 0:
            return []

        total_vencido = sum(
            float(i.get("amount_brl", 0.0))
            for i in items
            if i.get("status") == "overdue"
            or (i.get("status") == "pending" and (i.get("due_date", "9999") < today))
        )

        taxa = total_vencido / total_a_receber
        if taxa < INADIMPLENCIA_WARN_PCT:
            return []

        severity = "critical" if taxa >= INADIMPLENCIA_CRITICAL_PCT else "warn"
        pct = round(taxa * 100, 1)

        summary = (
            f"Taxa de inadimplência em {pct}% "
            f"(R$ {total_vencido:,.2f} vencido de R$ {total_a_receber:,.2f} a receber). "
            f"{'🔴 Nível crítico — ação urgente.' if severity == 'critical' else '⚠️ Acima do limite saudável (15%).'}"
        )

        return [Alert(
            rule_name=self.name,
            severity=severity,
            summary=summary,
            raw_data={
                "total_overdue_brl": round(total_vencido, 2),
                "total_receivables_brl": round(total_a_receber, 2),
                "inadimplencia_pct": pct,
                "warn_threshold_pct": round(INADIMPLENCIA_WARN_PCT * 100, 1),
                "critical_threshold_pct": round(INADIMPLENCIA_CRITICAL_PCT * 100, 1),
            },
            dedup_key="inadimplencia:global",
        )]
