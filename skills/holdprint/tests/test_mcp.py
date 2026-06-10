#!/usr/bin/env python3
"""
Testes da skill holdprint — mockam a camada HTTP com os payloads de exemplo da
doc oficial (https://docs.holdworks.ai), já que não há sandbox.
Roda: python3 tests/test_mcp.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))

os.environ["HOLDPRINT_API_KEY"] = "test-key"

import base  # noqa: E402
import holdprint_client as hc  # noqa: E402

# ── Payloads de exemplo (verbatim da doc) ───────────────────────────────────────
EXPENSES = {
    "success": True,
    "data": {
        "items": [
            {"id": 1001, "description": "Aluguel", "amount": 3500.00, "due_date": "2025-02-05",
             "payment_date": "2025-02-05", "status": "paid", "supplier": {"id": 55, "name": "Fornecedor XYZ"},
             "category": "equipment_rental", "cost_center": "production"},
            {"id": 1002, "description": "Papel", "amount": 1250.00, "due_date": "2025-02-15",
             "payment_date": None, "status": "pending", "supplier": {"id": 56, "name": "Papelaria Central"},
             "category": "paper_supplies", "cost_center": "production"},
        ],
        "pagination": {"page": 1, "limit": 50, "total": 120, "pages": 3},
    },
    "message": "Success",
}
INCOMES = {
    "success": True,
    "data": {
        "items": [
            {"id": 2001, "description": "Job #5678", "amount": 12500.00, "expected_date": "2025-02-15",
             "received_date": "2025-02-14", "status": "received", "customer": {"id": 789, "name": "Empresa Exemplo LTDA"},
             "revenue_center": "sales", "job_id": 5678},
            {"id": 2002, "description": "Job #5680", "amount": 8750.00, "expected_date": "2025-02-20",
             "received_date": None, "status": "pending", "customer": {"id": 790, "name": "Editora ABC"},
             "revenue_center": "sales", "job_id": 5680},
        ],
        "pagination": {"page": 1, "limit": 50, "total": 95, "pages": 2},
    },
    "message": "Success",
}
CUSTOMERS = {"success": True, "data": {"items": [{"id": 1}], "pagination": {"page": 1, "total": 42, "pages": 1}}, "message": "Success"}


def _fake_http(method, url, **kwargs):
    if "expenses" in url:
        return EXPENSES
    if "incomes" in url:
        return INCOMES
    if "customers" in url:
        return CUSTOMERS
    return {"success": True, "data": {"items": [], "pagination": {"page": 1, "total": 0, "pages": 1}}}


def main():
    # injeta o mock no módulo base (de onde o client importa http_request)
    hc.http_request = _fake_http
    base.http_request = _fake_http
    c = hc.HoldprintClient()
    passed = 0

    def check(label, cond):
        nonlocal passed
        assert cond, f"FALHOU: {label}"
        print(f"  ✅ {label}")
        passed += 1

    # auth/header
    check("header x-api-key presente", c._headers().get("x-api-key") == "test-key")

    # list_payables → contrato make_payable_item
    pay = c.list_payables(from_date="2025-01-01", to_date="2025-12-31")
    check("payables: 2 itens", len(pay["items"]) == 2)
    check("payables: total_pages=3", pay["total_pages"] == 3)
    p0 = pay["items"][0]
    check("payable.amount_brl=3500", p0["amount_brl"] == 3500.0)
    check("payable.due_date=2025-02-05", p0["due_date"] == "2025-02-05")
    check("payable.counterparty=Fornecedor XYZ", p0["counterparty"] == "Fornecedor XYZ")
    check("payable.status=paid", p0["status"] == "paid")

    # list_receivables → contrato make_receivable_item (due_date = expected_date)
    rec = c.list_receivables()
    r0 = rec["items"][0]
    check("receivable.due_date=expected_date", r0["due_date"] == "2025-02-15")
    check("receivable.counterparty=Empresa Exemplo LTDA", r0["counterparty"] == "Empresa Exemplo LTDA")
    check("receivable.category=revenue_center(sales)", r0["category"] == "sales")

    # get_balance (sem endpoint)
    bal = c.get_balance()
    check("balance_brl=0 + note", bal["balance_brl"] == 0.0 and "note" in bal)

    # company_info usa /customers (ping)
    info = c.company_info()
    check("company_info.customers_total=42", info["customers_total"] == 42)

    # dashboard_metrics roda end-to-end com os mocks
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import dashboard_metrics as dm
    dm.os.environ["HOLDPRINT_API_KEY"] = "test-key"
    # força o client mockado dentro do dashboard
    import importlib
    importlib.reload(dm)
    dm._load_env = lambda: True
    m = dm.get_metrics()
    check("dashboard tem chaves canônicas", all(k in m for k in
          ("balance_brl", "receivables_brl", "payables_brl", "overdue_total_brl", "top_debtors", "health")))

    print(f"\n✅ {passed} checks OK")


if __name__ == "__main__":
    main()
