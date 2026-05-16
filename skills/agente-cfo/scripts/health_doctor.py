#!/usr/bin/env python3
"""
health_doctor.py — Daemon de saúde sistêmica e auto-recovery.

Sprint 44 — Auto-healing inteligente: detecta daemons doentes,
tenta recuperação automática quando seguro, escala para humano quando não.

Loop a cada HEALTH_DOCTOR_INTERVAL_S (default: 60s):
  1. Coleta status de todos os serviços monitorados
  2. Detecta daemons "unhealthy" (muitos restarts ou inativos)
  3. Aplica auto-recovery por tipo:
     - openclaw-gateway inválido → auto_rollback.sh + restart
     - cloudflared-cfo → restart simples
     - wacli-*         → PARA (Evolution substituiu wacli)
     - outros         → log + alerta, NÃO toca
  4. Publica métrica daemon_health (0=unhealthy, 1=healthy)
  5. Cooldown inteligente: se restarts > RESTART_LIMIT_HOUR → pausa + alerta

Logs: ~/.agente-cfo/logs/health-doctor.log
State: ~/.agente-cfo/state/health_doctor.json
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE   = Path.home() / ".agente-cfo" / ".env"
LOG_FILE   = Path.home() / ".agente-cfo" / "logs" / "health-doctor.log"
STATE_FILE = Path.home() / ".agente-cfo" / "state" / "health_doctor.json"
WORKSPACE  = Path.home() / ".openclaw" / "workspace" / "skills" / "agente-cfo" / "scripts"
OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

INTERVAL_S = int(os.environ.get("HEALTH_DOCTOR_INTERVAL_S", "60"))

# Limites de restart — configura via env
RESTART_LIMIT_HOUR  = int(os.environ.get("HEALTH_DOCTOR_RESTART_LIMIT_HOUR", "5"))
RESTART_LIMIT_DAY   = int(os.environ.get("HEALTH_DOCTOR_RESTART_LIMIT_DAY", "10"))
PAUSE_RESTART_MIN   = int(os.environ.get("HEALTH_DOCTOR_PAUSE_MIN", "10"))

# Serviços monitorados (whitelist rigorosa)
MONITORED_SERVICES = [
    "openclaw-gateway",
    "cloudflared-cfo",
    "cfo-proactive",
    "cfo-automation-engine",
    "cfo-credentials-sync",
    "cfo-supabase-sync",
    "cfo-mcp-warmer",
    "cfo-metrics-publisher",
    "cfo-alerts-checker",
    "cfo-health-doctor",
]

# Serviços com auto-recovery ativo (os outros só recebem diagnóstico+alerta)
AUTO_RECOVERY_SERVICES = {
    "openclaw-gateway",
    "cloudflared-cfo",
}

# Serviços que devem ser PARADOS se unhealthy (jamais auto-reiniciados)
STOP_IF_UNHEALTHY = {
    "wacli-sync",
    "wacli-inbound",
}


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


# ── Env + State ───────────────────────────────────────────────────────────────

def load_env() -> None:
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for raw in f:
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                k, _, v = raw.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


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


# ── systemctl wrappers ────────────────────────────────────────────────────────

def _has_systemctl() -> bool:
    try:
        subprocess.run(["systemctl", "--version"], capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def systemctl_show(service: str) -> dict:
    """
    Retorna propriedades relevantes do service via `systemctl show`.
    Se systemctl não disponível, retorna dados inferidos do processo.
    """
    if not _has_systemctl():
        return _macos_service_info(service)

    try:
        result = subprocess.run(
            ["systemctl", "show", service,
             "--property=ActiveState,SubState,Result,NRestarts,ExecMainStatus"],
            capture_output=True, text=True, timeout=10,
        )
        props: dict = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                props[k.strip()] = v.strip()
        return props
    except Exception as e:
        return {"error": str(e)}


def _macos_service_info(service: str) -> dict:
    """Fallback para macOS: verifica processo por nome."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", service],
            capture_output=True, timeout=5,
        )
        active = result.returncode == 0
        return {
            "ActiveState": "active" if active else "inactive",
            "SubState": "running" if active else "dead",
            "NRestarts": "0",
        }
    except Exception:
        return {"ActiveState": "unknown", "NRestarts": "0"}


def systemctl_restart(service: str) -> bool:
    """Reinicia um service. Retorna True se bem-sucedido."""
    if not _has_systemctl():
        # macOS: tenta openclaw gateway restart se for o gateway
        if service == "openclaw-gateway":
            try:
                subprocess.run(["openclaw", "gateway", "restart"],
                               capture_output=True, timeout=30)
                return True
            except Exception:
                return False
        return False
    try:
        result = subprocess.run(
            ["systemctl", "restart", service],
            capture_output=True, timeout=60,
        )
        return result.returncode == 0
    except Exception:
        return False


def systemctl_stop(service: str) -> bool:
    """Para um service."""
    if not _has_systemctl():
        return False
    try:
        result = subprocess.run(
            ["systemctl", "stop", service],
            capture_output=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_journal_errors(service: str, minutes: int = 60) -> list[str]:
    """Extrai últimas linhas de erro do journal do service."""
    if not _has_systemctl():
        # Fallback: lê log local
        log_file = Path.home() / ".agente-cfo" / "logs" / f"{service.replace('cfo-','')}.log"
        if log_file.exists():
            try:
                return subprocess.run(
                    ["tail", "-20", str(log_file)],
                    capture_output=True, text=True,
                ).stdout.splitlines()[-5:]
            except Exception:
                return []
        return []
    try:
        result = subprocess.run(
            ["journalctl", "-u", service, "--since", f"{minutes} minutes ago",
             "-p", "err", "-n", "10", "--no-pager"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip().splitlines()
    except Exception:
        return []


# ── Diagnóstico por tipo de serviço ──────────────────────────────────────────

def diagnose_openclaw_gateway() -> str:
    """Diagnostica por que o openclaw-gateway falhou."""
    errors = get_journal_errors("openclaw-gateway", minutes=10)
    error_text = " ".join(errors).lower()

    if "invalid config" in error_text or "config" in error_text or "json" in error_text:
        return "config_invalid"
    if "port" in error_text and ("bind" in error_text or "use" in error_text):
        return "port_conflict"
    if "token" in error_text or "auth" in error_text:
        return "auth_error"
    return "unknown"


def recover_openclaw_gateway(state: dict) -> bool:
    """
    Tenta recuperar openclaw-gateway:
    1. Se config inválida → auto_rollback.sh + restart
    2. Outros → restart simples
    """
    rollback_script = WORKSPACE / "auto_rollback.sh"
    diagnosis = diagnose_openclaw_gateway()
    log(f"[recover] openclaw-gateway: diagnóstico = {diagnosis}")

    if diagnosis == "config_invalid" and rollback_script.exists():
        log("[recover] Tentando rollback do openclaw.json...")
        result = subprocess.run(
            ["bash", str(rollback_script)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            log(f"[recover] Rollback aplicado: {result.stdout.strip()[:100]}")
        elif result.returncode == 2:
            log("[recover] Config atual já é válida (resultado do rollback)")
        else:
            log(f"[recover] Rollback falhou: {result.stderr.strip()[:100]}")
            return False

    log("[recover] Reiniciando openclaw-gateway...")
    ok = systemctl_restart("openclaw-gateway")
    log(f"[recover] openclaw-gateway restart: {'OK' if ok else 'FALHOU'}")
    return ok


def recover_cloudflared(state: dict) -> bool:
    """Cloudflared: restart simples (URL nova detectada no próximo heartbeat)."""
    log("[recover] Reiniciando cloudflared-cfo...")
    ok = systemctl_restart("cloudflared-cfo")
    log(f"[recover] cloudflared-cfo restart: {'OK' if ok else 'FALHOU'}")
    return ok


# ── Cooldown inteligente ──────────────────────────────────────────────────────

def get_restart_count_in_window(service: str, window_hours: int, state: dict) -> int:
    """Conta quantas vezes o service foi reiniciado na janela de tempo dada."""
    key = f"restarts:{service}"
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=window_hours)).isoformat()
    events: list[str] = state.get(key, [])
    return sum(1 for e in events if e >= cutoff)


def record_restart(service: str, state: dict) -> None:
    """Registra um restart no state."""
    key = f"restarts:{service}"
    now_iso = datetime.now(timezone.utc).isoformat()
    events: list[str] = state.get(key, [])
    events.append(now_iso)
    # Limpa eventos > 48h (limpeza automática do state)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    state[key] = [e for e in events if e >= cutoff]


def is_paused(service: str, state: dict) -> bool:
    """Retorna True se o serviço está em pausa de restart."""
    pause_until = state.get(f"pause_until:{service}")
    if not pause_until:
        return False
    try:
        pause_dt = datetime.fromisoformat(pause_until)
        return datetime.now(timezone.utc) < pause_dt
    except Exception:
        return False


def pause_service_restarts(service: str, minutes: int, state: dict) -> None:
    """Pausa restarts automáticos de um service por N minutos."""
    until = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    state[f"pause_until:{service}"] = until
    log(f"[cooldown] {service} pausado por {minutes}min (até {until})")


# ── Publicação de métricas ────────────────────────────────────────────────────

def emit_health_metric(service: str, healthy: bool) -> None:
    """Emite daemon_health metric via metric_emit.sh."""
    emit_script = WORKSPACE / "metric_emit.sh"
    if not emit_script.exists():
        return
    try:
        subprocess.run(
            ["bash", str(emit_script),
             "daemon.health", "1" if healthy else "0",
             json.dumps({"daemon": service})],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


# ── Notificação de alerta ─────────────────────────────────────────────────────

def send_alert_notification(message: str) -> None:
    """Envia notificação de alerta via event endpoint do painel."""
    panel_base = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    if not panel_base or not panel_token:
        return
    try:
        body = json.dumps({
            "type": "health_alert",
            "payload": {"message": message},
        }).encode()
        req = urllib.request.Request(
            f"{panel_base}/event",
            data=body,
            headers={"X-Panel-Token": panel_token, "Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ── Ciclo de saúde ────────────────────────────────────────────────────────────

def check_service(service: str, state: dict) -> str:
    """
    Avalia saúde de um service e aplica recovery se necessário.
    Retorna: "healthy" | "unhealthy" | "recovering" | "paused" | "stopped"
    """
    info = systemctl_show(service)
    active_state = info.get("ActiveState", "unknown")
    n_restarts_raw = info.get("NRestarts", "0")

    # Parse NRestarts (pode ser "0" ou falhar)
    try:
        n_restarts = int(n_restarts_raw)
    except ValueError:
        n_restarts = 0

    is_active = active_state == "active"

    # Conta restarts na janela de 1h (nosso rastreamento próprio, mais preciso)
    restarts_1h = get_restart_count_in_window(service, 1, state)
    restarts_24h = get_restart_count_in_window(service, 24, state)

    # Determina saúde
    unhealthy = (
        not is_active
        or n_restarts > RESTART_LIMIT_HOUR
        or restarts_1h > RESTART_LIMIT_HOUR
    )

    if not unhealthy:
        emit_health_metric(service, True)
        return "healthy"

    log(f"[health] {service} UNHEALTHY: active={is_active} n_restarts={n_restarts} "
        f"restarts_1h={restarts_1h} restarts_24h={restarts_24h}")

    # Verifica se deve parar por limite diário
    if restarts_24h > RESTART_LIMIT_DAY:
        msg = (f"🔴 {service} atingiu limite de {RESTART_LIMIT_DAY} restarts em 24h. "
               f"DESATIVADO — verifique os logs manualmente.")
        log(f"[health] {msg}")
        if service not in {"cfo-health-doctor"}:  # nunca para a si mesmo
            systemctl_stop(service)
            send_alert_notification(msg)
        emit_health_metric(service, False)
        return "stopped"

    # Verifica pausa ativa
    if is_paused(service, state):
        log(f"[health] {service} em pausa de restart (cooldown ativo)")
        emit_health_metric(service, False)
        return "paused"

    # Serviços que devem ser PARADOS (wacli legacy)
    if service in STOP_IF_UNHEALTHY:
        log(f"[health] {service} unhealthy → PARANDO (serviço legado, não recupera)")
        systemctl_stop(service)
        emit_health_metric(service, False)
        return "stopped"

    # Auto-recovery para services específicos
    if service in AUTO_RECOVERY_SERVICES:
        # Pausa antes de tentar recovery (evita storm)
        if restarts_1h >= RESTART_LIMIT_HOUR:
            pause_service_restarts(service, PAUSE_RESTART_MIN, state)
            send_alert_notification(
                f"⚠️ {service}: muitos restarts ({restarts_1h}x/h). "
                f"Pausando {PAUSE_RESTART_MIN}min antes de tentar recovery."
            )

        recovered = False
        if service == "openclaw-gateway":
            recovered = recover_openclaw_gateway(state)
        elif service == "cloudflared-cfo":
            recovered = recover_cloudflared(state)

        if recovered:
            record_restart(service, state)
            send_alert_notification(
                f"✅ {service}: auto-recovery aplicado e reiniciado."
            )

        emit_health_metric(service, recovered)
        return "recovering" if recovered else "unhealthy"

    # Outros: só alerta, não toca
    errors = get_journal_errors(service, minutes=5)
    error_summary = " | ".join(errors[-2:]) if errors else "sem logs de erro recentes"
    msg = (f"⚠️ {service} unhealthy ({active_state}). "
           f"Erros: {error_summary[:150]}. "
           f"Intervenção manual necessária.")
    log(f"[health] {msg}")
    send_alert_notification(msg)
    emit_health_metric(service, False)
    return "unhealthy"


def health_cycle() -> None:
    """Ciclo completo de verificação de saúde."""
    state = load_state()
    results: dict[str, str] = {}

    for service in MONITORED_SERVICES:
        try:
            status = check_service(service, state)
            results[service] = status
        except Exception as e:
            log(f"[health] Erro verificando {service}: {e}")
            results[service] = "error"

    save_state(state)

    healthy_count = sum(1 for s in results.values() if s == "healthy")
    total = len(results)
    log(f"[health] {healthy_count}/{total} services healthy | "
        + ", ".join(f"{svc}={st}" for svc, st in results.items() if st != "healthy"))


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()
    log("health_doctor.py started (Sprint 44 — auto-recovery)")
    log(f"Intervalo: {INTERVAL_S}s | Restart limit/h: {RESTART_LIMIT_HOUR} | /24h: {RESTART_LIMIT_DAY}")

    while True:
        log("--- Início do ciclo health-doctor ---")
        try:
            health_cycle()
        except Exception as e:
            log(f"[main] Erro: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    run_loop()
