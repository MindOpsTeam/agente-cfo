#!/usr/bin/env python3
"""Dashboard metrics para skill contaazul — Agente CFO. Contrato plano canônico (FIX-KPI)."""
import sys, os, json
from datetime import datetime, date, timezone, timedelta

SKILL_NAME = "contaazul"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/contaazul.env")
TOKEN_ENV = "CONTAAZUL_ACCESS_TOKEN"


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


def _parse_due(due: str):
    if not due:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(due)[:10], fmt).date()
        except ValueError:
            continue
    return None


def _days_overdue(due: str) -> int:
    d = _parse_due(due)
    return max(0, (date.today() - d).days) if d else 0


def _build_cash_projection(balance, receivables, payables, days=90) -> list:
    today = date.today()
    horizon = today + timedelta(days=days)
    flow: dict = {}
    for r in receivables:
        d = _parse_due(r.get("due_date", ""))
        if d and today <= d <= horizon:
            flow[d.isoformat()] = flow.get(d.isoformat(), 0.0) + float(r.get("amount_brl", 0) or 0)
    for p in payables:
        d = _parse_due(p.get("due_date", ""))
        if d and today <= d <= horizon:
            flow[d.isoformat()] = flow.get(d.isoformat(), 0.0) - float(p.get("amount_brl", 0) or 0)
    if not flow:
        return []
    series, running = [], float(balance)
    for offset in range(days + 1):
        d = (today + timedelta(days=offset)).isoformat()
        running += flow.get(d, 0.0)
        series.append({"date": d, "balance_brl": round(running, 2)})
    return series


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
    if not has_creds or not os.environ.get(TOKEN_ENV):
        out["health"] = {"status": "credential_invalid", "last_sync": _now_iso()}
        return out

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from contaazul_client import ContaAzulClient
        client = ContaAzulClient()

        degraded = False
        rec_items: list = []
        pay_items: list = []

        try:
            out["balance_brl"] = round(float(client.get_balance().get("balance_brl", 0.0)), 2)
        except Exception:
            degraded = True

        try:
            rec_items = client.list_receivables(limit=200).get("items", [])
            out["receivables_brl"] = round(sum(float(i.get("amount_brl", 0) or 0) for i in rec_items), 2)
        except Exception:
            degraded = True

        try:
            pay_items = client.list_payables(limit=200).get("items", [])
            out["payables_brl"] = round(sum(float(i.get("amount_brl", 0) or 0) for i in pay_items), 2)
        except Exception:
            degraded = True

        try:
            ovd = client.list_overdue().get("items", [])
            out["overdue_total_brl"] = round(sum(float(i.get("amount_brl", 0) or 0) for i in ovd), 2)
            ranked = sorted(ovd, key=lambda x: -float(x.get("amount_brl", 0) or 0))[:10]
            out["top_debtors"] = [
                {
                    "name": i.get("counterparty") or i.get("name") or "—",
                    "brl": round(float(i.get("amount_brl", 0) or 0), 2),
                    "days_overdue": _days_overdue(i.get("due_date", "")),
                }
                for i in ranked
            ]
        except Exception:
            degraded = True

        try:
            out["cash_projection_90d"] = _build_cash_projection(out["balance_brl"], rec_items, pay_items)
        except Exception:
            out["cash_projection_90d"] = []

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
