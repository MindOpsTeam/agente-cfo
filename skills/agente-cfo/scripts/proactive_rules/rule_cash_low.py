"""
rule_cash_low — Caixa projetado nos próximos 7 dias abaixo do threshold.

Severity: warn  (critical se < 50% do threshold)
Cooldown: 24h (global)
Dependência: ERP

Lógica de projeção:
  saldo_atual (get_balance)
  + total a receber nos próximos 7 dias (list_receivables próximos 7 dias)
  - total a pagar nos próximos 7 dias (list_payables próximos 7 dias)
  = saldo_projetado

Threshold: LLM_BUDGET_BRL * 5 (env var) como heurística inicial.
Futuro (Sprint 7): cliente configura no painel.
"""
from __future__ import annotations
import os
from datetime import date, timedelta
from . import ProactiveRule, Alert


def _cash_threshold() -> float:
    budget = float(os.environ.get("LLM_BUDGET_BRL", "50"))
    multiplier = float(os.environ.get("CFO_CASH_THRESHOLD_MULTIPLIER", "5"))
    override = os.environ.get("CFO_CASH_LOW_THRESHOLD_BRL")
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    return budget * multiplier


class RuleCashLow(ProactiveRule):
    name = "rule_cash_low"
    cooldown_hours = 24

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if erp_client is None:
            return []

        today = date.today()
        in_7_days = (today + timedelta(days=7)).isoformat()
        today_str = today.isoformat()

        try:
            balance_resp = erp_client.get_balance()
        except (NotImplementedError, Exception):
            return []

        balance = float(balance_resp.get("balance_brl", 0.0))

        try:
            receivables_resp = erp_client.list_receivables(
                from_date=today_str, to_date=in_7_days, limit=200
            )
            incoming = sum(
                float(i.get("amount_brl", 0.0))
                for i in receivables_resp.get("items", [])
                if i.get("status") in ("pending", "overdue")
            )
        except (NotImplementedError, Exception):
            incoming = 0.0

        try:
            payables_resp = erp_client.list_payables(
                from_date=today_str, to_date=in_7_days, limit=200
            )
            outgoing = sum(
                float(i.get("amount_brl", 0.0))
                for i in payables_resp.get("items", [])
                if i.get("status") in ("pending", "overdue")
            )
            # Coleta as contas que vencem nos próximos 7 dias para o summary
            upcoming_bills = sorted(
                [
                    i for i in payables_resp.get("items", [])
                    if i.get("status") in ("pending", "overdue")
                ],
                key=lambda x: x.get("due_date", ""),
            )[:3]
        except (NotImplementedError, Exception):
            outgoing = 0.0
            upcoming_bills = []

        projected = balance + incoming - outgoing
        threshold = _cash_threshold()

        if projected >= threshold:
            return []

        severity = "critical" if projected < threshold * 0.5 else "warn"

        bills_str = ""
        if upcoming_bills:
            parts = [
                f"{b.get('counterparty','?')} R$ {float(b.get('amount_brl',0)):,.0f} ({b.get('due_date','')})"
                for b in upcoming_bills[:2]
            ]
            bills_str = f" Principais vencimentos: {'; '.join(parts)}."

        summary = (
            f"Caixa projetado em 7 dias: R$ {projected:,.2f} "
            f"(threshold R$ {threshold:,.2f}).{bills_str} "
            f"Saldo atual: R$ {balance:,.2f} | "
            f"+recebimentos: R$ {incoming:,.2f} | "
            f"-pagamentos: R$ {outgoing:,.2f}."
        )

        return [Alert(
            rule_name=self.name,
            severity=severity,
            summary=summary,
            raw_data={
                "balance_brl": balance,
                "incoming_7d_brl": round(incoming, 2),
                "outgoing_7d_brl": round(outgoing, 2),
                "projected_brl": round(projected, 2),
                "threshold_brl": round(threshold, 2),
                "upcoming_bills": upcoming_bills[:5],
            },
            dedup_key="cash_low:global",
        )]
