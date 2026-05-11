#!/usr/bin/env python3
"""Dashboard metrics para skill omie — Agente CFO."""
import sys, os, json

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


def get_metrics() -> dict:
    health_status = "ok"
    balance_brl = 0.0
    receivables_brl = 0.0
    payables_brl = 0.0
    overdue_total_brl = 0.0
    top_debtors: list[dict] = []

    try:
        resp = unified_get_balance()
        balance_brl = float(resp.get("balance_brl", 0.0))
    except Exception:
        health_status = "degraded"

    try:
        resp = unified_list_receivables(limit=200)
        receivables_brl = sum(float(i.get("amount_brl", 0.0)) for i in resp.get("items", []))
    except Exception:
        health_status = "degraded"

    try:
        resp = unified_list_payables(limit=200)
        payables_brl = sum(float(i.get("amount_brl", 0.0)) for i in resp.get("items", []))
    except Exception:
        health_status = "degraded"

    try:
        resp = unified_list_overdue()
        items = resp.get("items", [])
        overdue_total_brl = sum(float(i.get("amount_brl", 0.0)) for i in items)
        top_debtors = sorted(items, key=lambda x: -float(x.get("amount_brl", 0.0)))[:10]
    except Exception:
        health_status = "degraded"

    return {
        "balance_brl": round(balance_brl, 2),
        "receivables_brl": round(receivables_brl, 2),
        "payables_brl": round(payables_brl, 2),
        "overdue_total_brl": round(overdue_total_brl, 2),
        "top_debtors": top_debtors,
        "cash_projection_90d": [],
        "health": {"status": health_status, "last_sync": now_iso()},
    }


if __name__ == '__main__':
    print(json.dumps(get_metrics(), default=str))
