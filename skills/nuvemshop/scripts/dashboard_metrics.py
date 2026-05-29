#!/usr/bin/env python3
"""Dashboard metrics para skill nuvemshop — Agente CFO. Contrato plano canônico (FIX-KPI).
E-commerce: ecommerce_revenue_month_brl."""
import sys, os, json
from datetime import datetime, timezone

SKILL_NAME = "nuvemshop"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/nuvemshop.env")
TOKEN_ENV = "NS_ACCESS_TOKEN"


def _load_env() -> bool:
    if not os.path.exists(SECRETS_FILE):
        return False
    try:
        with open(SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, _, v = line.partition('=')
                    os.environ.setdefault(k.strip(), v.strip())
        return True
    except Exception:
        return False


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_metrics() -> dict:
    out = {
        "ecommerce_revenue_month_brl": 0.0,
        "health": {"status": "no_data", "last_sync": _now_iso()},
    }
    has_creds = _load_env()
    if not has_creds or not os.environ.get(TOKEN_ENV):
        out["health"] = {"status": "credential_invalid", "last_sync": _now_iso()}
        return out

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from nuvemshop_client import NuvemshopClient
        client = NuvemshopClient()
        degraded = False

        try:
            orders = client.list_orders_30d(limit=200)
            items = orders if isinstance(orders, list) else orders.get("results", [])
            out["ecommerce_revenue_month_brl"] = round(sum(float(o.get("total", 0) or 0) for o in items), 2)
        except Exception:
            degraded = True

        out["health"] = {"status": "degraded" if degraded else "ok", "last_sync": _now_iso()}

    except ImportError:
        out["health"] = {"status": "no_data", "last_sync": _now_iso()}
    except Exception as e:
        err = str(e).lower()
        status = "credential_invalid" if any(k in err for k in ("401", "403", "invalid", "token", "unauthorized")) else "error"
        out["health"] = {"status": status, "last_sync": _now_iso()}
    return out


if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
