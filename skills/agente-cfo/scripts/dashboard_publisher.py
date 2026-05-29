#!/usr/bin/env python3
"""
dashboard_publisher.py — daemon que publica o snapshot financeiro consolidado
do agente-cfo no painel central (Lovable Cloud) via /dashboard-snapshot-push.

Modelo PUSH: roda dashboard_metrics.py de cada integração ativa, agrega o
contrato plano em um payload canônico (KPIs, pipeline, projeção de caixa,
devedores, saúde) e POSTa periodicamente.

Lê env de ~/.agente-cfo/.env (ou /root/.agente-cfo/.env).

Uso:
  python3 dashboard_publisher.py            # loop contínuo
  python3 dashboard_publisher.py --once     # roda 1x e sai
  python3 dashboard_publisher.py --dry-run  # imprime payload, não faz POST
"""
import os
import sys
import json
import time
import glob
import logging
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

LOG_DIR = os.path.expanduser("~/.agente-cfo/logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "dashboard-publisher.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("dashboard_publisher")


def _load_env():
    """Carrega variáveis de ~/.agente-cfo/.env e /root/.agente-cfo/.env."""
    candidates = [
        os.path.expanduser("~/.agente-cfo/.env"),
        "/root/.agente-cfo/.env",
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception as e:
            log.warning("falha lendo %s: %s", path, e)


def _interval():
    try:
        return int(os.environ.get("DASHBOARD_PUBLISHER_INTERVAL_S", "120"))
    except ValueError:
        return 120


def _discover_integrations():
    """Descobre integrações ativas: omie (sempre) + secrets/*.env."""
    integrations = ["omie"]
    secrets_dir = os.path.expanduser("~/.openclaw/secrets")
    for path in glob.glob(os.path.join(secrets_dir, "*.env")):
        name = os.path.splitext(os.path.basename(path))[0]
        if name and name not in integrations:
            integrations.append(name)
    return integrations


def _collect(name):
    """Roda dashboard_metrics.py da integração e retorna o contrato plano."""
    script = os.path.expanduser(
        f"~/.openclaw/workspace/skills/{name}/scripts/dashboard_metrics.py"
    )
    if not os.path.isfile(script):
        log.warning("dashboard_metrics.py de %s não encontrado: %s", name, script)
        return {"name": name, "health": {"status": "error", "last_sync": None}}
    try:
        result = subprocess.run(
            ["python3", script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.warning("dashboard_metrics %s rc=%s: %s", name, result.returncode, result.stderr.strip())
            return {"name": name, "status": "error", "last_sync": None,
                    "health": {"status": "error", "last_sync": None}}
        data = json.loads(result.stdout)
        data["name"] = name
        return data
    except subprocess.TimeoutExpired:
        log.warning("dashboard_metrics %s timeout", name)
        return {"name": name, "status": "error", "last_sync": None,
                "health": {"status": "error", "last_sync": None}}
    except Exception as e:
        log.warning("dashboard_metrics %s falhou: %s", name, e)
        return {"name": name, "status": "error", "last_sync": None,
                "health": {"status": "error", "last_sync": None}}


def _collect_report(label, script_name, days=90):
    """Roda erp_gateway/crm_gateway pra obter um report e devolve o JSON cru.
    Em qualquer falha (rc!=0, timeout, JSON inválido, script ausente) -> {}."""
    script = os.path.expanduser(
        f"~/.openclaw/workspace/skills/agente-cfo/scripts/{script_name}"
    )
    cmd_map = {
        "erp_gateway.py": "get_cash_projection",
        "crm_gateway.py": "get_pipeline_projection",
    }
    subcommand = cmd_map.get(script_name, "")
    try:
        result = subprocess.run(
            ["python3", script, subcommand, "--days", str(days), "--json"],
            capture_output=True, text=True, timeout=45,
        )
        if result.returncode != 0:
            log.warning("%s rc=%s: %s", label, result.returncode, result.stderr.strip()[:200])
            return {}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        log.warning("%s timeout", label)
        return {}
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError) as e:
        log.warning("%s falhou: %s", label, e)
        return {}
    except Exception as e:
        log.warning("%s falhou (inesperado): %s", label, e)
        return {}


def _build_payload():
    active_integrations = _discover_integrations()
    results = [_collect(name) for name in active_integrations]

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "kpis": {
            "balance_brl": next((d["balance_brl"] for d in results if d.get("balance_brl", 0) > 0), 0),
            "receivables_30d_brl": sum(d.get("receivables_brl", 0) for d in results),
            "payables_30d_brl": sum(d.get("payables_brl", 0) for d in results),
            "pipeline_weighted_brl": sum(d.get("pipeline_weighted_brl", 0) for d in results),
            "ecommerce_revenue_month_brl": sum(d.get("ecommerce_revenue_month_brl", 0) for d in results),
            "overdue_total_brl": sum(d.get("overdue_total_brl", 0) for d in results),
        },
        "by_channel_revenue_30d": [
            {"channel": name, "brl": d.get("receivables_brl", 0) + d.get("ecommerce_revenue_month_brl", 0)}
            for name, d in zip(active_integrations, results)
            if d.get("receivables_brl", 0) + d.get("ecommerce_revenue_month_brl", 0) > 0
        ],
        "pipeline_by_stage": next((d["pipeline_by_stage"] for d in results if d.get("pipeline_by_stage")), []),
        "cash_projection_90d": next((d["cash_projection_90d"] for d in results if d.get("cash_projection_90d")), []),
        "top_debtors": next((d["top_debtors"] for d in results if d.get("top_debtors")), [])[:10],
        "integrations_health": [
            {"name": name, "status": d.get("health", {}).get("status", "error"), "last_sync": d.get("health", {}).get("last_sync")}
            for name, d in zip(active_integrations, results)
        ],
    }

    # Embute reports completos (JSON cru dos gateways) — fallback {} em falha.
    payload["reports"] = {
        "cash_projection": _collect_report("erp_gateway get_cash_projection", "erp_gateway.py"),
        "pipeline_projection": _collect_report("crm_gateway get_pipeline_projection", "crm_gateway.py"),
    }
    return payload


def _post(payload):
    base = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    hooks_token = os.environ.get("HOOKS_TOKEN", "")
    if not base:
        log.error("PANEL_BASE_URL não definido — abortando POST")
        return False
    url = f"{base}/dashboard-snapshot-push"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Panel-Token", panel_token)
    req.add_header("X-Hooks-Token", hooks_token)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log.info("POST %s -> %s", url, resp.status)
            return True
    except urllib.error.HTTPError as e:
        log.error("POST %s falhou: HTTP %s %s", url, e.code, e.read().decode("utf-8", "ignore"))
        return False
    except Exception as e:
        log.error("POST %s falhou: %s", url, e)
        return False


def main():
    _load_env()
    once = "--once" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        payload = _build_payload()
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    interval = _interval()
    log.info("dashboard_publisher iniciado (interval=%ss)", interval)
    while True:
        try:
            payload = _build_payload()
            _post(payload)
        except Exception as e:
            log.error("loop falhou: %s", e)
        if once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
