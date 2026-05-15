#!/usr/bin/env python3
"""
alerts_checker.py — Daemon de avaliação e disparo de alertas configuráveis.

Sprint 42 — Alertas sem SSH: cliente configura no painel, VPS dispara
via WhatsApp/Telegram/painel quando condição é atendida.

Loop a cada ALERTS_CHECKER_INTERVAL_S (default: 60s):
  1. GET /alerts-config-vps-list → lista de alertas ativos
  2. Coleta métricas locais (metrics.jsonl + daemon status + custo)
  3. Avalia cada alerta
  4. Se disparado E cooldown expirado → registra + notifica

Tipos de alerta:
  error_rate  : taxa de erro de daemon > threshold
  daemon_down : daemon inativo por > window_min
  cost_budget : custo diário > threshold_brl
  latency     : avg_cycle_ms > threshold_ms

Cooldown padrão: 30min (configurável por alerta via condition.cooldown_min).

Logs: ~/.agente-cfo/logs/alerts-checker.log
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
ENV_FILE      = Path.home() / ".agente-cfo" / ".env"
LOG_FILE      = Path.home() / ".agente-cfo" / "logs" / "alerts-checker.log"
METRICS_JSONL = Path.home() / ".agente-cfo" / "logs" / "metrics.jsonl"
STATE_FILE    = Path.home() / ".agente-cfo" / "state" / "alerts_state.json"
WORKSPACE     = Path.home() / ".openclaw" / "workspace" / "skills" / "agente-cfo" / "scripts"

INTERVAL_S    = int(os.environ.get("ALERTS_CHECKER_INTERVAL_S", "60"))
DEFAULT_COOLDOWN_MIN = 30


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


# ── State (cooldown tracking) ─────────────────────────────────────────────────

def load_state() -> dict:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def is_in_cooldown(alert_id: str, cooldown_min: int, state: dict) -> bool:
    """Retorna True se o alerta ainda está em cooldown."""
    last_fired = state.get(f"last_fired:{alert_id}")
    if not last_fired:
        return False
    try:
        last_dt = datetime.fromisoformat(last_fired.replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60
        return elapsed < cooldown_min
    except Exception:
        return False


def mark_fired(alert_id: str, state: dict) -> None:
    state[f"last_fired:{alert_id}"] = datetime.now(timezone.utc).isoformat()


# ── Panel API ─────────────────────────────────────────────────────────────────

def _panel_headers() -> dict:
    return {
        "X-Panel-Token": os.environ.get("PANEL_TOKEN", ""),
        "X-Hooks-Token":  os.environ.get("HOOKS_TOKEN", ""),
        "Content-Type": "application/json",
    }


def _panel_base() -> str:
    return os.environ.get("PANEL_BASE_URL", "").rstrip("/")


def fetch_alerts_config() -> list[dict]:
    """GET /alerts-config-vps-list → lista de alertas ativos."""
    base = _panel_base()
    if not base:
        return []
    url = f"{base}/alerts-config-vps-list"
    req = urllib.request.Request(url, headers=_panel_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else data.get("alerts", [])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []  # Edge function não deployada ainda
        log(f"[fetch] HTTP {e.code}")
        return []
    except Exception as e:
        log(f"[fetch] Erro: {e}")
        return []


def record_alert_fired(alert_id: str, payload: dict) -> None:
    """POST /alerts-record-fired → grava no alerts_history."""
    base = _panel_base()
    if not base:
        return
    body = json.dumps({"alert_id": alert_id, "payload": payload, "status": "fired"},
                       default=str).encode()
    req = urllib.request.Request(
        f"{base}/alerts-record-fired",
        data=body, headers=_panel_headers(), method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as _:
            pass
    except Exception:
        pass  # Best-effort


# ── Coleta de métricas locais ─────────────────────────────────────────────────

def read_recent_metrics(hours: int = 1) -> list[dict]:
    """Lê metrics.jsonl das últimas N horas."""
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
    except Exception:
        pass
    return records


def daemon_is_active(daemon_name: str) -> bool:
    """Verifica se daemon está rodando."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", daemon_name],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "active"
    except FileNotFoundError:
        # macOS fallback: pgrep
        try:
            result = subprocess.run(
                ["pgrep", "-f", daemon_name],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    except Exception:
        return False


def get_cost_brl_today() -> float:
    """Coleta custo do dia via cost_estimator."""
    try:
        cost_script = WORKSPACE / "cost_estimator.py"
        if not cost_script.exists():
            return 0.0
        result = subprocess.run(
            [sys.executable, str(cost_script)],
            capture_output=True, text=True, timeout=20,
        )
        for line in result.stdout.splitlines():
            if "R$" in line and "Custo" in line:
                # "Custo hoje:  $0.5768 USD / R$2.88 BRL"
                import re
                m = re.search(r"R\$([0-9.]+)", line)
                if m:
                    return float(m.group(1))
    except Exception:
        pass
    return 0.0


# ── Avaliadores por tipo de alerta ────────────────────────────────────────────

def evaluate_error_rate(alert: dict, records: list[dict]) -> tuple[bool, dict]:
    """
    Dispara se taxa de erro de um daemon > threshold nas últimas window_min.
    condition: { daemon, threshold (0.0-1.0), window_min }
    """
    cond = alert.get("condition", {})
    daemon = cond.get("daemon", "")
    threshold = float(cond.get("threshold", 0.5))
    window_min = int(cond.get("window_min", 5))

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_min)
    daemon_records = [
        r for r in records
        if r.get("daemon") == daemon
        and datetime.fromisoformat(r.get("ts", "").replace("Z", "+00:00")) >= cutoff
    ]

    if not daemon_records:
        return False, {}

    total = len(daemon_records)
    errors = sum(int(r.get("errors", 0)) for r in daemon_records)
    rate = errors / total if total else 0.0

    fired = rate > threshold
    payload = {"daemon": daemon, "error_rate": round(rate, 3),
                "threshold": threshold, "total_cycles": total, "window_min": window_min}
    return fired, payload


def evaluate_daemon_down(alert: dict) -> tuple[bool, dict]:
    """
    Dispara se daemon está inativo.
    condition: { daemon }
    """
    cond = alert.get("condition", {})
    daemon = cond.get("daemon", "")
    if not daemon:
        return False, {}
    active = daemon_is_active(daemon)
    payload = {"daemon": daemon, "active": active}
    return not active, payload


def evaluate_cost_budget(alert: dict) -> tuple[bool, dict]:
    """
    Dispara se custo diário > threshold_brl.
    condition: { threshold_brl }
    """
    cond = alert.get("condition", {})
    threshold_brl = float(cond.get("threshold_brl", 50.0))
    cost_brl = get_cost_brl_today()
    fired = cost_brl >= threshold_brl
    payload = {"cost_brl": cost_brl, "threshold_brl": threshold_brl}
    return fired, payload


def evaluate_latency(alert: dict, records: list[dict]) -> tuple[bool, dict]:
    """
    Dispara se avg_cycle_ms de um daemon > threshold_ms.
    condition: { daemon, threshold_ms, window_min }
    """
    cond = alert.get("condition", {})
    daemon = cond.get("daemon", "")
    threshold_ms = int(cond.get("threshold_ms", 60_000))
    window_min = int(cond.get("window_min", 5))

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_min)
    daemon_records = [
        r for r in records
        if r.get("daemon") == daemon
        and datetime.fromisoformat(r.get("ts", "").replace("Z", "+00:00")) >= cutoff
    ]

    if not daemon_records:
        return False, {}

    total_ms = sum(int(r.get("cycle_ms", 0)) for r in daemon_records)
    avg_ms = total_ms // len(daemon_records)
    fired = avg_ms > threshold_ms
    payload = {"daemon": daemon, "avg_ms": avg_ms,
                "threshold_ms": threshold_ms, "window_min": window_min}
    return fired, payload


def evaluate_alert(alert: dict, records: list[dict]) -> tuple[bool, dict]:
    """Avalia um alerta e retorna (fired, payload)."""
    alert_type = alert.get("type", "")
    try:
        if alert_type == "error_rate":
            return evaluate_error_rate(alert, records)
        if alert_type == "daemon_down":
            return evaluate_daemon_down(alert)
        if alert_type == "cost_budget":
            return evaluate_cost_budget(alert)
        if alert_type == "latency":
            return evaluate_latency(alert, records)
    except Exception as e:
        log(f"[eval] Erro avaliando {alert.get('id', '?')} ({alert_type}): {e}")
    return False, {}


# ── Notificação ───────────────────────────────────────────────────────────────

def format_alert_message(alert: dict, payload: dict) -> str:
    """Formata mensagem de alerta pra envio."""
    name = alert.get("name", "Alerta sem nome")
    alert_type = alert.get("type", "?")

    if alert_type == "error_rate":
        daemon = payload.get("daemon", "?")
        rate = payload.get("error_rate", 0)
        return (f"🚨 *{name}*\n"
                f"Taxa de erro do daemon `{daemon}` está em {rate:.0%} "
                f"(limite: {alert.get('condition',{}).get('threshold',0):.0%})")

    if alert_type == "daemon_down":
        daemon = payload.get("daemon", "?")
        return (f"🔴 *{name}*\n"
                f"Daemon `{daemon}` está INATIVO.\n"
                f"Execute: systemctl restart {daemon}")

    if alert_type == "cost_budget":
        cost = payload.get("cost_brl", 0)
        limit = payload.get("threshold_brl", 0)
        return (f"💸 *{name}*\n"
                f"Custo Anthropic hoje: R${cost:.2f} (limite: R${limit:.2f})")

    if alert_type == "latency":
        daemon = payload.get("daemon", "?")
        avg_ms = payload.get("avg_ms", 0)
        threshold_ms = payload.get("threshold_ms", 0)
        return (f"⚠️ *{name}*\n"
                f"Daemon `{daemon}` com latência alta: {avg_ms}ms "
                f"(limite: {threshold_ms}ms)")

    return f"🔔 *{name}*\n{json.dumps(payload, ensure_ascii=False)}"


def send_notification(alert: dict, message: str) -> None:
    """Envia notificação nos canais configurados no alerta."""
    channels: list[str] = alert.get("channels", ["panel"])
    panel_post_reply = WORKSPACE / "panel_post_reply.sh"

    for channel_spec in channels:
        # channel_spec pode ser "panel", "whatsapp:instance:phone", "telegram:bot:chat_id"
        parts = channel_spec.split(":")
        channel_type = parts[0]

        try:
            if channel_type == "whatsapp" and len(parts) >= 3:
                instance, phone = parts[1], parts[2]
                send_script = WORKSPACE.parent.parent / "evolution-api" / "scripts" / "send_evolution.sh"
                if send_script.exists():
                    subprocess.run(
                        ["bash", str(send_script), instance, phone, message],
                        capture_output=True, timeout=30,
                    )
                    log(f"[notify] WA {instance}:{phone} ✓")

            elif channel_type == "telegram" and len(parts) >= 3:
                bot, chat_id = parts[1], parts[2]
                send_script = WORKSPACE.parent.parent / "telegram" / "scripts" / "send_telegram.sh"
                if send_script.exists():
                    subprocess.run(
                        ["bash", str(send_script), bot, chat_id, message],
                        capture_output=True, timeout=30,
                    )
                    log(f"[notify] TG {bot}:{chat_id} ✓")

            elif channel_type == "panel":
                # Emite evento no painel via edge function event
                panel_base = _panel_base()
                panel_token = os.environ.get("PANEL_TOKEN", "")
                if panel_base and panel_token:
                    body = json.dumps({
                        "type": "alert_fired",
                        "payload": {"message": message, "alert": alert.get("name")},
                    }).encode()
                    req = urllib.request.Request(
                        f"{panel_base}/event",
                        data=body,
                        headers={
                            "X-Panel-Token": panel_token,
                            "Content-Type": "application/json",
                        },
                        method="POST",
                    )
                    try:
                        urllib.request.urlopen(req, timeout=10)
                    except Exception:
                        pass

        except Exception as e:
            log(f"[notify] Erro canal {channel_spec}: {e}")


# ── Ciclo principal ───────────────────────────────────────────────────────────

def check_cycle() -> None:
    """Avalia todos os alertas ativos e dispara notificações conforme necessário."""
    alerts = fetch_alerts_config()
    if not alerts:
        return

    records = read_recent_metrics(hours=1)
    state = load_state()
    state_changed = False

    fired_count = 0
    for alert in alerts:
        if not alert.get("active", True):
            continue

        alert_id = str(alert.get("id", alert.get("name", "unknown")))
        cond = alert.get("condition", {})
        cooldown_min = int(cond.get("cooldown_min", DEFAULT_COOLDOWN_MIN))

        fired, payload = evaluate_alert(alert, records)

        if not fired:
            continue

        # Verifica cooldown
        if is_in_cooldown(alert_id, cooldown_min, state):
            log(f"[check] {alert.get('name', alert_id)}: DISPARADO mas em cooldown")
            continue

        # Dispara!
        log(f"[check] ⚡ ALERTA: {alert.get('name', alert_id)} ({alert.get('type')}) | {payload}")
        message = format_alert_message(alert, payload)

        # 1. Notifica canais
        send_notification(alert, message)

        # 2. Registra no painel
        record_alert_fired(alert_id, {**payload, "message": message})

        # 3. Atualiza cooldown
        mark_fired(alert_id, state)
        state_changed = True
        fired_count += 1

    if state_changed:
        save_state(state)

    log(f"[check] {len(alerts)} alertas avaliados, {fired_count} disparados")


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()
    log("alerts_checker.py started (Sprint 42)")
    log(f"Intervalo: {INTERVAL_S}s | Cooldown padrão: {DEFAULT_COOLDOWN_MIN}min")

    while True:
        log("--- Início do ciclo alerts-checker ---")
        try:
            check_cycle()
        except Exception as e:
            log(f"[main] Erro: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    run_loop()
