"""
rule_deal_stale — Deal aberto há mais de 30 dias sem atualização.

Severity: info
Cooldown: 168h (1 semana) por deal
Dependência: CRM

Retorna [] silenciosamente se CRM não configurado.

Lógica:
  - Lista todos os deals com status "open"
  - Detecta deals que não têm "updated_at" ou cujo updated_at é > STALE_DAYS atrás
  - Fallback: se não houver updated_at, usa created_at ou expected_close_date
  - Limit: máx 5 alertas por ciclo (para não spam em pipelines grandes)
"""
from __future__ import annotations
import os
from datetime import date, timedelta
from . import ProactiveRule, Alert

STALE_DAYS = int(os.environ.get("CFO_DEAL_STALE_DAYS", "30"))
MAX_ALERTS_PER_CYCLE = 5


class RuleDealStale(ProactiveRule):
    name = "rule_deal_stale"
    cooldown_hours = 168  # 1 semana por deal

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if crm_client is None:
            return []

        today = date.today()
        stale_cutoff = (today - timedelta(days=STALE_DAYS)).isoformat()

        try:
            resp = crm_client.list_deals(status="open", limit=200)
        except (NotImplementedError, Exception):
            return []

        alerts = []
        for deal in resp.get("items", []):
            deal_id = deal.get("id", "")
            title = deal.get("title", "deal sem título")
            stage = deal.get("stage", "desconhecido")

            # Determinar a data de referência para "último update"
            raw = deal.get("raw", {})
            last_activity = (
                raw.get("updated_at") or raw.get("last_activity_date")
                or raw.get("lastActivityDate") or raw.get("last_modified")
                or deal.get("expected_close_date")
                or raw.get("created_at") or raw.get("createdAt")
                or ""
            )

            if not last_activity:
                # Sem data nenhuma — considera stale por definição
                days_stale = STALE_DAYS
            else:
                try:
                    ref_date = date.fromisoformat(str(last_activity)[:10])
                    days_stale = (today - ref_date).days
                except ValueError:
                    days_stale = STALE_DAYS

            if days_stale < STALE_DAYS:
                continue

            amount = deal.get("amount_brl")
            amount_str = f"R$ {amount:,.2f}" if amount else "valor não informado"
            dedup_key = f"deal_stale:{deal_id}"

            summary = (
                f"Deal \"{title}\" parado há {days_stale} dias "
                f"(stage: {stage}, {amount_str}). "
                f"Considere follow-up ou atualização de status."
            )

            alerts.append(Alert(
                rule_name=self.name,
                severity="info",
                summary=summary,
                raw_data={
                    "deal_id": deal_id,
                    "title": title,
                    "stage": stage,
                    "amount_brl": amount,
                    "days_stale": days_stale,
                    "last_activity": last_activity,
                },
                dedup_key=dedup_key,
            ))

            if len(alerts) >= MAX_ALERTS_PER_CYCLE:
                break

        return alerts
