#!/usr/bin/env python3
"""
metrics_publisher.py — Daemon de coleta e publicação de métricas pro painel.

Sprint 40 — Observability: cliente vê o que Marcos faz sem SSH.

Loop a cada METRICS_PUBLISHER_INTERVAL_S (default: 60s):
  1. Lê ~/.agente-cfo/logs/metrics.jsonl (últimas 24h)
  2. Agrega métricas por daemon e por tool
  3. Coleta status atual dos daemons via systemctl
  4. Lê uso de tokens do log do OpenClaw (se disponível)
  5. POST /metrics-publish (X-Panel-Token + X-Hooks-Token)

Formato metrics.jsonl (emitido por cada daemon e por metric_emit.sh):
  {"ts":"2026-05-14T12:00:00Z","daemon":"<name>","cycle_ms":<int>,"errors":<int>,"meta":{}}

Logs: ~/.agente-cfo/logs/metrics-publisher.log
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE       = Path.home() / ".agente-cfo" / ".env"
LOG_FILE       = Path.home() / ".agente-cfo" / "logs" / "metrics-publisher.log"
METRICS_JSONL  = Path.home() / ".agente-cfo" / "logs" / "metrics.jsonl"

INTERVAL_S = int(os.environ.get("METRICS_PUBLISHER_INTERVAL_S", "60"))

# Daemons monitorados
DAEMONS = [
    "openclaw-gateway",
    "cloudflared-cfo",
    "cfo-proactive",
    "cfo-automation-engine",
    "cfo-credentials-sync",
    "cfo-supabase-sync",
    "cfo-mcp-warmer",
    "cfo-metrics-publisher",
]


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── Env loader ────────────────────────────────────────────────────────────────

def load_env() -> None:
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for raw in f:
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                k, _, v = raw.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ── metrics.jsonl reader ──────────────────────────────────────────────────────

def read_metrics_jsonl(hours: int = 24) -> list[dict]:
    """Lê metrics.jsonl e filtra entradas das últimas `hours` horas."""
    if not METRICS_JSONL.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    records: list[dict] = []
    try:
        with open(METRICS_JSONL) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    ts_str = rec.get("ts", "")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts >= cutoff:
                            records.append(rec)
                except Exception:
                    pass
    except Exception as e:
        log(f"[metrics] Erro lendo metrics.jsonl: {e}")
    return records


# ── Agregação de métricas ─────────────────────────────────────────────────────

def aggregate_metrics(records: list[dict]) -> list[dict]:
    """
    Agrega registros por daemon:
    - cycle_count: total de ciclos
    - total_errors: soma de errors
    - avg_cycle_ms: média de cycle_ms
    - last_seen: último ts

    Também agrega por "tool" se meta.tool_name estiver presente.
    """
    from collections import defaultdict

    # Agrega por daemon
    by_daemon: dict[str, dict] = defaultdict(lambda: {
        "cycles": 0, "errors": 0, "total_ms": 0, "last_seen": ""
    })
    # Agrega por tool (metric_name para emissões de ferramentas)
    by_tool: dict[str, dict] = defaultdict(lambda: {
        "calls": 0, "errors": 0, "total_ms": 0
    })

    for rec in records:
        daemon = rec.get("daemon", "unknown")
        cycle_ms = int(rec.get("cycle_ms", 0))
        errors = int(rec.get("errors", 0))
        ts = rec.get("ts", "")
        meta = rec.get("meta", {})

        # Daemon agregation
        by_daemon[daemon]["cycles"] += 1
        by_daemon[daemon]["errors"] += errors
        by_daemon[daemon]["total_ms"] += cycle_ms
        if ts > by_daemon[daemon]["last_seen"]:
            by_daemon[daemon]["last_seen"] = ts

        # Tool aggregation (metric_emit emite com meta.tool_name)
        tool_name = meta.get("tool_name") or meta.get("metric_name")
        if tool_name:
            by_tool[tool_name]["calls"] += 1
            by_tool[tool_name]["errors"] += meta.get("error", 0)
            by_tool[tool_name]["total_ms"] += cycle_ms

    metrics_out: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for daemon, data in by_daemon.items():
        avg_ms = data["total_ms"] // data["cycles"] if data["cycles"] else 0
        error_rate = (data["errors"] / data["cycles"]) if data["cycles"] else 0.0
        metrics_out.extend([
            {
                "metric_name": "daemon.cycle_count",
                "metric_value": data["cycles"],
                "labels": {"daemon": daemon},
                "recorded_at": now_iso,
            },
            {
                "metric_name": "daemon.error_count",
                "metric_value": data["errors"],
                "labels": {"daemon": daemon},
                "recorded_at": now_iso,
            },
            {
                "metric_name": "daemon.avg_cycle_ms",
                "metric_value": avg_ms,
                "labels": {"daemon": daemon},
                "recorded_at": now_iso,
            },
            {
                "metric_name": "daemon.error_rate",
                "metric_value": round(error_rate, 4),
                "labels": {"daemon": daemon, "last_seen": data["last_seen"]},
                "recorded_at": now_iso,
            },
        ])

    for tool_name, data in by_tool.items():
        avg_ms = data["total_ms"] // data["calls"] if data["calls"] else 0
        metrics_out.extend([
            {
                "metric_name": "tool.call_count",
                "metric_value": data["calls"],
                "labels": {"tool": tool_name},
                "recorded_at": now_iso,
            },
            {
                "metric_name": "tool.avg_ms",
                "metric_value": avg_ms,
                "labels": {"tool": tool_name},
                "recorded_at": now_iso,
            },
        ])

    return metrics_out


# ── Status dos daemons ────────────────────────────────────────────────────────

def collect_daemon_status() -> list[dict]:
    """Coleta status atual de cada daemon via systemctl (ou heurística macOS)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: list[dict] = []
    has_systemctl = _has_systemctl()

    for daemon in DAEMONS:
        if has_systemctl:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", daemon],
                    capture_output=True, text=True, timeout=5,
                )
                active = 1 if result.stdout.strip() == "active" else 0
            except Exception:
                active = -1
        else:
            # macOS: verifica por processo
            try:
                result = subprocess.run(
                    ["pgrep", "-f", daemon],
                    capture_output=True, text=True, timeout=5,
                )
                active = 1 if result.returncode == 0 else 0
            except Exception:
                active = 0

        metrics.append({
            "metric_name": "daemon.active",
            "metric_value": active,
            "labels": {"daemon": daemon},
            "recorded_at": now_iso,
        })

    return metrics


def _has_systemctl() -> bool:
    try:
        subprocess.run(["systemctl", "--version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Métricas do gateway OpenClaw (tokens) ─────────────────────────────────────

def collect_openclaw_metrics() -> list[dict]:
    """Coleta métricas do gateway OpenClaw via CLI."""
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: list[dict] = []
    try:
        result = subprocess.run(
            ["openclaw", "usage", "status", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            # Extrai campos de uso se disponíveis
            total_tokens = data.get("totalTokens") or data.get("total_tokens")
            cost_usd = data.get("estimatedCostUsd") or data.get("cost_usd")
            if total_tokens is not None:
                metrics.append({
                    "metric_name": "openclaw.total_tokens_today",
                    "metric_value": int(total_tokens),
                    "labels": {},
                    "recorded_at": now_iso,
                })
            if cost_usd is not None:
                metrics.append({
                    "metric_name": "openclaw.cost_usd_today",
                    "metric_value": round(float(cost_usd), 6),
                    "labels": {},
                    "recorded_at": now_iso,
                })
    except Exception:
        # openclaw status pode não ter --json ou falhar — não é crítico
        pass
    return metrics


# ── MCP warmer métricas ───────────────────────────────────────────────────────

def collect_mcp_warmer_metrics() -> list[dict]:
    """Lê últimas métricas do mcp-warmer do log."""
    now_iso = datetime.now(timezone.utc).isoformat()
    metrics: list[dict] = []
    warmer_log = Path.home() / ".agente-cfo" / "logs" / "mcp-warmer.log"
    if not warmer_log.exists():
        return metrics

    # Lê últimas 100 linhas e extrai tempos
    try:
        result = subprocess.run(
            ["tail", "-100", str(warmer_log)],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.splitlines()
        # Procura por linhas com "ok N tools (Xms)"
        import re
        for line in lines:
            m = re.search(r"✓ (.+?): ok (\d+) tools \((\d+)ms\)", line)
            if m:
                name, tools, ms = m.group(1), int(m.group(2)), int(m.group(3))
                metrics.append({
                    "metric_name": "mcp.warmup_ms",
                    "metric_value": ms,
                    "labels": {"mcp": name, "tools": str(tools)},
                    "recorded_at": now_iso,
                })
    except Exception:
        pass
    return metrics


# ── Panel publish ─────────────────────────────────────────────────────────────

def publish_metrics(metrics: list[dict]) -> bool:
    """POST /metrics-publish com lista de métricas."""
    if not metrics:
        return True

    panel_base = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    hooks_token = os.environ.get("HOOKS_TOKEN", "")

    if not all([panel_base, panel_token, hooks_token]):
        log("[publish] PANEL_BASE_URL, PANEL_TOKEN ou HOOKS_TOKEN não configurados")
        return False

    url = f"{panel_base}/metrics-publish"
    body = json.dumps(metrics, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={
            "X-Panel-Token": panel_token,
            "X-Hooks-Token": hooks_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read()
            return True
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()[:200]
        log(f"[publish] HTTP {e.code}: {body_err}")
        return False
    except Exception as e:
        log(f"[publish] Erro: {e}")
        return False


# ── Ciclo principal ───────────────────────────────────────────────────────────

def collect_and_publish() -> None:
    """Coleta todas as métricas e publica no painel."""
    # 1. Lê metrics.jsonl
    records = read_metrics_jsonl(hours=24)
    aggregated = aggregate_metrics(records)

    # 2. Status dos daemons
    daemon_status = collect_daemon_status()

    # 3. OpenClaw usage
    openclaw_metrics = collect_openclaw_metrics()

    # 4. MCP warmer timings
    mcp_metrics = collect_mcp_warmer_metrics()

    all_metrics = aggregated + daemon_status + openclaw_metrics + mcp_metrics

    log(f"[collect] {len(records)} registros em 24h → {len(all_metrics)} métricas")

    ok = publish_metrics(all_metrics)
    if ok:
        log(f"[publish] {len(all_metrics)} métricas publicadas")
    else:
        log("[publish] Falha ao publicar (edge fn não deployada ou erro de rede)")


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()
    log("metrics_publisher.py started (Sprint 40 — Observability)")
    log(f"Intervalo: {INTERVAL_S}s | JSONL: {METRICS_JSONL}")

    while True:
        log("--- Início do ciclo metrics-publisher ---")
        try:
            collect_and_publish()
        except Exception as e:
            log(f"[main] Erro: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    run_loop()
