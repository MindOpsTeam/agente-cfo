#!/usr/bin/env python3
"""
cfo_automation_engine.py — Daemon do Automation Engine do Agente CFO.

Sprint 19: sem SUPABASE_SERVICE_ROLE_KEY na VPS.
Todas as consultas e escritas ao Supabase são feitas via edge functions
autenticadas com X-Panel-Token + X-Hooks-Token.

Roda em loop a cada AUTOMATION_ENGINE_INTERVAL_MIN (default 5 min).
A cada ciclo:
  1. Chama edge function automations-engine-poll → lista o que precisa executar
  2. Para cada item em `scheduled`: executa (ou solicita confirmação)
  3. Para cada run em `pending_runs`: expira (marca como expired via record-run)
  4. Para cada run em `running_runs`: executa as ações

Envs obrigatórias:
  PANEL_BASE_URL   — URL base das edge functions, ex: https://xxx.supabase.co/functions/v1
  PANEL_TOKEN      — X-Panel-Token
  HOOKS_TOKEN      — X-Hooks-Token

Envs opcionais:
  AUTOMATION_ENGINE_INTERVAL_MIN  — intervalo entre ciclos (default 5)

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
from datetime import datetime, timezone
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


# ── Edge function helpers ─────────────────────────────────────────────────────

def _edge_headers() -> dict:
    return {
        "X-Panel-Token": os.environ["PANEL_TOKEN"],
        "X-Hooks-Token": os.environ["HOOKS_TOKEN"],
        "Content-Type": "application/json",
    }


def _panel_base() -> str:
    return os.environ["PANEL_BASE_URL"].rstrip("/")


def poll() -> dict:
    """
    Chama GET /automations-engine-poll.
    Retorna { scheduled: [...], pending_runs: [...], running_runs: [...] }
    """
    url = f"{_panel_base()}/automations-engine-poll"
    req = urllib.request.Request(url, headers=_edge_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            log(
                f"[poll] scheduled={len(data.get('scheduled', []))} "
                f"pending_runs={len(data.get('pending_runs', []))} "
                f"running_runs={len(data.get('running_runs', []))}"
            )
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"[poll] HTTP {e.code}: {body}")
        return {}
    except Exception as e:
        log(f"[poll] Erro: {e}")
        return {}


def record_run(run: dict, update_last_run: bool = False) -> dict:
    """
    Chama POST /automations-engine-record-run.
    - Se run["id"] está presente → UPDATE.
    - Caso contrário → INSERT (retorna run_id).
    Retorna { run_id } ou {} em caso de erro.
    """
    url = f"{_panel_base()}/automations-engine-record-run"
    payload = json.dumps(
        {"run": run, "update_automation_last_run": update_last_run},
        default=str,
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=_edge_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        log(f"[record_run] HTTP {e.code}: {body}")
        return {}
    except Exception as e:
        log(f"[record_run] Erro: {e}")
        return {}


# ── Panel events ─────────────────────────────────────────────────────────────

def emit_panel_event(event_type: str, payload: dict) -> None:
    """Emite evento para o painel via edge function /event."""
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
    if automation.get("require_confirmation") is not None:
        return bool(automation["require_confirmation"])
    for action in automation.get("actions", []):
        atype = action.get("type", "")
        if atype in ACTIONS_REQUIRING_CONFIRM:
            if atype == "send_whatsapp" and action.get("to", "") == "owner":
                continue
            return True
    return False


# ── Execute automation ────────────────────────────────────────────────────────

def execute_automation(automation: dict, reason: str) -> None:
    """
    Avalia se a automação precisa de confirmação e cria/executa o run.
    Chamado para itens do payload.scheduled.
    """
    needs_confirm = compute_needs_confirmation(automation)

    # 1. Cria o run (INSERT) via edge function
    run = {
        "automation_id": automation["id"],
        "user_id": automation.get("user_id"),
        "status": "pending_confirm" if needs_confirm else "running",
        "trigger_payload": {"reason": reason},
        "steps": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = record_run(run, update_last_run=True)
    run_id = resp.get("run_id")

    if not run_id:
        log(f"[execute] Falha ao criar run para automação {automation.get('id')}")
        return

    run["id"] = run_id

    if needs_confirm:
        _send_confirmation_request(automation, run_id)
    else:
        _execute_run_actions(automation, run)


def _send_confirmation_request(automation: dict, run_id: int) -> None:
    """Envia pedido de confirmação via WhatsApp e emite evento no painel."""
    actions_summary = ", ".join(a.get("type", "?") for a in automation.get("actions", []))
    # A edge function automation-confirm gera o confirmation_token; precisamos buscá-lo.
    # Para compatibilidade: o wacli_inbound usa o run_id como referência.
    msg = (
        f"\U0001f916 *Marcos*: vou executar *{automation.get('name', '?')}*.\n"
        f"Ações: {actions_summary}\n"
        f"Confirma? Responde *SIM* ou *NÃO*.\n"
        f"[run:{run_id}]"
    )

    scripts_dir = Path(__file__).parent
    try:
        subprocess.run(
            ["bash", str(scripts_dir / "_send_whatsapp.sh"), msg],
            capture_output=True, timeout=30,
        )
    except Exception as e:
        log(f"[confirm] Erro enviando WhatsApp: {e}")

    emit_panel_event("automation_confirmation_request", {
        "run_id": run_id,
        "automation_name": automation.get("name", ""),
    })


def _execute_run_actions(automation: dict, run: dict) -> None:
    """Executa as ações de uma automação e atualiza o run via record_run."""
    run_id = run.get("id")
    scripts_dir = str(Path(__file__).parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from automation_actions import ACTION_REGISTRY, load_all  # type: ignore
    load_all()

    run_context = {
        "automation_id": automation["id"],
        "run_id": run_id,
        "user_id": automation.get("user_id", ""),
        "scripts_dir": scripts_dir,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "env": dict(os.environ),
    }

    steps: list[dict[str, Any]] = []
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

        if step["status"] == "failed":
            break

    # 2. Atualiza o run via edge function (UPDATE)
    finished_run = {
        "id": run_id,
        "automation_id": automation["id"],
        "status": "succeeded" if overall_success else "failed",
        "steps": steps,
        "started_at": run.get("started_at", datetime.now(timezone.utc).isoformat()),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "result": {"steps_count": len(steps), "success": overall_success},
    }
    record_run(finished_run, update_last_run=True)
    log(f"[execute] Run {run_id} {'succeeded' if overall_success else 'failed'} ({len(steps)} steps)")


# ── Handle confirmed runs (running_runs) ─────────────────────────────────────

def handle_running_run(run_row: dict) -> None:
    """
    Detecta run com status=running (confirmado pelo dono via automation-confirm)
    e executa as ações correspondentes.
    """
    run_id = run_row.get("id")
    automation_id = run_row.get("automation_id")
    if not run_id or not automation_id:
        return

    # Precisamos do objeto da automação — ele veio embedded no run ou buscamos via poll?
    # O poll não retorna running_runs com a automação inline. Fazemos um poll específico
    # buscando a automação pelo id via qualquer run recente.
    # Como não queremos SUPABASE REST, vamos incluir a automação no running_runs
    # (futuro: o poll já embute). Por ora, o run_row pode não ter a automação.
    # Workaround: reutilizamos poll() que também retorna scheduled — se a automação
    # já foi encontrada e está em running_runs, o payload do run_row tem automation_id.
    # Chamamos record_run com status=failed se não conseguirmos a automação.

    automation = run_row.get("automation")  # Se vier embedded no futuro
    if not automation:
        # Busca automação: como não temos REST direto, precisamos de outro jeito.
        # A edge function poll retorna running_runs mas sem automation embedded.
        # Solução: adicionar um campo "automation" ao running_runs na edge function
        # OU aceitar que handle_running_run vai ser chamado apenas quando
        # a edge function retornar o objeto da automação.
        # Por ora: loga e retorna, esperando melhoria futura.
        log(f"[running] Automação não encontrada para run {run_id} "
            f"(automation_id={automation_id}). "
            f"Aguardando próximo ciclo com automação embedded.")
        return

    log(f"[running] Executando run {run_id} (automação: {automation.get('name', '?')})")
    # Monta run dict com id para que _execute_run_actions faça UPDATE
    run = {
        "id": run_id,
        "automation_id": automation_id,
        "started_at": run_row.get("started_at", datetime.now(timezone.utc).isoformat()),
    }
    _execute_run_actions(automation, run)


# ── Expire pending_runs ──────────────────────────────────────────────────────

def expire_pending_run(run_row: dict) -> None:
    """Marca um run pending_confirm > 24h como expired via record_run."""
    run_id = run_row.get("id")
    automation_id = run_row.get("automation_id")
    if not run_id or not automation_id:
        return

    expired_run = {
        "id": run_id,
        "automation_id": automation_id,
        "status": "expired",
        "started_at": run_row.get("started_at", datetime.now(timezone.utc).isoformat()),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    record_run(expired_run, update_last_run=False)
    log(f"[expire] Run {run_id} expirado (pending_confirm > 24h)")


# ── Main cycle ───────────────────────────────────────────────────────────────

def cycle() -> None:
    """Executa um ciclo do engine."""
    payload = poll()

    if not payload:
        log("[cycle] Poll retornou vazio ou erro")
        return

    # 1. Expira runs pending_confirm > 24h
    for run_row in payload.get("pending_runs", []):
        try:
            expire_pending_run(run_row)
        except Exception as e:
            log(f"[cycle] Erro expirando run {run_row.get('id')}: {e}")

    # 2. Executa runs confirmados pelo dono (status=running, finished_at=null)
    for run_row in payload.get("running_runs", []):
        try:
            handle_running_run(run_row)
        except Exception as e:
            log(f"[cycle] Erro executando running run {run_row.get('id')}: {e}")

    # 3. Executa automações agendadas pelo engine (cron/metric)
    for item in payload.get("scheduled", []):
        try:
            execute_automation(item["automation"], item["reason"])
        except Exception as e:
            log(f"[cycle] Erro executando automação {item.get('automation_id')}: {e}")


def run_loop() -> None:
    """Loop principal do daemon."""
    load_env()

    # Valida envs obrigatórias
    for env_key in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN"):
        if not os.environ.get(env_key):
            log(f"[startup] ERRO: variável de ambiente '{env_key}' não configurada. Abortando.")
            sys.exit(1)

    log("cfo_automation_engine.py started (Sprint 19 — sem service_role)")
    log(f"Intervalo de polling: {INTERVAL_MINUTES} minutos")
    log(f"Panel base URL: {os.environ['PANEL_BASE_URL']}")

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
