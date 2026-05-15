#!/usr/bin/env python3
"""
cost_estimator.py — Calcula custo Anthropic a partir de tokens do OpenClaw.

Sprint 42 — Budget tracking: calcula custo acumulado do dia/mês
consultando sessions_list via /tools/invoke e emite métricas via metric_emit.sh.

Preços (claude-sonnet-4-6, Maio 2026 — ajuste conforme Anthropic pricing):
  Input:  $3.00 / MTok
  Output: $15.00 / MTok
  Cache-write: $3.75 / MTok
  Cache-read:  $0.30 / MTok

Cotação fixa USD/BRL: 5.0 (ajustar via env USD_BRL_RATE)
"""
import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Preços por modelo (USD per million tokens) ────────────────────────────────
MODEL_PRICES: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input":        3.00,
        "output":      15.00,
        "cache_write":  3.75,
        "cache_read":   0.30,
    },
    "claude-opus-4-7": {
        "input":       15.00,
        "output":      75.00,
        "cache_write": 18.75,
        "cache_read":   1.50,
    },
    "claude-haiku-3-5": {
        "input":        0.80,
        "output":        4.00,
        "cache_write":   1.00,
        "cache_read":    0.08,
    },
}

DEFAULT_PRICES = MODEL_PRICES["claude-sonnet-4-6"]
USD_BRL_RATE = float(os.environ.get("USD_BRL_RATE", "5.0"))

ENV_FILE = Path.home() / ".agente-cfo" / ".env"
METRIC_EMIT = Path.home() / ".openclaw" / "workspace" / "skills" / "agente-cfo" / "scripts" / "metric_emit.sh"


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for raw in f:
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                k, _, v = raw.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def _gateway_token() -> str:
    cfg_file = Path.home() / ".openclaw" / "openclaw.json"
    if not cfg_file.exists():
        return ""
    try:
        data = json.loads(cfg_file.read_text())
        return data.get("gateway", {}).get("auth", {}).get("token", "")
    except Exception:
        return ""


def _gateway_invoke(tool: str, args: dict) -> Optional[dict]:
    """Chama /tools/invoke no gateway local."""
    token = _gateway_token()
    if not token:
        return None
    try:
        body = json.dumps({"tool": tool, "args": args}).encode()
        req = urllib.request.Request(
            "http://localhost:18789/tools/invoke",
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("result", {}).get("details")
    except Exception:
        return None


def estimate_cost_usd(total_tokens: int, model: str = "claude-sonnet-4-6") -> float:
    """
    Estimativa simples baseada em total_tokens assumindo split 70/30 input/output.
    Para cálculo mais preciso, usar estimatedCostUsd já retornado pelo OpenClaw.
    """
    prices = MODEL_PRICES.get(model, DEFAULT_PRICES)
    # Split estimado: 70% input, 30% output
    input_tok = int(total_tokens * 0.7)
    output_tok = total_tokens - input_tok
    cost = (input_tok * prices["input"] + output_tok * prices["output"]) / 1_000_000
    return round(cost, 6)


def collect_session_costs() -> dict:
    """
    Lê sessions_list e acumula custo total do dia.
    Retorna { total_tokens, cost_usd, cost_brl, sessions_count, by_model }.
    """
    details = _gateway_invoke("sessions_list", {})
    if not details:
        return {}

    sessions = details.get("sessions", [])
    now_utc = datetime.now(timezone.utc)
    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    total_tokens = 0
    cost_usd = 0.0
    by_model: dict[str, float] = {}
    sessions_today = 0

    for s in sessions:
        started_at = s.get("startedAt")
        if started_at:
            try:
                ts = datetime.fromtimestamp(started_at / 1000, tz=timezone.utc)
                if ts < day_start:
                    continue
            except Exception:
                pass

        tok = s.get("totalTokens", 0) or 0
        cost = s.get("estimatedCostUsd", 0.0) or 0.0
        model = s.get("model", "unknown")

        total_tokens += tok
        cost_usd += cost
        by_model[model] = by_model.get(model, 0.0) + cost
        sessions_today += 1

    cost_brl = round(cost_usd * USD_BRL_RATE, 4)
    return {
        "total_tokens": total_tokens,
        "cost_usd": round(cost_usd, 6),
        "cost_brl": cost_brl,
        "sessions_count": sessions_today,
        "by_model": by_model,
    }


def emit_cost_metrics(costs: dict) -> None:
    """Emite métricas de custo via metric_emit.sh."""
    if not costs or not METRIC_EMIT.exists():
        return

    items = [
        ("anthropic.tokens_today", costs.get("total_tokens", 0),
         {"sessions": costs.get("sessions_count", 0)}),
        ("anthropic.cost_usd_today", int(costs.get("cost_usd", 0) * 1_000_000),
         {"display": f"${costs.get('cost_usd', 0):.4f}"}),
        ("anthropic.cost_brl_today", int(costs.get("cost_brl", 0) * 100),
         {"display": f"R${costs.get('cost_brl', 0):.2f}"}),
    ]
    for metric_name, value_ms, meta in items:
        try:
            subprocess.run(
                ["bash", str(METRIC_EMIT), metric_name, str(value_ms), json.dumps(meta)],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass


if __name__ == "__main__":
    load_env()
    costs = collect_session_costs()
    if costs:
        print(f"Tokens hoje: {costs['total_tokens']:,}")
        print(f"Custo hoje:  ${costs['cost_usd']:.4f} USD / R${costs['cost_brl']:.2f} BRL")
        print(f"Sessões:     {costs['sessions_count']}")
        print(f"Por modelo:  {costs['by_model']}")
        emit_cost_metrics(costs)
    else:
        print("Não foi possível coletar dados de custo (gateway offline?)")
