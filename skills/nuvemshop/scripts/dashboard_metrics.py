#!/usr/bin/env python3
"""Dashboard metrics para skill nuvemshop — Agente CFO. Sprint INT-2."""
import sys, os, json
from datetime import datetime, timezone

SKILL_NAME = "nuvemshop"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/nuvemshop.env")

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
    base = {
        "skill": SKILL_NAME,
        "as_of": _now_iso(),
        "metrics": {},
        "health": "no_data",
        "error": None,
    }
    has_creds = _load_env()
    if not has_creds or not os.environ.get("NS_ACCESS_TOKEN"):
        base["health"] = "credential_invalid"
        base["error"] = f"Secrets não encontrados ou NS_ACCESS_TOKEN ausente: {SECRETS_FILE}"
        return base

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from nuvemshop_client import NuvemshopClient
        client = NuvemshopClient()

        metrics = {}
        degraded = False

        try:
            orders = client.list_orders_30d(limit=200)
            items = orders if isinstance(orders, list) else orders.get("results", [])
            revenue = sum(float(o.get("total", 0)) for o in items)
            metrics["revenue_30d_brl"] = round(revenue, 2)
            metrics["orders_30d_count"] = len(items)
            metrics["ticket_avg_brl"] = round(revenue / len(items), 2) if items else 0.0
        except Exception:
            metrics["revenue_30d_brl"] = 0.0
            metrics["orders_30d_count"] = 0
            metrics["ticket_avg_brl"] = 0.0
            degraded = True

        base["metrics"] = metrics
        base["health"] = "degraded" if degraded else "ok"

    except ImportError as e:
        base["health"] = "no_data"
        base["error"] = f"Client não disponível: {e}"
    except Exception as e:
        err_str = str(e)
        if any(k in err_str.lower() for k in ("401", "403", "invalid", "token", "unauthorized")):
            base["health"] = "credential_invalid"
        else:
            base["health"] = "error"
        base["error"] = err_str[:300]
    return base

if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
