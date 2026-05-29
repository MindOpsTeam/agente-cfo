#!/usr/bin/env python3
"""Dashboard metrics para skill omie — Agente CFO. Contrato plano canônico (FIX-KPI)."""
import sys, os, json
from datetime import datetime, date, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
from base import now_iso

# Importa funções reais do client Omie
sys.path.insert(0, os.path.dirname(__file__))
from omie_client import (
    unified_get_balance,
    unified_list_receivables,
    unified_list_payables,
    unified_list_overdue,
)


def _parse_due(due: str):
    """Parse due_date do Omie (dd/mm/yyyy) ou ISO (yyyy-mm-dd) -> date | None."""
    if not due:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(due[:10], fmt).date()
        except ValueError:
            continue
    return None


def _build_cash_projection(balance: float, receivables: list, payables: list, days: int = 90) -> list:
    """Saldo atual + recebíveis datados (entradas) - pagáveis datados (saídas)
    -> série diária [{date, balance_brl}] cobrindo `days` dias."""
    today = date.today()
    horizon = today + timedelta(days=days)

    # net flow por dia (chave ISO)
    flow: dict = {}
    for r in receivables:
        d = _parse_due(r.get("due_date", ""))
        if d and today <= d <= horizon and r.get("status") in ("pending", "overdue", None, ""):
            flow[d.isoformat()] = flow.get(d.isoformat(), 0.0) + float(r.get("amount_brl", 0) or 0)
    for p in payables:
        d = _parse_due(p.get("due_date", ""))
        if d and today <= d <= horizon and p.get("status") in ("pending", "overdue", None, ""):
            flow[d.isoformat()] = flow.get(d.isoformat(), 0.0) - float(p.get("amount_brl", 0) or 0)

    if not flow:
        return []

    series = []
    running = float(balance)
    for offset in range(days + 1):
        d = (today + timedelta(days=offset)).isoformat()
        running += flow.get(d, 0.0)
        series.append({"date": d, "balance_brl": round(running, 2)})
    return series


def _days_overdue(due: str) -> int:
    d = _parse_due(due)
    if not d:
        return 0
    return max(0, (date.today() - d).days)


def get_metrics() -> dict:
    health_status = "ok"
    balance_brl = 0.0
    receivables_brl = 0.0
    payables_brl = 0.0
    overdue_total_brl = 0.0
    top_debtors: list = []
    cash_projection_90d: list = []
    rec_items: list = []
    pay_items: list = []

    try:
        resp = unified_get_balance()
        balance_brl = float(resp.get("balance_brl", 0.0))
    except Exception:
        health_status = "degraded"

    try:
        resp = unified_list_receivables(limit=200)
        rec_items = resp.get("items", [])
        receivables_brl = sum(float(i.get("amount_brl", 0.0)) for i in rec_items)
    except Exception:
        health_status = "degraded"

    try:
        resp = unified_list_payables(limit=200)
        pay_items = resp.get("items", [])
        payables_brl = sum(float(i.get("amount_brl", 0.0)) for i in pay_items)
    except Exception:
        health_status = "degraded"

    try:
        resp = unified_list_overdue()
        items = resp.get("items", [])
        overdue_total_brl = sum(float(i.get("amount_brl", 0.0)) for i in items)
        ranked = sorted(items, key=lambda x: -float(x.get("amount_brl", 0.0)))[:10]
        top_debtors = [
            {
                "name": i.get("counterparty") or i.get("name") or "—",
                "brl": round(float(i.get("amount_brl", 0.0)), 2),
                "days_overdue": _days_overdue(i.get("due_date", "")),
            }
            for i in ranked
        ]
    except Exception:
        health_status = "degraded"

    try:
        cash_projection_90d = _build_cash_projection(balance_brl, rec_items, pay_items, days=90)
    except Exception:
        cash_projection_90d = []

    return {
        "balance_brl": round(balance_brl, 2),
        "receivables_brl": round(receivables_brl, 2),
        "payables_brl": round(payables_brl, 2),
        "overdue_total_brl": round(overdue_total_brl, 2),
        "top_debtors": top_debtors,
        "cash_projection_90d": cash_projection_90d,
        "health": {"status": health_status, "last_sync": now_iso()},
    }


if __name__ == '__main__':
    print(json.dumps(get_metrics(), default=str))
