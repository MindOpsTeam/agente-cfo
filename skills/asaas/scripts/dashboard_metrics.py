#!/usr/bin/env python3
"""Dashboard metrics para skill asaas — Agente CFO. Contrato plano canônico (FIX-KPI).
Cobrança: receivables_brl = pending, overdue_total_brl = defaulted (paid_30d ignorado)."""
import sys, os, json
from datetime import datetime, timezone

SKILL_NAME = "asaas"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/asaas.env")
TOKEN_ENV = "ASAAS_API_TOKEN"


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
        "receivables_brl": 0.0,
        "overdue_total_brl": 0.0,
        "health": {"status": "no_data", "last_sync": _now_iso()},
    }
    has_creds = _load_env()
    if not has_creds or not os.environ.get(TOKEN_ENV):
        out["health"] = {"status": "credential_invalid", "last_sync": _now_iso()}
        return out

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from asaas_client import AsaasClient
        client = AsaasClient()
        degraded = False

        try:
            pending = client.list_pending(limit=200)
            out["receivables_brl"] = round(sum(float(i.get("value", 0) or 0) for i in pending.get("data", [])), 2)
        except Exception:
            degraded = True

        try:
            overdue = client.list_overdue(limit=200)
            out["overdue_total_brl"] = round(sum(float(i.get("value", 0) or 0) for i in overdue.get("data", [])), 2)
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
