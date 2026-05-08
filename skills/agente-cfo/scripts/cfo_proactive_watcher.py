#!/usr/bin/env python3
"""
cfo_proactive_watcher.py — Daemon de detecção de anomalias do Agente CFO.

Roda em loop a cada POLL_INTERVAL_MINUTES (default 30 min).
A cada ciclo:
  1. Carrega ERP client (agnóstico: omie, bling, tiny, etc.) e CRM client (se configurado)
  2. Executa todas as regras em proactive_rules/
  3. Filtra alertas por cooldown (state em ~/.agente-cfo/state/proactive_alerts.json)
  4. Dispara POST /hooks/agent para cada novo alerta (name=proactive_alert)
  5. Emite _panel_event "proactive_alert" para o painel
  6. Persiste state atualizado

Governance: daemon é 100% read-only — nenhuma write nos ERPs/CRMs.

Logs: ~/.agente-cfo/logs/proactive.log
State: ~/.agente-cfo/state/proactive_alerts.json
"""
import importlib
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
STATE_FILE = Path.home() / ".agente-cfo" / "state" / "proactive_alerts.json"
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "proactive.log"
SKILLS_ROOT = Path.home() / ".openclaw" / "workspace" / "skills"

POLL_INTERVAL_MINUTES = int(os.environ.get("CFO_PROACTIVE_INTERVAL_MINUTES", "30"))


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


def is_in_cooldown(rule_name: str, dedup_key: str, cooldown_hours: int, state: dict) -> bool:
    """Retorna True se o alerta ainda está dentro do cooldown."""
    rule_state = state.get(rule_name, {})
    alerts_sent = rule_state.get("alerts_sent", [])
    now = datetime.now(timezone.utc)
    for entry in alerts_sent:
        if entry.get("dedup_key") != dedup_key:
            continue
        try:
            sent_at = datetime.fromisoformat(entry["sent_at"])
        except (KeyError, ValueError):
            continue
        elapsed_hours = (now - sent_at).total_seconds() / 3600
        if elapsed_hours < cooldown_hours:
            return True
    return False


def record_alert_sent(rule_name: str, dedup_key: str, state: dict) -> None:
    """Registra que um alerta foi enviado agora."""
    if rule_name not in state:
        state[rule_name] = {"alerts_sent": []}
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state[rule_name]["alerts_sent"].append({
        "dedup_key": dedup_key,
        "sent_at": now_iso,
    })
    # Limitar histórico a 200 entradas por regra
    state[rule_name]["alerts_sent"] = state[rule_name]["alerts_sent"][-200:]


# ── ERP/CRM client loader ─────────────────────────────────────────────────────

def _load_client(skill_name: str, base_class_name: str) -> Any | None:
    """
    Carrega dinamicamente o client de uma skill do monorepo.
    Retorna None se a skill não estiver instalada ou as credenciais faltarem.
    """
    if not skill_name or skill_name == "nenhum":
        return None

    skill_dir = SKILLS_ROOT / skill_name / "scripts"
    if not skill_dir.exists():
        log(f"[loader] Skill '{skill_name}' não encontrada em {skill_dir}")
        return None

    # Adicionar ao sys.path: skill scripts + _lib
    for p in [str(skill_dir), str(SKILLS_ROOT / "_lib")]:
        if p not in sys.path:
            sys.path.insert(0, p)

    # Convenção: omie → omie_client.py → OmieClient; bling → bling_client.py → BlingClient
    module_name = f"{skill_name}_client"
    class_name = skill_name.replace("-", "_").replace("_", " ").title().replace(" ", "") + "Client"

    try:
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        return cls()
    except ImportError as e:
        log(f"[loader] ImportError ao carregar {module_name}: {e}")
        return None
    except AttributeError as e:
        log(f"[loader] {class_name} não encontrado em {module_name}: {e}")
        return None
    except Exception as e:
        log(f"[loader] Erro ao instanciar {class_name}: {e}")
        return None


def load_erp_client() -> Any | None:
    erp_name = os.environ.get("CFO_ERP_NAME", "omie")
    client = _load_client(erp_name, "BaseERPClient")
    if client is not None:
        log(f"[loader] ERP client carregado: {erp_name}")
    else:
        log(f"[loader] ERP client '{erp_name}' indisponível — regras ERP serão puladas")
    return client


def load_crm_client() -> Any | None:
    crm_name = os.environ.get("CFO_CRM_NAME", "nenhum")
    if crm_name == "nenhum":
        return None
    client = _load_client(crm_name, "BaseCRMClient")
    if client is not None:
        log(f"[loader] CRM client carregado: {crm_name}")
    else:
        log(f"[loader] CRM client '{crm_name}' indisponível — regras CRM serão puladas")
    return client


# ── Rule loader ───────────────────────────────────────────────────────────────

RULE_MODULES = [
    ("proactive_rules.rule_overdue_critical",   "RuleOverdueCritical"),
    ("proactive_rules.rule_cash_low",            "RuleCashLow"),
    ("proactive_rules.rule_concentration",       "RuleConcentration"),
    ("proactive_rules.rule_inadimplencia_high",  "RuleInadimplenciaHigh"),
    ("proactive_rules.rule_deal_stale",          "RuleDealStale"),
    ("proactive_rules.rule_pipeline_drop",       "RulePipelineDrop"),
    ("proactive_rules.rule_erp_api_health",      "RuleERPApiHealth"),
]


def load_rules() -> list:
    rules = []
    scripts_dir = Path(__file__).parent
    rules_pkg_dir = scripts_dir / "proactive_rules"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    for module_path, class_name in RULE_MODULES:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            rules.append(cls())
        except Exception as e:
            log(f"[rules] Falha ao carregar {module_path}.{class_name}: {e}")
    return rules


# ── Dispatch to OpenClaw ──────────────────────────────────────────────────────

def dispatch_alert(alert: Any) -> bool:
    """POST /hooks/agent com o alerta. Retorna True se OK."""
    hooks_token = os.environ.get("HOOKS_TOKEN", "")
    hooks_url = "http://127.0.0.1:18789/hooks/agent"

    message = (
        f"[PROACTIVE_ALERT] rule={alert.rule_name} severity={alert.severity}\n"
        f"dedup_key={alert.dedup_key}\n\n"
        f"{alert.summary}\n\n"
        f"raw_data={json.dumps(alert.raw_data, ensure_ascii=False, default=str)}\n\n"
        f"Instrucoes: Leia prompts/proactive.md e envie uma mensagem curta e direta "
        f"para o dono via bash $SCRIPTS_DIR/_send_whatsapp.sh '$CFO_WHATSAPP_TO' '<msg>'. "
        f"Nao peca confirmacao — apenas informe. Máx 600 chars."
    )

    payload = json.dumps({
        "message": message,
        "name": "proactive_alert",
        "wakeMode": "now",
        "deliver": False,
        "timeoutSeconds": 180,
        "metadata": {
            "rule": alert.rule_name,
            "severity": alert.severity,
            "dedup_key": alert.dedup_key,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        hooks_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {hooks_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log(f"[dispatch] OK rule={alert.rule_name} key={alert.dedup_key} -> {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        log(f"[dispatch] HTTP {e.code} rule={alert.rule_name}: {body}")
        return False
    except Exception as e:
        log(f"[dispatch] Erro rule={alert.rule_name}: {e}")
        return False


def emit_panel_event(alert: Any) -> None:
    """Emite proactive_alert para o painel via curl (reutiliza lógica de _shared.sh)."""
    panel_url = os.environ.get("PANEL_BASE_URL", "")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    instance_id = os.environ.get("INSTANCE_ID", "")

    if not all([panel_url, panel_token, instance_id]):
        return

    payload = json.dumps({
        "instance_id": instance_id,
        "type": "proactive_alert",
        "severity": alert.severity,
        "payload": {
            "rule": alert.rule_name,
            "summary": alert.summary,
            "dedup_key": alert.dedup_key,
            "raw_data": alert.raw_data,
        },
    }, default=str)

    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", "10", "-X", "POST", f"{panel_url}/event",
             "-H", "Content-Type: application/json",
             "-H", f"X-Panel-Token: {panel_token}",
             "-d", payload],
            capture_output=True, text=True, timeout=15,
        )
        http_code = result.stdout.strip()
        if http_code not in ("200", "201"):
            log(f"[panel] proactive_alert HTTP {http_code} rule={alert.rule_name}")
    except Exception as e:
        log(f"[panel] Erro ao emitir evento: {e}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_cycle(rules: list, erp_client: Any, crm_client: Any, state: dict) -> int:
    """Executa um ciclo de detecção. Retorna número de alertas disparados."""
    dispatched = 0

    for rule in rules:
        try:
            alerts = rule.evaluate(erp_client, crm_client, state)
        except Exception as e:
            log(f"[cycle] Exceção em {rule.name}: {e}")
            continue

        for alert in alerts:
            if is_in_cooldown(rule.name, alert.dedup_key, rule.cooldown_hours, state):
                log(f"[cooldown] Ignorando {rule.name}/{alert.dedup_key} (cooldown {rule.cooldown_hours}h)")
                continue

            log(f"[alert] {rule.name} severity={alert.severity} key={alert.dedup_key}: {alert.summary[:80]}")

            if dispatch_alert(alert):
                record_alert_sent(rule.name, alert.dedup_key, state)
                emit_panel_event(alert)
                dispatched += 1
            else:
                log(f"[cycle] Dispatch falhou para {rule.name}/{alert.dedup_key} — não registrando cooldown")

    save_state(state)
    return dispatched


def run() -> None:
    load_env()
    log("cfo_proactive_watcher.py started")
    log(f"Intervalo de polling: {POLL_INTERVAL_MINUTES} minutos")

    rules = load_rules()
    log(f"Regras carregadas: {[r.name for r in rules]}")

    while True:
        log("--- Início do ciclo de detecção ---")
        state = load_state()

        erp_client = load_erp_client()
        crm_client = load_crm_client()

        try:
            n = run_cycle(rules, erp_client, crm_client, state)
            log(f"--- Ciclo concluído: {n} alerta(s) disparado(s) ---")
        except Exception as e:
            log(f"[main] Erro não capturado no ciclo: {e}")

        log(f"Aguardando {POLL_INTERVAL_MINUTES} minutos até o próximo ciclo...")
        time.sleep(POLL_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    run()
