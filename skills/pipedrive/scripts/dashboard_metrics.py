#!/usr/bin/env python3
"""Dashboard metrics para skill pipedrive — Agente CFO. Contrato plano canônico (FIX-KPI).
CRM — client ainda não implementado; retorna contrato plano vazio."""
import os, json
from datetime import datetime, timezone

SKILL_NAME = "pipedrive"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/pipedrive.env")
TOKEN_ENVS = ("PIPEDRIVE_API_TOKEN",)


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
        "pipeline_weighted_brl": 0.0,
        "pipeline_by_stage": [],
        "health": {"status": "no_data", "last_sync": _now_iso()},
    }
    has_creds = _load_env()
    if not has_creds or not any(os.environ.get(e) for e in TOKEN_ENVS):
        out["health"] = {"status": "credential_invalid", "last_sync": _now_iso()}
        return out
    out["health"] = {"status": "no_data", "last_sync": _now_iso()}
    return out


if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
