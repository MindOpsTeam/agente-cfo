#!/usr/bin/env python3
"""Dashboard metrics para skill supabase — Agente CFO. Contrato plano canônico (FIX-KPI).
Supabase é infraestrutura — sem métricas financeiras. Só health=ok."""
import json
from datetime import datetime, timezone

SKILL_NAME = "supabase"


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_metrics() -> dict:
    return {
        "health": {"status": "ok", "last_sync": _now_iso()},
    }


if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
