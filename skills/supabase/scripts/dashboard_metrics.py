#!/usr/bin/env python3
"""Dashboard metrics para skill supabase — Agente CFO. Sprint INT-2.
Supabase é infraestrutura — sem métricas financeiras.
Sempre retorna health=ok para indicar que o backend está operacional.
"""
import os, json
from datetime import datetime, timezone

SKILL_NAME = "supabase"

def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def get_metrics() -> dict:
    return {
        "skill": SKILL_NAME,
        "as_of": _now_iso(),
        "metrics": {},
        "health": "ok",
        "error": None,
    }

if __name__ == '__main__':
    print(json.dumps(get_metrics(), ensure_ascii=False, default=str))
