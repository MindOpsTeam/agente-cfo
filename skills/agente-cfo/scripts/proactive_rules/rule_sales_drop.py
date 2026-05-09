"""
rule_sales_drop — Vendas do dia abaixo de 50% da média dos últimos 7 dias.

Severity: warn
Cooldown: 24h (global — 1 alerta por dia)
Dependência: e-commerce (CFO_ECOMMERCE_NAME)

Lógica:
  - Coleta pedidos paid/shipped/delivered nos últimos 8 dias
  - Calcula média diária dos últimos 7 dias (D-7 a D-1)
  - Compara com total do dia atual (D-0)
  - Se dia atual < média × CFO_SALES_DROP_THRESHOLD (default 0.5) → dispara
  - Só dispara se média_7d > 0 (evita falsos positivos em lojas novas)
  - Só dispara após às 14:00 (dá tempo do dia ter vendas)

Env:
  CFO_SALES_DROP_THRESHOLD — fração (default 0.5 = 50% da média)
"""
from __future__ import annotations
import os
import sys
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

from . import ProactiveRule, Alert

SKILLS_ROOT = Path.home() / ".openclaw" / "workspace" / "skills"
_THRESHOLD = float(os.environ.get("CFO_SALES_DROP_THRESHOLD", "0.5"))
_MIN_HOUR = int(os.environ.get("CFO_SALES_DROP_MIN_HOUR", "14"))  # só dispara após X hora


def _load_ecommerce_client():
    import importlib
    ecom_name = os.environ.get("CFO_ECOMMERCE_NAME", "nenhum")
    if ecom_name == "nenhum":
        return None
    skill_dir = SKILLS_ROOT / ecom_name / "scripts"
    if not skill_dir.exists():
        return None
    for p in [str(skill_dir), str(SKILLS_ROOT / "_lib")]:
        if p not in sys.path:
            sys.path.insert(0, p)
    module_name = ecom_name.replace("-", "_") + "_client"
    class_name = ecom_name.replace("-", "_").replace("_", " ").title().replace(" ", "") + "Client"
    try:
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        return cls()
    except Exception:
        return None


class RuleSalesDrop(ProactiveRule):
    name = "rule_sales_drop"
    cooldown_hours = 24

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        # Só avalia após _MIN_HOUR local
        now_hour = datetime.now().hour
        if now_hour < _MIN_HOUR:
            return []

        ec_client = _load_ecommerce_client()
        if ec_client is None:
            return []

        try:
            metrics = ec_client.get_sales_metrics(days=8)
        except (NotImplementedError, Exception):
            return []

        # Precisa de get_sales_metrics detalhado por dia — fallback: usa list_orders
        # Se get_sales_metrics retorna apenas totais, usamos a heurística:
        # total 8 dias → média 7 dias = (total - hoje_est) / 7
        # Tentar list_orders com since=D-8 para breakdown por dia
        today = date.today()
        d7_ago = (today - timedelta(days=7)).isoformat()

        try:
            orders_resp = ec_client.list_orders(status="all", limit=500, since=d7_ago)
        except (NotImplementedError, Exception):
            return []

        orders = orders_resp.get("items", [])
        paid_orders = [
            o for o in orders
            if o.get("status") in ("paid", "shipped", "delivered")
        ]

        if not paid_orders:
            return []

        today_str = today.isoformat()
        today_rev = sum(
            float(o.get("amount_brl", 0.0)) for o in paid_orders
            if (o.get("created_at") or "")[:10] == today_str
        )
        prev_7d_rev = sum(
            float(o.get("amount_brl", 0.0)) for o in paid_orders
            if (o.get("created_at") or "")[:10] < today_str
        )
        prev_days_with_data = len(set(
            o.get("created_at", "")[:10] for o in paid_orders
            if (o.get("created_at") or "")[:10] < today_str
        ))

        if prev_days_with_data == 0:
            return []

        avg_7d = prev_7d_rev / prev_days_with_data

        if avg_7d <= 0:
            return []

        if today_rev >= avg_7d * _THRESHOLD:
            return []

        drop_pct = round((1 - today_rev / avg_7d) * 100, 1)
        today_orders = sum(1 for o in paid_orders if (o.get("created_at") or "")[:10] == today_str)

        summary = (
            f"Vendas de hoje até agora: R$ {today_rev:,.2f} ({today_orders} pedido(s)) — "
            f"queda de {drop_pct}% em relação à média dos últimos {prev_days_with_data} dias "
            f"(~R$ {avg_7d:,.2f}/dia). Hora atual: {now_hour}h."
        )

        return [Alert(
            rule_name=self.name,
            severity="warn",
            summary=summary,
            raw_data={
                "today_revenue_brl": round(today_rev, 2),
                "today_order_count": today_orders,
                "avg_7d_daily_brl": round(avg_7d, 2),
                "drop_pct": drop_pct,
                "threshold_pct": round(_THRESHOLD * 100, 1),
                "prev_days_analyzed": prev_days_with_data,
                "ecommerce_skill": os.environ.get("CFO_ECOMMERCE_NAME", ""),
            },
            dedup_key="sales_drop:global",
        )]
