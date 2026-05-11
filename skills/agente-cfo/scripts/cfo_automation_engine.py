#!/usr/bin/env python3
"""
cfo_automation_engine.py — Daemon do Automation Engine do Agente CFO.

Roda em loop a cada AUTOMATION_ENGINE_INTERVAL_MIN (default 5 min).
A cada ciclo:
  1. Busca automações ativas no Supabase
  2. Expira runs pending_confirm > 24h
  3. Avalia triggers (cron, metric, manual)
  4. Cria runs e solicita confirmação ou executa diretamente
  5. Detecta runs com status=running e executa-os

Logs: ~/.agente-cfo/logs/automation-engine.log
State: ~/.agente-cfo/state/automation_engine.json
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE = Path.home() / ".agente-cfo" / ".env"
STATE_FILE = Path.home() / ".agente-cfo" / "state" / "automation_engine.json"
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "automation-engine.log"
CONFIRM_TOKEN_FILE = Path.home() / ".agente-cfo" / "state" / "pending_confirm_token.txt"

INTERVAL_MINUTES = int(os.environ.get("AUTOMATION_ENGINE_INTERVAL_MIN", "5"))
INTERVAL_SECONDS = INTERVAL_MINUTES * 60


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
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ── State management ──────────────────────────────────────────────────────────

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


# ── Supabase REST helper ─────────────────────────────────────────────────────

def supabase_request(method: str, path: str, body: dict | list | None = None,
                     params: dict | None = None) -> Any:
    """
    Chama a Supabase REST API usando urllib (sem dependências externas).
    Base: {SUPABASE_URL}/rest/v1/{path}
    """
    supabase_url = os.environ.get("SUPABASE_URL", os.environ.get("PANEL_BASE_URL", ""))
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supabase_url or not service_key:
        log("[supabase] SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY não configurados")
        return None

    # Normaliza base URL: remove /functions/v1 se presente
    base = supabase_url.replace("/functions/v1", "")
    url = f"{base}/rest/v1/{path}"

    if params:
        query_parts = []
        for k, v in params.items():
            query_parts.append(f"{k}={v}")
        url += "?" + "&".join(query_parts)

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    data = None
    if body is not None:
        data = json.dumps(body, default=str).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            response_body = resp.read().decode()
            if response_body:
                return json.loads(response_body)
            return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:300]
        log(f"[supabase] HTTP {e.code} {method} {path}: {error_body}")
        return None
    except Exception as e:
        log(f"[supabase] Erro {method} {path}: {e}")
        return None


# ── Cron evaluation ──────────────────────────────────────────────────────────

def should_run_cron(expr: str, last_run_at: str | None) -> bool:
    """
    Retorna True se a expressão cron deveria ter disparado desde last_run_at.
    Timezone: America/Sao_Paulo (UTC-3 aproximação).
    """
    now = datetime.now(timezone.utc)

    if last_run_at:
        try:
            last = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            last = now - timedelta(hours=24)
    else:
        last = now - timedelta(hours=24)

    try:
        import croniter
        cron = croniter.croniter(expr, last)
        next_run = cron.get_next(datetime)
        return next_run <= now
    except ImportError:
        return _simple_cron_check(expr, last, now)


def _simple_cron_check(expr: str, last: datetime, now: datetime) -> bool:
    """Fallback: parser simples para padrões cron comuns."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return False

    minute, hour, dom, month, dow = parts
    tz_offset = timedelta(hours=-3)  # America/Sao_Paulo aproximação
    now_local = now + tz_offset
    last_local = last + tz_offset

    # */N * * * * — every N minutes
    if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
        try:
            n = int(minute[2:])
            elapsed = (now - last).total_seconds() / 60
            return elapsed >= n
        except ValueError:
            return False

    # 0 H * * * — daily at hour H
    if dom == "*" and month == "*" and dow == "*":
        try:
            target_minute = int(minute)
            target_hour = int(hour)
            target_today = now_local.replace(
                hour=target_hour, minute=target_minute, second=0, microsecond=0
            )
            target_yesterday = target_today - timedelta(days=1)

            # Verifica se o target de hoje ou ontem está entre last e now
            for target in [target_today, target_yesterday]:
                if last_local < target <= now_local:
                    return True
            return False
        except ValueError:
            return False

    # 0 H * * W — weekly on weekday W (0=Sun, 1=Mon, ..., 6=Sat)
    if dom == "*" and month == "*" and dow != "*":
        try:
            target_minute = int(minute)
            target_hour = int(hour)
            target_dow = int(dow)
            # Python: Monday=0, Sunday=6; cron: Sunday=0, Monday=1
            # Converter cron DOW para Python DOW
            python_dow = (target_dow - 1) % 7 if target_dow > 0 else 6

            # Verificar últimos 7 dias
            for days_back in range(8):
                check_day = now_local - timedelta(days=days_back)
                if check_day.weekday() == python_dow:
                    target_time = check_day.replace(
                        hour=target_hour, minute=target_minute, second=0, microsecond=0
                    )
                    if last_local < target_time <= now_local:
                        return True
            return False
        except ValueError:
            return False

    return False


# ── Metric evaluation ────────────────────────────────────────────────────────

def should_run_metric(trigger: dict, automation: dict) -> bool:
    """
    Busca o snapshot do dashboard e compara o KPI com o threshold.
    Cooldown: 24h para evitar spam.
    """
    state = load_state()
    cooldown_key = f"metric_cooldown:{automation['id']}"
    last_fired = state.get(cooldown_key)
    if last_fired:
        try:
            last_dt = datetime.fromisoformat(last_fired.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < 86400:
                return False
        except (ValueError, TypeError):
            pass

    metric_name = trigger.get("metric", "balance_brl")
    operator = trigger.get("operator", "lt")
    threshold = float(trigger.get("value", 0))

    snapshot = get_latest_snapshot()
    if not snapshot:
        return False

    kpis = snapshot.get("kpis", {})
    try:
        value = float(kpis.get(metric_name, 0))
    except (ValueError, TypeError):
        return False

    ops = {
        "lt": value < threshold, "lte": value <= threshold,
        "gt": value > threshold, "gte": value >= threshold,
        "eq": value == threshold, "neq": value != threshold,
    }
    result = ops.get(operator, False)

    if result:
        state[cooldown_key] = datetime.now(timezone.utc).isoformat()
        save_state(state)

    return result


def get_latest_snapshot() -> dict | None:
    """Tenta ler da tabela dashboard_snapshots via Supabase REST API."""
    result = supabase_request(
        "GET", "dashboard_snapshots",
        params={"select": "*", "order": "created_at.desc", "limit": "1"},
    )
    if result and isinstance(result, list) and len(result) > 0:
        return result[0]
    return None


# ── Confirmation logic ───────────────────────────────────────────────────────

ACTIONS_REQUIRING_CONFIRM = {
    "send_whatsapp",
    "crm_update_deal",
    "erp_create_invoice",
    "cobranca_send",
    "ai_decide",
}


def compute_needs_confirmation(automation: dict) -> bool:
    """Decide se a automação precisa de confirmação do dono."""
    # Override explícito do usuário
    if automation.get("require_confirmation") is not None:
        return bool(automation["require_confirmation"])

    for action in automation.get("actions", []):
        atype = action.get("type", "")
        if atype in ACTIONS_REQUIRING_CONFIRM:
            if atype == "send_whatsapp" and action.get("to", "") == "owner":
                continue
            return True
    return False


# ── Run management ───────────────────────────────────────────────────────────

def schedule_run(automation: dict, trigger_payload: dict, needs_confirm: bool):
    """Cria um run no Supabase e solicita confirmação ou executa."""
    status = "pending_confirm" if needs_confirm else "running"
    run = supabase_request("POST", "automation_runs", body={
        "automation_id": automation["id"],
        "user_id": automation.get("user_id"),
        "status": status,
        "trigger_payload": trigger_payload,
        "steps": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    run_id = None
    confirm_token = None
    if run and isinstance(run, list) and len(run) > 0:
        run_id = run[0].get("id")
        confirm_token = run[0].get("confirmation_token")

    if not run_id:
        log(f"[schedule] Falha ao criar run para automação {automation['id']}")
        return

    # Atualiza last_run_at
    supabase_request("PATCH", f"automations?id=eq.{automation['id']}", body={
        "last_run_at": datetime.now(timezone.utc).isoformat(),
    })

    if needs_confirm:
        send_confirmation_request(automation, run_id, confirm_token or "")
    else:
        execute_automation_run(automation, run_id)


def send_confirmation_request(automation: dict, run_id: int, confirm_token: str):
    """Envia pedido de confirmação via WhatsApp."""
    actions_summary = ", ".join(a.get("type", "?") for a in automation.get("actions", []))
    msg = (
        f"\U0001f916 *Marcos*: vou executar *{automation.get('name', '?')}*.\n"
        f"Ações: {actions_summary}\n"
        f"Confirma? Responde *SIM* ou *NÃO*.\n"
        f"[confirm:{confirm_token}]"
    )

    scripts_dir = Path(__file__).parent
    try:
        subprocess.run(
            ["bash", str(scripts_dir / "_send_whatsapp.sh"), msg],
            capture_output=True, timeout=30,
        )
    except Exception as e:
        log(f"[confirm] Erro enviando WhatsApp: {e}")

    # Salva token pendente para wacli_inbound capturar reply
    try:
        CONFIRM_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIRM_TOKEN_FILE.write_text(confirm_token)
    except Exception as e:
        log(f"[confirm] Erro salvando token pendente: {e}")

    emit_panel_event("automation_confirmation_request", {
        "run_id": run_id,
        "automation_name": automation.get("name", ""),
        "confirm_token": confirm_token,
    })


def execute_automation_run(automation: dict, run_id: int):
    """Executa todas as ações de uma automação."""
    # Importa o registry de ações
    scripts_dir = str(Path(__file__).parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from automation_actions import ACTION_REGISTRY, load_all
    load_all()

    run_context = {
        "automation_id": automation["id"],
        "run_id": run_id,
        "user_id": automation.get("user_id", ""),
        "scripts_dir": scripts_dir,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "env": dict(os.environ),
    }

    steps = []
    overall_success = True

    for action_spec in automation.get("actions", []):
        atype = action_spec.get("type", "")
        step: dict[str, Any] = {
            "action_type": atype,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            action_cls = ACTION_REGISTRY.get(atype)
            if not action_cls:
                raise ValueError(f"Tipo de ação desconhecido: {atype}")
            result = action_cls().execute(action_spec, run_context)
            step["status"] = "succeeded" if result.get("success") else "failed"
            step["output"] = result.get("output", {})
            step["error"] = result.get("error")
            if not result.get("success"):
                overall_success = False
        except Exception as e:
            step["status"] = "failed"
            step["error"] = str(e)
            overall_success = False

        step["finished_at"] = datetime.now(timezone.utc).isoformat()
        steps.append(step)

        # Fail-fast
        if step["status"] == "failed":
            break

    # Atualiza run
    supabase_request("PATCH", f"automation_runs?id=eq.{run_id}", body={
        "status": "succeeded" if overall_success else "failed",
        "steps": steps,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "result": {"steps_count": len(steps), "success": overall_success},
    })

    log(f"Run {run_id} {'succeeded' if overall_success else 'failed'} ({len(steps)} steps)")


# ── Panel events ─────────────────────────────────────────────────────────────

def emit_panel_event(event_type: str, payload: dict) -> None:
    """Emite evento para o painel via Supabase REST ou curl."""
    panel_url = os.environ.get("PANEL_BASE_URL", "")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    instance_id = os.environ.get("INSTANCE_ID", "")

    if not all([panel_url, panel_token, instance_id]):
        return

    event_payload = json.dumps({
        "instance_id": instance_id,
        "type": event_type,
        "payload": payload,
    }, default=str)

    try:
        subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", "10", "-X", "POST", f"{panel_url}/event",
             "-H", "Content-Type: application/json",
             "-H", f"X-Panel-Token: {panel_token}",
             "-d", event_payload],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as e:
        log(f"[panel] Erro ao emitir evento {event_type}: {e}")


# ── Expire old runs ──────────────────────────────────────────────────────────

def expire_old_runs():
    """Marca runs pending_confirm > 24h como expired."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    supabase_request(
        "PATCH",
        f"automation_runs?status=eq.pending_confirm&started_at=lt.{cutoff}",
        body={
            "status": "expired",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


# ── Process pending running runs ─────────────────────────────────────────────

def process_running_runs():
    """Detecta runs com status=running que ainda não foram executados e executa."""
    runs = supabase_request(
        "GET", "automation_runs",
        params={
            "status": "eq.running",
            "finished_at": "is.null",
            "select": "*",
        },
    )
    if not runs or not isinstance(runs, list):
        return

    for run in runs:
        automation_id = run.get("automation_id")
        run_id = run.get("id")
        if not automation_id or not run_id:
            continue

        # Busca automação
        automations = supabase_request(
            "GET", "automations",
            params={"id": f"eq.{automation_id}", "select": "*"},
        )
        if not automations or not isinstance(automations, list) or len(automations) == 0:
            log(f"[running] Automação {automation_id} não encontrada para run {run_id}")
            continue

        automation = automations[0]
        log(f"[running] Executando run {run_id} (automação: {automation.get('name', '?')})")
        execute_automation_run(automation, run_id)


# ── Automation evaluation ────────────────────────────────────────────────────

def evaluate_automation(automation: dict):
    """Avalia se a automação deve ser disparada neste ciclo."""
    trigger = automation.get("trigger", {})
    ttype = trigger.get("type", "manual")

    if ttype == "cron":
        if not should_run_cron(trigger.get("expression", ""), automation.get("last_run_at")):
            return
    elif ttype == "metric":
        if not should_run_metric(trigger, automation):
            return
    elif ttype == "manual":
        return  # Só via run-now

    needs_confirm = compute_needs_confirmation(automation)
    schedule_run(automation, trigger_payload=trigger, needs_confirm=needs_confirm)


# ── Main cycle ───────────────────────────────────────────────────────────────

def cycle():
    """Executa um ciclo do engine."""
    # 1. Busca automações ativas
    automations = supabase_request(
        "GET", "automations",
        params={"active": "eq.true", "select": "*"},
    )

    if not automations or not isinstance(automations, list):
        log("[cycle] Nenhuma automação ativa encontrada (ou erro na consulta)")
        automations = []

    # 2. Expira runs pendentes > 24h
    expire_old_runs()

    # 3. Processa runs com status=running (confirmados pelo dono)
    process_running_runs()

    # 4. Avalia cada automação
    for automation in automations:
        try:
            evaluate_automation(automation)
        except Exception as e:
            log(f"[cycle] Erro avaliando automação {automation.get('id', '?')}: {e}")


def run_loop():
    """Loop principal do daemon."""
    load_env()
    log("cfo_automation_engine.py started")
    log(f"Intervalo de polling: {INTERVAL_MINUTES} minutos")

    while True:
        log("--- Início do ciclo automation engine ---")
        try:
            cycle()
            log("--- Ciclo concluído ---")
        except Exception as e:
            log(f"[main] Erro no ciclo: {e}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_loop()
