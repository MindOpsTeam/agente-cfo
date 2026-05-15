#!/usr/bin/env python3
"""
evolution_sync.py — Daemon de sincronização Evolution API ↔ painel.

Sprint 27 — WhatsApp multi-instância via Evolution API.

Loop a cada EVOLUTION_SYNC_INTERVAL_S (default: 30s):
  1. Busca config da Evolution + lista de instâncias do painel
  2. Reconcilia: cria/deleta instâncias na Evolution conforme painel
  3. Sincroniza status (connected/disconnected/qr_pending) e QR codes
  4. Atualiza estado no painel via edge function

Edge functions consumidas (todas com X-Panel-Token + X-Hooks-Token):
  GET /evolution-config-vps        → { base_url, api_key, webhook_secret, active }
  GET /whatsapp-instances-vps-list → [{ id, instance_name, status, receives_marcos_chat }]
  POST /whatsapp-instances-vps-update → [{ id, status, qr_code_b64?, last_seen }]

Logs: ~/.agente-cfo/logs/evolution-sync.log
Env:  PANEL_BASE_URL, PANEL_TOKEN, HOOKS_TOKEN, EVOLUTION_SYNC_INTERVAL_S
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE  = Path.home() / ".agente-cfo" / ".env"
LOG_FILE  = Path.home() / ".agente-cfo" / "logs" / "evolution-sync.log"

INTERVAL_SECONDS = int(os.environ.get("EVOLUTION_SYNC_INTERVAL_S", "30"))


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


# ── Panel HTTP ────────────────────────────────────────────────────────────────

def _panel_headers() -> dict:
    return {
        "X-Panel-Token": os.environ["PANEL_TOKEN"],
        "X-Hooks-Token": os.environ["HOOKS_TOKEN"],
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _panel_base() -> str:
    return os.environ["PANEL_BASE_URL"].rstrip("/")


def _panel_get(path: str) -> Optional[Any]:
    url = f"{_panel_base()}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers=_panel_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception as e:
        log(f"[panel_get] Erro {path}: {e}")
        return None


def _panel_post(path: str, body: Any) -> Optional[Any]:
    url = f"{_panel_base()}/{path.lstrip('/')}"
    data = json.dumps(body, default=str).encode()
    req = urllib.request.Request(url, data=data, headers=_panel_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()[:200]
        log(f"[panel_post] HTTP {e.code} {path}: {body_txt}")
        return None
    except Exception as e:
        log(f"[panel_post] Erro {path}: {e}")
        return None


# Importa Any
# ── Fetch de config e instâncias ──────────────────────────────────────────────

def fetch_evolution_config() -> Optional[dict]:
    """
    GET /evolution-config-vps → { base_url, api_key, webhook_secret, active }
    Retorna None se não configurado ou inativo.
    """
    data = _panel_get("evolution-config-vps")
    if not data or not isinstance(data, dict):
        return None
    if not data.get("active", True):
        return None
    if not data.get("base_url") or not data.get("api_key"):
        return None
    return data


def fetch_panel_instances() -> list[dict]:
    """
    GET /whatsapp-instances-vps-list → lista de instâncias do painel.
    """
    data = _panel_get("whatsapp-instances-vps-list")
    if not data:
        return []
    return data if isinstance(data, list) else data.get("instances", [])


# ── Estado da Evolution → string normalizada ──────────────────────────────────

def parse_evo_state(state: str) -> str:
    """Normaliza o estado da Evolution para o schema do painel."""
    state = (state or "").lower()
    if state in ("open", "connected"):
        return "connected"
    if state in ("connecting", "qr"):
        return "qr_pending"
    if state in ("close", "disconnected", "logged_out"):
        return "disconnected"
    return "error"


# ── Webhook URL pra cada instância ────────────────────────────────────────────

def instance_webhook_url(panel_base: str) -> str:
    """
    URL que a Evolution chama ao receber mensagens.
    Sprint 35: aponta para whatsapp-incoming-webhook (thin wrapper → incoming-message).
    """
    return f"{panel_base}/whatsapp-incoming-webhook"


# ── Reconciliação ─────────────────────────────────────────────────────────────

def sync(evo_config: dict, panel_instances: list[dict]) -> None:
    """
    Reconcilia instâncias do painel com a Evolution API real.
    Atualiza status no painel via POST /whatsapp-instances-vps-update.
    """
    from evolution_client import EvolutionClient

    client = EvolutionClient(
        base_url=evo_config["base_url"],
        api_key=evo_config["api_key"],
    )
    webhook_secret = evo_config.get("webhook_secret", "")
    panel_base = _panel_base()
    webhook_url = instance_webhook_url(panel_base)

    # Busca instâncias existentes na Evolution
    try:
        evo_instances_raw = client.fetch_instances()
    except Exception as e:
        log(f"[sync] Erro ao buscar instâncias da Evolution: {e}")
        return

    # Índice por nome
    evo_by_name: dict[str, dict] = {}
    for evo_inst in evo_instances_raw:
        # Evolution retorna {"instance": {"instanceName": ..., "state": ...}, ...}
        inst_data = evo_inst.get("instance", evo_inst)
        name = inst_data.get("instanceName", inst_data.get("instance_name", ""))
        if name:
            evo_by_name[name] = evo_inst

    panel_names = {inst["instance_name"] for inst in panel_instances if inst.get("instance_name")}

    # ── 1. Deleta instâncias que sumiram do painel ────────────────────────────
    for evo_name in list(evo_by_name.keys()):
        if evo_name not in panel_names:
            try:
                client.delete_instance(evo_name)
                log(f"[sync] Deletou instância Evolution '{evo_name}' (removida do painel)")
            except Exception as e:
                log(f"[sync] Erro ao deletar '{evo_name}': {e}")

    # ── 2. Cria/atualiza instâncias do painel ─────────────────────────────────
    updates: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for panel_inst in panel_instances:
        inst_name = panel_inst.get("instance_name", "")
        inst_id = panel_inst.get("id", "")
        if not inst_name or not inst_id:
            continue

        # Criar se não existe na Evolution
        if inst_name not in evo_by_name:
            try:
                client.create_instance(
                    instance_name=inst_name,
                    webhook_url=webhook_url,
                    webhook_secret=webhook_secret,
                )
                log(f"[sync] Criou instância '{inst_name}' na Evolution")
            except Exception as e:
                log(f"[sync] Erro ao criar '{inst_name}': {e}")
                updates.append({"id": inst_id, "status": "error", "last_seen": now_iso})
                continue

        # Busca estado atual
        try:
            conn = client.get_connection_state(inst_name)
        except Exception as e:
            log(f"[sync] Erro ao buscar estado de '{inst_name}': {e}")
            continue

        # Evolution retorna {"instance": {"instanceName": ..., "state": "open"}}
        conn_data = conn.get("instance", conn)
        raw_state = conn_data.get("state", conn_data.get("connectionStatus", ""))
        status = parse_evo_state(raw_state)

        update: dict = {
            "id": inst_id,
            "status": status,
            "qr_code_b64": None,
            "last_seen": now_iso,
        }

        # Se precisa QR code, busca
        if status == "qr_pending":
            try:
                qr_resp = client.connect_instance(inst_name)
                # Pode vir como {"base64": "data:image/png;base64,..."} ou {"qrcode": {...}}
                qr_b64 = (
                    qr_resp.get("base64")
                    or qr_resp.get("qrcode", {}).get("base64")
                    or qr_resp.get("qrcode", {}).get("pairingCode")
                )
                if qr_b64:
                    update["qr_code_b64"] = qr_b64
                    log(f"[sync] '{inst_name}': QR code obtido")
            except Exception as e:
                log(f"[sync] Erro ao buscar QR de '{inst_name}': {e}")

        log(f"[sync] '{inst_name}': {panel_inst.get('status', '?')} → {status}")
        updates.append(update)

    # ── 3. Atualiza painel ────────────────────────────────────────────────────
    if updates:
        result = _panel_post("whatsapp-instances-vps-update", updates)
        if result is not None:
            log(f"[sync] Painel atualizado: {len(updates)} instância(s)")
        else:
            log("[sync] Falha ao atualizar painel (edge fn não deployada ainda?)")


# ── Main loop ─────────────────────────────────────────────────────────────────

# Adiciona scripts/ ao path pra importar evolution_client
_scripts_dir = str(Path(__file__).parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def run_loop() -> None:
    load_env()

    missing = [k for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN") if not os.environ.get(k)]
    if missing:
        log(f"[startup] ERRO: variáveis obrigatórias ausentes: {', '.join(missing)}")
        sys.exit(1)

    log("evolution_sync.py started (Sprint 27 — WhatsApp multi-instância)")
    log(f"Intervalo: {INTERVAL_SECONDS}s | Panel: {os.environ['PANEL_BASE_URL']}")

    while True:
        log("--- Início do ciclo evolution-sync ---")
        try:
            evo_config = fetch_evolution_config()
            if not evo_config:
                log("[cycle] Evolution não configurada no painel — aguardando")
            else:
                panel_instances = fetch_panel_instances()
                log(f"[cycle] {len(panel_instances)} instância(s) no painel")
                sync(evo_config, panel_instances)
        except Exception as e:
            log(f"[main] Erro no ciclo: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_loop()
