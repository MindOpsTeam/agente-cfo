#!/usr/bin/env python3
"""Dashboard metrics para skill hubspot — Agente CFO. Sprint INT-2."""
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
    base = {
        "skill": SKILL_NAME,
        "as_of": _now_iso(),
        "metrics": {},
        "health": "no_data",
        "error": None,
    }
    has_creds = _load_env()
    if not has_creds or not _has_token():
        base["health"] = "credential_invalid"
        base["error"] = f"Secrets não encontrados ou token HubSpot ausente: {SECRETS_FILE}"
        return base

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from hubspot_client import HubSpotClient
        client = HubSpotClient()

        metrics = {}
        degraded = False

        try:
            pipeline = client.get_pipeline_summary()
            metrics["pipeline_count"] = int(pipeline.get("count", 0))
            metrics["pipeline_weighted_brl"] = round(float(pipeline.get("weighted_brl", 0.0)), 2)
        except Exception:
            metrics["pipeline_count"] = 0
            metrics["pipeline_weighted_brl"] = 0.0
            degraded = True

        try:
            won = client.get_deals_won_30d()
            metrics["deals_won_30d_brl"] = round(float(won.get("total_brl", 0.0)), 2)
        except Exception:
            metrics["deals_won_30d_brl"] = 0.0
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
