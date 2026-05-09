"""
rule_unfulfilled_orders — Pedidos pagos mas não enviados há mais de N dias.

Severity: warn (critical se > 5 dias)
Cooldown: 12h (global)
Dependência: e-commerce (CFO_ECOMMERCE_NAME)

Trigger: pedido com status=paid E sem tracking_code E created_at há > CFO_UNFULFILLED_DAYS (default 2)
"""
from __future__ import annotations
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from . import ProactiveRule, Alert

SKILLS_ROOT = Path.home() / ".openclaw" / "workspace" / "skills"
_MIN_DAYS = int(os.environ.get("CFO_UNFULFILLED_DAYS", "2"))
_MAX_SHOW = int(os.environ.get("CFO_UNFULFILLED_MAX_SHOW", "5"))


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


class RuleUnfulfilledOrders(ProactiveRule):
    name = "rule_unfulfilled_orders"
    cooldown_hours = 12

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        ec_client = _load_ecommerce_client()
        if ec_client is None:
            return []

        cutoff = (date.today() - timedelta(days=_MIN_DAYS)).isoformat()
        try:
            orders_resp = ec_client.list_orders(
                status="paid", limit=200,
                since=(date.today() - timedelta(days=30)).isoformat()
            )
        except (NotImplementedError, Exception):
            return []

        orders = orders_resp.get("items", [])
        unfulfilled = [
            o for o in orders
            if o.get("status") == "paid"
            and not o.get("tracking_code")
            and (o.get("created_at") or "9999")[:10] <= cutoff
        ]

        if not unfulfilled:
            return []

        # Ordenar por mais antigo primeiro
        unfulfilled.sort(key=lambda x: x.get("created_at", ""))

        count = len(unfulfilled)
        total_rev = sum(float(o.get("amount_brl", 0.0)) for o in unfulfilled)

        oldest = unfulfilled[0]
        oldest_date = (oldest.get("created_at") or "")[:10]
        try:
            days_old = (date.today() - date.fromisoformat(oldest_date)).days
        except Exception:
            days_old = 0

        severity = "critical" if days_old > 5 else "warn"

        # Lista dos mais antigos para o summary
        examples = []
        for o in unfulfilled[:_MAX_SHOW]:
            odate = (o.get("created_at") or "")[:10]
            try:
                od = (date.today() - date.fromisoformat(odate)).days
            except Exception:
                od = 0
            examples.append(
                f"#{o.get('id', '?')} {o.get('customer_name', '?')} "
                f"R$ {float(o.get('amount_brl', 0)):,.0f} ({od}d)"
            )

        extras = count - len(examples)
        summary_list = "; ".join(examples)
        if extras > 0:
            summary_list += f" + {extras} outros"

        summary = (
            f"{count} pedido(s) pago(s) sem envio há mais de {_MIN_DAYS} dias "
            f"(total R$ {total_rev:,.2f}). Mais antigo: {days_old} dias. "
            f"Pedidos: {summary_list}."
        )

        return [Alert(
            rule_name=self.name,
            severity=severity,
            summary=summary,
            raw_data={
                "unfulfilled_count": count,
                "total_revenue_brl": round(total_rev, 2),
                "oldest_order_days": days_old,
                "min_days_threshold": _MIN_DAYS,
                "orders": [
                    {"id": o.get("id"), "customer": o.get("customer_name"),
                     "amount_brl": o.get("amount_brl"), "created_at": o.get("created_at")}
                    for o in unfulfilled[:10]
                ],
                "ecommerce_skill": os.environ.get("CFO_ECOMMERCE_NAME", ""),
            },
            dedup_key="unfulfilled_orders:global",
        )]
