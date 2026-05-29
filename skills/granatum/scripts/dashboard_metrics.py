#!/usr/bin/env python3
"""Dashboard metrics para skill granatum — Agente CFO. Contrato plano canônico (FIX-KPI).
ERP financeiro — client ainda não implementado; retorna contrato plano vazio."""
import os, json
from datetime import datetime, timezone

SKILL_NAME = "granatum"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/granatum.env")
TOKEN_ENVS = ("GRANATUM_TOKEN",)


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
        "balance_brl": 0.0,
        "receivables_brl": 0.0,
        "payables_brl": 0.0,
        "overdue_total_brl": 0.0,
        "top_debtors": [],
        "cash_projection_90d": [],
        "health": {"status": "no_data", "last_sync": _now_iso()},
    }
    has_creds = _load_env()
    if not has_creds or not any(os.environ.get(e) for e in TOKEN_ENVS):
        out["health"] = {"status": "credential_invalid", "last_sync": _now_iso()}
        return out
    # Credencial presente, client não implementado ainda
    out["health"] = {"status": "no_data", "last_sync": _now_iso()}
    return out


if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
