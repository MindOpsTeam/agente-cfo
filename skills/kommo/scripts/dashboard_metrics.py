#!/usr/bin/env python3
"""Dashboard metrics para skill kommo — Agente CFO. Sprint INT-2.
Kommo (ex-amoCRM) — CRM de funil de vendas.
"""
import os, json
from datetime import datetime, timezone

SKILL_NAME = "kommo"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/kommo.env")

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
    if not has_creds or not os.environ.get("KOMMO_ACCESS_TOKEN"):
        base["health"] = "credential_invalid"
        base["error"] = f"Secrets não encontrados ou KOMMO_ACCESS_TOKEN ausente: {SECRETS_FILE}"
        return base
    # CRM — client não implementado; cred presente
    base["health"] = "no_data"
    base["metrics"] = {"pipeline_count": 0, "pipeline_weighted_brl": 0.0, "deals_won_30d_brl": 0.0}
    base["error"] = "Client Kommo não implementado. Credencial configurada."
    return base

if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
