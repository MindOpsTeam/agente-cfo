#!/usr/bin/env python3
"""Dashboard metrics para skill hubspot — Agente CFO. Contrato plano canônico (FIX-KPI).
CRM: pipeline_weighted_brl + pipeline_by_stage."""
import sys, os, json
from datetime import datetime, timezone

SKILL_NAME = "hubspot"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/hubspot.env")


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


def _has_token() -> bool:
    return bool(
        os.environ.get("HUBSPOT_TOKEN") or
        os.environ.get("HUBSPOT_OAUTH_ACCESS_TOKEN") or
        os.environ.get("HUBSPOT_ACCESS_TOKEN")
    )


def get_metrics() -> dict:
    out = {
        "pipeline_weighted_brl": 0.0,
        "pipeline_by_stage": [],
        "health": {"status": "no_data", "last_sync": _now_iso()},
    }
    has_creds = _load_env()
    if not has_creds or not _has_token():
        out["health"] = {"status": "credential_invalid", "last_sync": _now_iso()}
        return out

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from hubspot_client import HubSpotClient
        client = HubSpotClient()
        degraded = False

        try:
            deals = client.list_deals(status="open", limit=200).get("items", [])
            by_stage: dict = {}
            total = 0.0
            for d in deals:
                brl = float(d.get("amount_brl", 0) or 0)
                total += brl
                stage = d.get("stage") or "—"
                agg = by_stage.setdefault(stage, {"stage": stage, "brl": 0.0, "count": 0})
                agg["brl"] += brl
                agg["count"] += 1
            out["pipeline_weighted_brl"] = round(total, 2)
            out["pipeline_by_stage"] = [
                {"stage": s["stage"], "brl": round(s["brl"], 2), "count": s["count"]}
                for s in by_stage.values()
            ]
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
