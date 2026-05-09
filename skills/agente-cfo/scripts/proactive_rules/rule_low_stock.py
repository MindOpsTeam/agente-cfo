"""
rule_low_stock — Produtos com estoque abaixo do threshold no e-commerce.

Severity: warn  (critical se estoque = 0)
Cooldown: 24h por produto (evita spam diário do mesmo produto)
Dependência: e-commerce (CFO_ECOMMERCE_NAME)

Threshold: CFO_LOW_STOCK_THRESHOLD (default 5 unidades)
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

from . import ProactiveRule, Alert

SKILLS_ROOT = Path.home() / ".openclaw" / "workspace" / "skills"
_THRESHOLD = int(os.environ.get("CFO_LOW_STOCK_THRESHOLD", "5"))
_MAX_ALERTS = int(os.environ.get("CFO_LOW_STOCK_MAX_ALERTS", "5"))  # máx alertas por ciclo


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


class RuleLowStock(ProactiveRule):
    name = "rule_low_stock"
    cooldown_hours = 24

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        ec_client = _load_ecommerce_client()
        if ec_client is None:
            return []

        try:
            resp = ec_client.get_low_stock(threshold=_THRESHOLD)
        except (NotImplementedError, Exception):
            return []

        products = resp.get("items", [])
        alerts: list[Alert] = []

        for p in products[:_MAX_ALERTS]:
            pid = p.get("id", "")
            pname = p.get("name", "?")
            qty = p.get("stock_qty", 0)
            severity = "critical" if qty == 0 else "warn"
            dedup_key = f"low_stock:{pid}"

            if qty == 0:
                summary = (
                    f"Produto '{pname}' (ID: {pid}) está com ESTOQUE ZERO. "
                    f"Reposição urgente necessária."
                )
            else:
                summary = (
                    f"Produto '{pname}' (ID: {pid}) com estoque baixo: {qty} unidade(s) "
                    f"(threshold: {_THRESHOLD}). Considere repor o estoque."
                )

            alerts.append(Alert(
                rule_name=self.name,
                severity=severity,
                summary=summary,
                raw_data={
                    "product_id": pid,
                    "product_name": pname,
                    "stock_qty": qty,
                    "threshold": _THRESHOLD,
                    "sku": p.get("sku"),
                    "price_brl": p.get("price_brl"),
                    "ecommerce_skill": os.environ.get("CFO_ECOMMERCE_NAME", ""),
                },
                dedup_key=dedup_key,
            ))

        return alerts
