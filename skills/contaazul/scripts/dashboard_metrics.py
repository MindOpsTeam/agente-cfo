#!/usr/bin/env python3
"""Dashboard metrics para skill contaazul — Agente CFO. Sprint INT-2."""
import sys, os, json
from datetime import datetime, timezone

SKILL_NAME = "contaazul"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/contaazul.env")

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
    if not has_creds or not os.environ.get("CONTAAZUL_ACCESS_TOKEN"):
        base["health"] = "credential_invalid"
        base["error"] = f"Secrets não encontrados ou CONTAAZUL_ACCESS_TOKEN ausente: {SECRETS_FILE}"
        return base

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from contaazul_client import ContaAzulClient
        client = ContaAzulClient()

        metrics = {}
        degraded = False

        try:
            saldo = client.get_saldo()
            metrics["balance_brl"] = round(float(saldo.get("saldo", 0.0)), 2)
        except Exception:
            metrics["balance_brl"] = 0.0
            degraded = True

        try:
            rec = client.list_contas_receber(days=30)
            metrics["receivables_30d_brl"] = round(sum(float(i.get("valor", 0)) for i in rec.get("data", [])), 2)
        except Exception:
            metrics["receivables_30d_brl"] = 0.0
            degraded = True

        try:
            pay = client.list_contas_pagar(days=30)
            metrics["payables_30d_brl"] = round(sum(float(i.get("valor", 0)) for i in pay.get("data", [])), 2)
        except Exception:
            metrics["payables_30d_brl"] = 0.0
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
