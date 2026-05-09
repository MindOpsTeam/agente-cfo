"""
rule_pipeline_health — Pipeline projetado nos próximos 30 dias abaixo do threshold.

Severity: warn  (critical se < 30% do threshold)
Cooldown: 72h (global)
Dependência: CRM

Lógica:
  1. Chama get_pipeline_projection(horizon_days=30)
  2. expected_close_brl = deals com expected_close_date dentro de 30 dias
  3. Threshold = CFO_PIPELINE_HEALTH_THRESHOLD_BRL (env) ou heurística:
     LLM_BUDGET_BRL * CFO_PIPELINE_HEALTH_MULTIPLIER (default: 20)
  4. Se expected_close_brl < threshold → dispara
  5. Bonus: se overdue_close_count > 0 (deals com close_date vencido) → sempre informa

Env vars:
  CFO_PIPELINE_HEALTH_THRESHOLD_BRL  — threshold direto em R$ (sobreescreve heurística)
  CFO_PIPELINE_HEALTH_MULTIPLIER     — multiplicador sobre LLM_BUDGET_BRL (default: 20)
"""
from __future__ import annotations
import os
from . import ProactiveRule, Alert


def _pipeline_threshold() -> float:
    override = os.environ.get("CFO_PIPELINE_HEALTH_THRESHOLD_BRL")
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    budget = float(os.environ.get("LLM_BUDGET_BRL", "50"))
    multiplier = float(os.environ.get("CFO_PIPELINE_HEALTH_MULTIPLIER", "20"))
    return budget * multiplier


class RulePipelineHealth(ProactiveRule):
    name = "rule_pipeline_health"
    cooldown_hours = 72  # 3 dias

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if crm_client is None:
            return []

        try:
            proj = crm_client.get_pipeline_projection(horizon_days=30)
        except (NotImplementedError, Exception):
            return []

        expected_brl = float(proj.get("expected_close_brl", 0.0))
        expected_count = int(proj.get("expected_close_count", 0))
        overdue_count = int(proj.get("overdue_close_count", 0))
        overdue_brl = float(proj.get("overdue_close_brl", 0.0))
        total_open_brl = float(proj.get("total_open_brl", 0.0))
        no_date_count = int(proj.get("no_close_date_count", 0))

        threshold = _pipeline_threshold()
        alerts: list[Alert] = []

        # Alerta principal: pipeline esperado abaixo do threshold
        if expected_brl < threshold:
            severity = "critical" if expected_brl < threshold * 0.3 else "warn"

            overdue_hint = ""
            if overdue_count > 0:
                overdue_hint = (
                    f" Além disso, {overdue_count} deal(s) totalizando "
                    f"R$ {overdue_brl:,.2f} têm data de fechamento vencida."
                )

            no_date_hint = ""
            if no_date_count > 0:
                no_date_hint = (
                    f" {no_date_count} deal(s) sem data de fechamento definida "
                    f"não entram na projeção."
                )

            summary = (
                f"Pipeline projetado para os próximos 30 dias: R$ {expected_brl:,.2f} "
                f"({expected_count} deal(s)) — abaixo do threshold R$ {threshold:,.2f}. "
                f"Pipeline total aberto: R$ {total_open_brl:,.2f}."
                f"{overdue_hint}{no_date_hint}"
            )

            alerts.append(Alert(
                rule_name=self.name,
                severity=severity,
                summary=summary,
                raw_data={
                    "expected_close_30d_brl": round(expected_brl, 2),
                    "expected_close_30d_count": expected_count,
                    "overdue_close_brl": round(overdue_brl, 2),
                    "overdue_close_count": overdue_count,
                    "total_open_brl": round(total_open_brl, 2),
                    "no_close_date_count": no_date_count,
                    "threshold_brl": round(threshold, 2),
                    "by_week": proj.get("by_week", []),
                },
                dedup_key="pipeline_health:global",
            ))

        # Alerta secundário: deals com close_date vencido (independente do threshold)
        # Só dispara se não entrou no alerta principal (evita duplo aviso)
        elif overdue_count > 0:
            summary = (
                f"{overdue_count} deal(s) no CRM com data de fechamento vencida, "
                f"totalizando R$ {overdue_brl:,.2f}. "
                f"Revise e atualize as datas ou mova para 'perdido'."
            )
            alerts.append(Alert(
                rule_name=self.name,
                severity="warn",
                summary=summary,
                raw_data={
                    "overdue_close_brl": round(overdue_brl, 2),
                    "overdue_close_count": overdue_count,
                    "total_open_brl": round(total_open_brl, 2),
                },
                dedup_key="pipeline_health:overdue_dates",
            ))

        return alerts
