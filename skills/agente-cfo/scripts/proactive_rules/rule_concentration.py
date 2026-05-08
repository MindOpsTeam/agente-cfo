"""
rule_concentration — 1 cliente representa >40% do total a receber.

Severity: warn
Cooldown: 168h (1 semana) por cliente
Dependência: ERP

Lógica:
  - Busca todos os recebíveis pendentes (status pending/overdue)
  - Agrupa por counterparty
  - Dispara se algum cliente tem share > CFO_CONCENTRATION_THRESHOLD (default 40%)
"""
from __future__ import annotations
import os
from collections import defaultdict
from . import ProactiveRule, Alert

CONCENTRATION_THRESHOLD = float(os.environ.get("CFO_CONCENTRATION_THRESHOLD_PCT", "40")) / 100.0


class RuleConcentration(ProactiveRule):
    name = "rule_concentration"
    cooldown_hours = 168  # 1 semana por cliente

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if erp_client is None:
            return []

        try:
            resp = erp_client.list_receivables(limit=200)
        except (NotImplementedError, Exception):
            return []

        items = [
            i for i in resp.get("items", [])
            if i.get("status") in ("pending", "overdue")
        ]
        if not items:
            return []

        total = sum(float(i.get("amount_brl", 0.0)) for i in items)
        if total <= 0:
            return []

        by_client: dict[str, float] = defaultdict(float)
        for i in items:
            cp = i.get("counterparty", "desconhecido") or "desconhecido"
            by_client[cp] += float(i.get("amount_brl", 0.0))

        alerts = []
        for client, amount in by_client.items():
            share = amount / total
            if share < CONCENTRATION_THRESHOLD:
                continue

            pct = round(share * 100, 1)
            dedup_key = f"concentration:{client.lower().replace(' ', '_')[:40]}"

            summary = (
                f"Cliente {client!r} representa {pct}% do total a receber "
                f"(R$ {amount:,.2f} de R$ {total:,.2f}). "
                f"Risco de concentração — um atraso deles impacta o caixa diretamente."
            )

            alerts.append(Alert(
                rule_name=self.name,
                severity="warn",
                summary=summary,
                raw_data={
                    "client": client,
                    "amount_brl": round(amount, 2),
                    "total_receivables_brl": round(total, 2),
                    "share_pct": pct,
                    "threshold_pct": round(CONCENTRATION_THRESHOLD * 100, 1),
                },
                dedup_key=dedup_key,
            ))

        return alerts
