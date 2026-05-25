#!/usr/bin/env python3
"""Dashboard metrics para skill piperun — Agente CFO. Sprint INT-2."""
import os, json
from datetime import datetime, timezone

SKILL_NAME = "piperun"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/piperun.env")

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
    if not has_creds or not os.environ.get("PIPERUN_TOKEN"):
        base["health"] = "credential_invalid"
        base["error"] = f"Secrets não encontrados ou PIPERUN_TOKEN ausente: {SECRETS_FILE}"
        return base
    base["health"] = "no_data"
    base["metrics"] = {"pipeline_count": 0, "pipeline_weighted_brl": 0.0, "deals_won_30d_brl": 0.0}
    base["error"] = "Client Piperun não implementado. Credencial configurada."
    return base

if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
