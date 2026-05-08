"""
rule_pipeline_drop — Total "won" no mês corrente < 50% do mês anterior na mesma data proporcional.

Severity: warn
Cooldown: 168h (1 semana, global)
Dependência: CRM

Lógica:
  - Lista deals won em ambos os meses
  - Corrige o mês anterior proporcionalmente pelo dia atual
    Ex: hoje = dia 10 de maio → mes_anterior_proratado = total_abril × (10/30)
  - Se won_mes_atual < won_mes_anterior_proratado × 0.5 → dispara
  - Só dispara se houver pelo menos R$ 1.000 em won histórico (evita falsos positivos
    em empresas novas com pipeline zerado)
"""
from __future__ import annotations
import os
from datetime import date
from calendar import monthrange
from . import ProactiveRule, Alert

PIPELINE_DROP_THRESHOLD = float(os.environ.get("CFO_PIPELINE_DROP_THRESHOLD_PCT", "50")) / 100.0
MIN_HISTORICAL_WON_BRL = float(os.environ.get("CFO_PIPELINE_DROP_MIN_BRL", "1000"))


class RulePipelineDrop(ProactiveRule):
    name = "rule_pipeline_drop"
    cooldown_hours = 168  # 1 semana

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if crm_client is None:
            return []

        today = date.today()

        # Mês atual: 1º ao hoje
        cur_start = today.replace(day=1).isoformat()
        cur_end = today.isoformat()

        # Mês anterior: 1º ao último dia
        if today.month == 1:
            prev_year, prev_month = today.year - 1, 12
        else:
            prev_year, prev_month = today.year, today.month - 1
        prev_days = monthrange(prev_year, prev_month)[1]
        prev_start = date(prev_year, prev_month, 1).isoformat()
        prev_end = date(prev_year, prev_month, prev_days).isoformat()

        try:
            cur_resp = crm_client.list_deals(status="won", limit=500)
        except (NotImplementedError, Exception):
            return []

        try:
            prev_resp = crm_client.list_deals(status="won", limit=500)
        except (NotImplementedError, Exception):
            return []

        def _total_won_in_range(deals_resp: dict, start: str, end: str) -> float:
            total = 0.0
            for d in deals_resp.get("items", []):
                raw = d.get("raw", {})
                close_date = (
                    raw.get("close_date") or raw.get("closeDate")
                    or raw.get("closed_at") or raw.get("won_at")
                    or d.get("expected_close_date") or ""
                )
                if not close_date:
                    continue
                close_str = str(close_date)[:10]
                if start <= close_str <= end:
                    total += float(d.get("amount_brl") or 0.0)
            return total

        won_cur = _total_won_in_range(cur_resp, cur_start, cur_end)
        won_prev_full = _total_won_in_range(prev_resp, prev_start, prev_end)

        if won_prev_full < MIN_HISTORICAL_WON_BRL:
            # Pipeline histórico muito pequeno — evita falsos positivos
            return []

        # Proporcionar mês anterior até o mesmo dia do mês
        day_of_month = today.day
        won_prev_prorated = won_prev_full * (day_of_month / prev_days)

        if won_cur >= won_prev_prorated * PIPELINE_DROP_THRESHOLD:
            return []

        drop_pct = round((1 - (won_cur / won_prev_prorated)) * 100, 1) if won_prev_prorated > 0 else 100.0

        summary = (
            f"Vendas fechadas este mês até hoje: R$ {won_cur:,.2f} "
            f"vs R$ {won_prev_prorated:,.2f} no mesmo período do mês passado "
            f"(queda de {drop_pct}%). "
            f"Mês anterior completo: R$ {won_prev_full:,.2f}."
        )

        return [Alert(
            rule_name=self.name,
            severity="warn",
            summary=summary,
            raw_data={
                "won_current_month_brl": round(won_cur, 2),
                "won_prev_month_prorated_brl": round(won_prev_prorated, 2),
                "won_prev_month_full_brl": round(won_prev_full, 2),
                "drop_pct": drop_pct,
                "threshold_pct": round(PIPELINE_DROP_THRESHOLD * 100, 1),
                "day_of_month": day_of_month,
            },
            dedup_key="pipeline_drop:global",
        )]
