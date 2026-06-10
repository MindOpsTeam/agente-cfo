#!/usr/bin/env python3
"""
Holdprint (Holdworks) ERP Client — Agente CFO skill.

API REST documentada em https://docs.holdworks.ai
- Base URL: https://api.holdworks.ai
- Auth: header `x-api-key: <HOLDPRINT_API_KEY>` (token pessoal em Holdprint → Ajustes → API)
- Resposta padrão: {"success": true, "data": {"items": [...], "pagination": {page,limit,total,pages}}, "message": "Success"}
- Rate limit: 100 req/min por API Key.
- NÃO há sandbox: testar exige uma API key real.
- NÃO há endpoint de saldo bancário (get_balance retorna 0 + nota).

Endpoints usados:
  GET /api-key/expenses/data   → Contas a Pagar  (list_payables)
  GET /api-key/incomes/data    → Contas a Receber (list_receivables)
  GET /api-key/customers/data  → Clientes
  GET /api-key/suppliers/data  → Fornecedores
  GET /api-key/budgets/data    → Orçamentos
  GET /api-key/jobs/data       → Jobs (produção)
"""

import os
import sys
from datetime import date, timedelta
from urllib.parse import urlencode

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseERPClient, http_request, now_iso, make_list_response  # noqa: E402


class HoldprintClient(BaseERPClient):
    SKILL_NAME = "holdprint"
    BASE_URL = "https://api.holdworks.ai"

    # ── env / auth ────────────────────────────────────────────────────────────
    def _validate_env(self) -> None:
        if not os.environ.get("HOLDPRINT_API_KEY"):
            raise RuntimeError("HOLDPRINT_API_KEY não definido. Execute connect.sh.")

    def _headers(self) -> dict:
        return {
            "x-api-key": os.environ["HOLDPRINT_API_KEY"],
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None) -> dict:
        qs = ""
        if params:
            qs = "?" + urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.BASE_URL}/{path.lstrip('/')}{qs}"
        return http_request("GET", url, headers=self._headers())

    @staticmethod
    def _default_range(from_date: str | None, to_date: str | None) -> tuple[str, str]:
        """A API filtra pelo MÊS CORRENTE se nenhuma data vier. Para vencidos e
        projeção precisamos de uma janela ampla — default: -365d a +365d."""
        today = date.today()
        f = from_date or (today - timedelta(days=365)).isoformat()
        t = to_date or (today + timedelta(days=365)).isoformat()
        return f, t

    @staticmethod
    def _pagination(data: dict) -> dict:
        d = data.get("data", {}) if isinstance(data, dict) else {}
        return d.get("pagination", {}) if isinstance(d, dict) else {}

    @staticmethod
    def _records(data: dict) -> list:
        d = data.get("data", {}) if isinstance(data, dict) else {}
        items = d.get("items", []) if isinstance(d, dict) else []
        return items if isinstance(items, list) else []

    # ── leitura financeira (contrato BaseERPClient) ────────────────────────────
    def get_balance(self) -> dict:
        # Holdprint não expõe saldo bancário. Retorna 0 — a projeção de caixa
        # ainda funciona como fluxo líquido (entradas - saídas) sobre base 0.
        return {
            "balance_brl": 0.0,
            "as_of": now_iso(),
            "note": "Holdprint não expõe saldo bancário; use projeção/contas a pagar e receber.",
        }

    def list_payables(self, from_date=None, to_date=None, limit=50, page=1) -> dict:
        f, t = self._default_range(from_date, to_date)
        data = self._get("api-key/expenses/data", {
            "page": page, "limit": min(int(limit), 100),
            "start_date": f, "end_date": t,
        })
        items = []
        for r in self._records(data):
            supplier = r.get("supplier", {}) or {}
            items.append({
                "id": str(r.get("id", "")),
                "due_date": (r.get("due_date", "") or "")[:10],
                "amount_brl": float(r.get("amount", 0) or 0),
                "counterparty": supplier.get("name", "") or "",
                "status": r.get("status", "pending"),  # pending|paid|overdue|cancelled
                "category": r.get("category"),
                "raw": r,
            })
        pg = self._pagination(data)
        return make_list_response(
            items, page=int(pg.get("page", page)),
            total_pages=int(pg.get("pages", 1) or 1),
            total_count=int(pg.get("total", len(items)) or len(items)),
        )

    def list_receivables(self, from_date=None, to_date=None, limit=50, page=1) -> dict:
        f, t = self._default_range(from_date, to_date)
        data = self._get("api-key/incomes/data", {
            "page": page, "limit": min(int(limit), 100),
            "start_date": f, "end_date": t,
        })
        items = []
        for r in self._records(data):
            customer = r.get("customer", {}) or {}
            items.append({
                "id": str(r.get("id", "")),
                "due_date": (r.get("expected_date", "") or "")[:10],
                "amount_brl": float(r.get("amount", 0) or 0),
                "counterparty": customer.get("name", "") or "",
                "status": r.get("status", "pending"),  # pending|received|overdue|cancelled
                "category": r.get("revenue_center"),
                "raw": r,
            })
        pg = self._pagination(data)
        return make_list_response(
            items, page=int(pg.get("page", page)),
            total_pages=int(pg.get("pages", 1) or 1),
            total_count=int(pg.get("total", len(items)) or len(items)),
        )

    def company_info(self) -> dict:
        # Sem endpoint de empresa. Faz um GET barato (1 cliente) que serve de
        # "ping" de conectividade/validação da API key para connect.sh/doctor.sh.
        data = self._get("api-key/customers/data", {"page": 1, "limit": 1})
        pg = self._pagination(data)
        return {
            "name": "Holdprint",
            "cnpj": None,
            "segment": "grafica/impressao",
            "customers_total": int(pg.get("total", 0) or 0),
        }

    # ── leitura específica do Holdprint (gráfica) ──────────────────────────────
    def list_customers(self, limit=50, page=1) -> dict:
        data = self._get("api-key/customers/data", {"page": page, "limit": min(int(limit), 100)})
        return self._passthrough(data, page)

    def list_suppliers(self, limit=50, page=1) -> dict:
        data = self._get("api-key/suppliers/data", {"page": page, "limit": min(int(limit), 100)})
        return self._passthrough(data, page)

    def list_budgets(self, from_date=None, to_date=None, limit=50, page=1) -> dict:
        f, t = self._default_range(from_date, to_date)
        data = self._get("api-key/budgets/data", {
            "page": page, "limit": min(int(limit), 100), "start_date": f, "end_date": t,
        })
        return self._passthrough(data, page)

    def list_jobs(self, from_date=None, to_date=None, limit=50, page=1) -> dict:
        f, t = self._default_range(from_date, to_date)
        data = self._get("api-key/jobs/data", {
            "page": page, "limit": min(int(limit), 100), "start_date": f, "end_date": t,
        })
        return self._passthrough(data, page)

    def _passthrough(self, data: dict, page: int) -> dict:
        items = self._records(data)
        pg = self._pagination(data)
        return make_list_response(
            items, page=int(pg.get("page", page)),
            total_pages=int(pg.get("pages", 1) or 1),
            total_count=int(pg.get("total", len(items)) or len(items)),
        )


if __name__ == "__main__":
    HoldprintClient().run_cli()
