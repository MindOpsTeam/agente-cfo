#!/usr/bin/env python3
"""
erp_sync.py — SPRINT SYNC-1: Daemon de pull ERP→painel (bidirecional)

Comportamento:
- Loop a cada 5 min (configurável via ERP_SYNC_INTERVAL_S env)
- Para cada ERP ativo: puxa payables + receivables criados/atualizados desde last_sync
- Insere novidades em cfo_write_events com origin='erp_sync' (dedup por hash erp+record_id)
- Mantém ~/.openclaw/state/last_erp_sync.json com timestamps por ERP
- Se CFO_ERP_SYNC_NOTIFY_WA=true e houver novidades: envia 1 msg agregada no WA (max 1/hora)

Uso:
    python3 erp_sync.py                  # daemon (loop infinito)
    python3 erp_sync.py --once           # roda uma vez e sai (útil para debug)
    python3 erp_sync.py --dry-run        # simula sem gravar no painel
    python3 erp_sync.py --erp omie       # força ERP específico (ignora CFO_ERP_NAME)
"""

import os
import sys
import json
import subprocess
import hashlib
import time
import logging
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Config via env ────────────────────────────────────────────────────────────

INTERVAL_S = int(os.environ.get("ERP_SYNC_INTERVAL_S", "300"))   # 5 min default
LIMIT_PER_CALL = int(os.environ.get("ERP_SYNC_LIMIT", "50"))
NOTIFY_WA = os.environ.get("CFO_ERP_SYNC_NOTIFY_WA", "false").lower() == "true"
WA_COOLDOWN_S = int(os.environ.get("ERP_SYNC_WA_COOLDOWN_S", "3600"))  # 1h entre notifs WA
LOG_DIR = os.path.expanduser(os.environ.get("CFO_LOG_DIR", "~/.agente-cfo/logs"))
STATE_DIR = os.path.expanduser("~/.openclaw/state")
STATE_FILE = os.path.join(STATE_DIR, "last_erp_sync.json")
WA_STATE_FILE = os.path.join(STATE_DIR, "erp_sync_wa_last.json")

SCRIPTS_DIR = Path(__file__).parent
ERP_GATEWAY = str(SCRIPTS_DIR / "erp_gateway.py")
PANEL_WRITE = str(SCRIPTS_DIR / "panel_write_event.sh")
PANEL_POST_REPLY = str(SCRIPTS_DIR / "panel_post_reply.sh")

# ── Logging ───────────────────────────────────────────────────────────────────

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ERP_SYNC] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "erp_sync.log"), encoding="utf-8"),
    ],
)
log = logging.getLogger("erp_sync")

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_env():
    env_file = os.path.expanduser("~/.agente-cfo/.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(state: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_wa_state() -> dict:
    if os.path.exists(WA_STATE_FILE):
        try:
            with open(WA_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_wa_state(state: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(WA_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def make_dedup_key(erp: str, record_id: str, action: str) -> str:
    """Hash determinístico: mesma rodada não duplica."""
    raw = f"{erp}|{record_id}|{action}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def call_erp_gateway(cmd: str, extra_args: list[str], erp: Optional[str] = None) -> Optional[dict]:
    """Chama erp_gateway.py e retorna dict JSON ou None em caso de erro."""
    env = os.environ.copy()
    if erp:
        env["CFO_ERP_NAME"] = erp
    result = subprocess.run(
        [sys.executable, ERP_GATEWAY, cmd] + extra_args,
        capture_output=True, text=True, timeout=60, env=env
    )
    raw = result.stdout.strip()
    if not raw:
        log.warning("erp_gateway.py %s: saída vazia (stderr: %s)", cmd, result.stderr[:200])
        return None
    try:
        data = json.loads(raw)
        if "error" in data and data.get("error"):
            log.warning("erp_gateway.py %s: erro %s", cmd, data["error"])
            return None
        return data
    except json.JSONDecodeError:
        log.warning("erp_gateway.py %s: JSON inválido: %s", cmd, raw[:200])
        return None


def panel_write_event(
    action: str,
    erp: str,
    erp_record_id: str,
    amount: Optional[float],
    supplier: Optional[str],
    due_date: Optional[str],
    raw_text: str,
    dedup_key: str,
    dry_run: bool = False,
) -> bool:
    """
    Registra evento no painel via panel_write_event.sh.
    Retorna True se inseriu/dedup OK, False em erro.
    """
    if dry_run:
        log.info("[DRY-RUN] write_event: %s | %s | %s | %s", action, erp, erp_record_id, raw_text[:80])
        return True

    args = [
        "bash", PANEL_WRITE,
        "--action", action,
        "--erp", erp,
        "--erp_record_id", erp_record_id,
        "--raw_text", raw_text[:500],
        "--thread_id", "erp_sync",
        "--channel", f"erp_sync:{erp}",
        "--status", "success",
        "--dedup_key", dedup_key,
        "--origin", "erp_sync",  # coluna adicionada pelo PM na migration SYNC-1
    ]
    if amount is not None:
        args += ["--amount", str(amount)]
    if supplier:
        args += ["--supplier", supplier[:100]]
    if due_date:
        args += ["--due_date", due_date]

    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    out = result.stdout.strip()

    if out.startswith("OK:"):
        log.info("Inserido: %s → id=%s", raw_text[:60], out.split(":", 1)[-1].strip())
        return True
    elif out.startswith("DUPLICATE:"):
        log.debug("Duplicata ignorada: %s", dedup_key)
        return False  # False = não é "novo" — não conta para notif WA
    else:
        log.warning("panel_write_event falhou: %s (stderr: %s)", out, result.stderr[:100])
        return False


def extract_record_id(item: dict, erp: str) -> str:
    """Extrai ID do registro de acordo com a estrutura do ERP."""
    # Omie usa nCodLancamento; outros podem usar id, codigo, etc.
    for key in ("nCodLancamento", "nCodTitulo", "id", "codigo", "ID", "code"):
        if key in item and item[key]:
            return str(item[key])
    # Fallback: hash do item inteiro
    return hashlib.md5(json.dumps(item, sort_keys=True).encode()).hexdigest()[:16]


def extract_amount(item: dict) -> Optional[float]:
    for key in ("nValorTitulo", "nValorLancamento", "valor", "amount", "value", "nValor"):
        if key in item:
            try:
                return float(item[key])
            except (ValueError, TypeError):
                pass
    return None


def extract_supplier(item: dict) -> Optional[str]:
    for key in ("cNomeFornecedor", "cNomeCliente", "nome", "name", "supplier", "customer",
                "fornecedor", "cliente", "cRazaoSocial"):
        if key in item and item[key]:
            return str(item[key])[:100]
    return None


def extract_due_date(item: dict) -> Optional[str]:
    for key in ("dDataVencimento", "dDtVenc", "due_date", "vencimento", "data_vencimento"):
        if key in item and item[key]:
            v = str(item[key])
            # Normaliza dd/mm/yyyy → yyyy-mm-dd se necessário
            if len(v) == 10 and v[2] == "/":
                parts = v.split("/")
                if len(parts) == 3:
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
            return v
    return None


def extract_description(item: dict) -> str:
    for key in ("cObservacao", "cHistorico", "descricao", "description", "obs",
                "cDescricao", "historico"):
        if key in item and item[key]:
            return str(item[key])[:200]
    return ""


def items_from_gateway_response(resp: Optional[dict]) -> list[dict]:
    """Normaliza resposta do erp_gateway em lista de items."""
    if resp is None:
        return []
    # Pode vir como {"items": [...]} ou {"payables": [...]} ou lista direta
    for key in ("items", "payables", "receivables", "lancamentos", "titulos", "data"):
        if key in resp and isinstance(resp[key], list):
            return resp[key]
    if isinstance(resp, list):
        return resp
    return []


# ── Core: sincronizar um ERP ──────────────────────────────────────────────────

def sync_erp(erp_name: str, state: dict, dry_run: bool) -> tuple[int, int]:
    """
    Puxa payables + receivables do ERP desde last_sync.
    Retorna (inserted_count, skipped_count).
    """
    last_sync_ts = state.get(erp_name, {}).get("last_sync", 0)
    # Se nunca sincronizou, pega os últimos 24h para não inundar
    if last_sync_ts == 0:
        lookback_dt = datetime.now(timezone.utc) - timedelta(hours=24)
    else:
        lookback_dt = datetime.fromtimestamp(last_sync_ts, tz=timezone.utc)
    from_date = lookback_dt.strftime("%Y-%m-%d")

    log.info("Sincronizando %s desde %s ...", erp_name, from_date)
    inserted = 0
    skipped = 0

    for record_type, gateway_cmd, action_name in [
        ("payable",    "list_payables",    "synced_payable"),
        ("receivable", "list_receivables", "synced_receivable"),
    ]:
        resp = call_erp_gateway(
            gateway_cmd,
            ["--from", from_date, "--limit", str(LIMIT_PER_CALL)],
            erp=erp_name,
        )
        items = items_from_gateway_response(resp)
        log.info("  %s: %d item(s) retornados pelo ERP", gateway_cmd, len(items))

        for item in items:
            record_id = extract_record_id(item, erp_name)
            dedup = make_dedup_key(erp_name, record_id, action_name)
            amount = extract_amount(item)
            supplier = extract_supplier(item)
            due_date = extract_due_date(item)
            desc = extract_description(item)

            tipo = "Conta a pagar" if record_type == "payable" else "Recebimento"
            amt_str = f"R${amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if amount else "valor n/d"
            raw_text = f"Sync ERP — {tipo}: {supplier or 'n/d'} {amt_str}"
            if desc:
                raw_text += f" ({desc[:80]})"

            ok = panel_write_event(
                action=action_name,
                erp=erp_name,
                erp_record_id=record_id,
                amount=amount,
                supplier=supplier,
                due_date=due_date,
                raw_text=raw_text,
                dedup_key=dedup,
                dry_run=dry_run,
            )
            if ok:
                inserted += 1
            else:
                skipped += 1

    # Atualiza timestamp de last_sync
    if erp_name not in state:
        state[erp_name] = {}
    state[erp_name]["last_sync"] = time.time()
    state[erp_name]["last_sync_iso"] = now_iso()
    state[erp_name]["last_inserted"] = inserted
    state[erp_name]["last_skipped"] = skipped

    log.info("  %s: %d inseridos, %d ignorados (dedup)", erp_name, inserted, skipped)
    return inserted, skipped


# ── Notificação WA ────────────────────────────────────────────────────────────

def maybe_notify_wa(erp_name: str, inserted: int, dry_run: bool):
    """Envia 1 msg agregada no WA se houver novidades e cooldown passou."""
    if not NOTIFY_WA or inserted == 0:
        return

    wa_state = load_wa_state()
    last_notif = wa_state.get("last_notif_ts", 0)
    if time.time() - last_notif < WA_COOLDOWN_S:
        log.info("Notif WA: cooldown ativo (%.0fmin restantes)",
                 (WA_COOLDOWN_S - (time.time() - last_notif)) / 60)
        return

    if dry_run:
        log.info("[DRY-RUN] Notif WA: %d novidade(s) no %s", inserted, erp_name)
        return

    wa_to = os.environ.get("CFO_WHATSAPP_TO", "")
    if not wa_to:
        log.warning("Notif WA: CFO_WHATSAPP_TO não definido, pulando")
        return

    msg = (
        f"🔄 *ERP Sync* — {inserted} lançamento(s) novo(s) no {erp_name.capitalize()} "
        f"detectado(s) e registrado(s) no painel.\n"
        f"Acesse o feed de atividade no painel para detalhes."
    )

    result = subprocess.run(
        ["bash", PANEL_POST_REPLY, "whatsapp:principal", wa_to, msg],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        log.info("Notif WA enviada: %s", msg[:80])
        wa_state["last_notif_ts"] = time.time()
        wa_state["last_notif_iso"] = now_iso()
        save_wa_state(wa_state)
    else:
        log.warning("Notif WA falhou: %s", result.stderr[:100])


# ── Descoberta de ERPs ativos ─────────────────────────────────────────────────

def get_active_erps(force_erp: Optional[str] = None) -> list[str]:
    """
    Retorna lista de ERPs para sincronizar.
    Prioridade: --erp arg > CFO_ERP_NAME env > scan de skills disponíveis.
    """
    if force_erp:
        return [force_erp]

    erp_name = os.environ.get("CFO_ERP_NAME", "").strip().lower()
    if erp_name and erp_name != "nenhum":
        erps = [erp_name]
    else:
        # Scan: se existir ~/.openclaw/workspace/skills/<erp>/SKILL.md e secrets
        skills_root = os.path.expanduser("~/.openclaw/workspace/skills")
        known_erps = ["omie", "bling", "tiny", "granatum", "vhsys", "nibo", "contaazul"]
        erps = []
        for erp in known_erps:
            skill_path = os.path.join(skills_root, erp, "SKILL.md")
            if os.path.exists(skill_path):
                erps.append(erp)

    if not erps:
        log.info("Nenhum ERP ativo detectado — ERP_SYNC ocioso")
    return erps


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_once(force_erp: Optional[str], dry_run: bool) -> dict[str, tuple[int, int]]:
    """Executa uma rodada de sync em todos os ERPs ativos."""
    erps = get_active_erps(force_erp)
    if not erps:
        return {}

    state = load_state()
    results: dict[str, tuple[int, int]] = {}

    for erp in erps:
        try:
            ins, skip = sync_erp(erp, state, dry_run)
            results[erp] = (ins, skip)
            if ins > 0:
                maybe_notify_wa(erp, ins, dry_run)
        except subprocess.TimeoutExpired:
            log.error("Timeout ao sincronizar %s — próxima tentativa em %ds", erp, INTERVAL_S)
        except Exception as exc:
            log.error("Erro ao sincronizar %s: %s", erp, exc, exc_info=True)

    if not dry_run:
        save_state(state)

    return results


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Agente CFO — ERP Sync daemon (SYNC-1)")
    parser.add_argument("--once", action="store_true", help="Roda uma vez e sai")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar no painel")
    parser.add_argument("--erp", type=str, default=None, help="Força ERP específico")
    args = parser.parse_args()

    log.info(
        "ERP Sync iniciado — interval=%ds, notify_wa=%s, dry_run=%s",
        INTERVAL_S, NOTIFY_WA, args.dry_run,
    )

    if args.once:
        results = run_once(args.erp, args.dry_run)
        total_ins = sum(r[0] for r in results.values())
        total_skip = sum(r[1] for r in results.values())
        log.info("Rodada única concluída: %d inseridos, %d ignorados", total_ins, total_skip)
        sys.exit(0)

    # Daemon loop
    while True:
        try:
            results = run_once(args.erp, args.dry_run)
            total_ins = sum(r[0] for r in results.values())
            total_skip = sum(r[1] for r in results.values())
            log.info(
                "Rodada: %d inseridos, %d ignorados. Próxima em %ds",
                total_ins, total_skip, INTERVAL_S,
            )
        except KeyboardInterrupt:
            log.info("ERP Sync interrompido (SIGINT)")
            sys.exit(0)
        except Exception as exc:
            log.error("Erro inesperado no loop: %s", exc, exc_info=True)

        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
