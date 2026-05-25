#!/usr/bin/env python3
"""Dashboard metrics para skill asaas — Agente CFO. Sprint INT-2."""
import sys, os, json
from datetime import datetime, timezone

SKILL_NAME = "asaas"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/asaas.env")

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
    if not has_creds or not os.environ.get("ASAAS_API_TOKEN"):
        base["health"] = "credential_invalid"
        base["error"] = f"Secrets não encontrados ou ASAAS_API_TOKEN ausente: {SECRETS_FILE}"
        return base

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from asaas_client import AsaasClient
        client = AsaasClient()

        metrics = {}
        degraded = False

        try:
            pending = client.list_pending(limit=200)
            metrics["pending_brl"] = round(sum(float(i.get("value", 0)) for i in pending.get("data", [])), 2)
        except Exception:
            metrics["pending_brl"] = 0.0
            degraded = True

        try:
            paid = client.list_paid_30d(limit=200)
            metrics["paid_30d_brl"] = round(sum(float(i.get("value", 0)) for i in paid.get("data", [])), 2)
        except Exception:
            metrics["paid_30d_brl"] = 0.0
            degraded = True

        try:
            overdue = client.list_overdue(limit=200)
            metrics["defaulted_brl"] = round(sum(float(i.get("value", 0)) for i in overdue.get("data", [])), 2)
        except Exception:
            metrics["defaulted_brl"] = 0.0
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
