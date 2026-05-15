#!/usr/bin/env python3
"""
whatsapp_pair_helper.py — Wrapper para pareamento WhatsApp via OpenClaw Baileys.

Sprint 51 — WhatsApp nativo via @openclaw/whatsapp (Baileys).

Spawna `openclaw channels login --channel whatsapp` em background,
captura o QR code ASCII do stdout e salva no state file para o
painel/admin_action consultar.

State file: /tmp/cfo-whatsapp-pair.json
{
  "status": "idle"|"starting"|"qr_ready"|"connected"|"failed"|"cancelled",
  "qr_ascii": "<linhas do QR ASCII art>",
  "started_at": "<iso>",
  "connected_at": "<iso>",
  "error": "<msg>",
  "pid": <int>
}

Uso:
  python3 whatsapp_pair_helper.py start      # inicia pareamento
  python3 whatsapp_pair_helper.py status     # retorna state JSON
  python3 whatsapp_pair_helper.py cancel     # cancela processo em andamento
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

STATE_FILE = Path("/tmp/cfo-whatsapp-pair.json")
LOG_FILE = Path.home() / ".agente-cfo" / "logs" / "whatsapp-pair.log"
PAIR_TIMEOUT_S = 120  # 2 minutos para escanear


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"status": "idle"}


def _write_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_status() -> dict:
    """Retorna estado atual do pareamento."""
    state = _read_state()
    # Verifica se processo ainda está vivo
    pid = state.get("pid")
    if pid and state.get("status") in ("starting", "qr_ready"):
        try:
            os.kill(pid, 0)  # signal 0 = só verifica existência
        except (ProcessLookupError, PermissionError):
            # Processo morreu
            if state.get("status") == "qr_ready":
                state["status"] = "failed"
                state["error"] = "Processo de pareamento encerrou sem conectar (QR expirou?)"
            elif state.get("status") == "starting":
                state["status"] = "failed"
                state["error"] = "Processo encerrou antes de gerar QR"
            _write_state(state)
    return state


def cmd_cancel() -> dict:
    """Cancela processo de pareamento em andamento."""
    state = _read_state()
    pid = state.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _log(f"Processo {pid} cancelado")
        except ProcessLookupError:
            pass
        except Exception as e:
            _log(f"Erro ao cancelar PID {pid}: {e}")
    state["status"] = "cancelled"
    state["pid"] = None
    _write_state(state)
    return state


def cmd_start() -> dict:
    """
    Inicia processo de pareamento WhatsApp.
    Spawna `openclaw channels login --channel whatsapp` e monitora stdout.
    """
    state = _read_state()

    # Cancela pareamento anterior se em curso
    if state.get("status") in ("starting", "qr_ready"):
        _log("Cancelando pareamento anterior...")
        cmd_cancel()

    # Verifica se plugin está instalado
    try:
        result = subprocess.run(
            ["openclaw", "plugins", "list"],
            capture_output=True, text=True, timeout=15,
        )
        if "whatsapp" not in result.stdout.lower():
            _log("Plugin @openclaw/whatsapp não encontrado — instalando...")
            subprocess.run(
                ["openclaw", "plugins", "install", "@openclaw/whatsapp"],
                capture_output=True, timeout=60,
            )
    except Exception as e:
        _log(f"Aviso ao verificar plugin: {e}")

    initial_state = {
        "status": "starting",
        "qr_ascii": None,
        "started_at": _now_iso(),
        "connected_at": None,
        "error": None,
        "pid": None,
    }
    _write_state(initial_state)

    # Spawna processo de login
    try:
        proc = subprocess.Popen(
            ["openclaw", "channels", "login", "--channel", "whatsapp"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        state = {**initial_state, "status": "failed", "error": "openclaw não encontrado no PATH"}
        _write_state(state)
        return state

    initial_state["pid"] = proc.pid
    _write_state(initial_state)
    _log(f"Login iniciado (PID {proc.pid})")

    # Thread que monitora stdout em background
    def _monitor():
        qr_lines: list[str] = []
        collecting_qr = False
        qr_done = False
        connected = False

        deadline = time.time() + PAIR_TIMEOUT_S

        for line in proc.stdout:
            line = line.rstrip()
            _log(f"[login] {line[:100]}")

            if time.time() > deadline:
                _log("Timeout — cancela processo")
                proc.terminate()
                break

            # Detecta início do QR
            if "Scan this QR" in line or "scan this QR" in line.lower():
                collecting_qr = True
                qr_lines = [line]
                continue

            # Coleta linhas do QR (blocos unicode ou ASCII art)
            if collecting_qr and not qr_done:
                # Linha vazia depois do QR = fim do bloco
                if line.strip() == "" and len(qr_lines) > 5:
                    qr_done = True
                    collecting_qr = False
                    state = _read_state()
                    state["status"] = "qr_ready"
                    state["qr_ascii"] = "\n".join(qr_lines)
                    _write_state(state)
                    _log(f"QR capturado ({len(qr_lines)} linhas)")
                else:
                    qr_lines.append(line)
                continue

            # Detecta conexão
            if any(k in line.lower() for k in ["connected", "linked", "ready", "welcome"]):
                connected = True
                state = _read_state()
                state["status"] = "connected"
                state["connected_at"] = _now_iso()
                state["pid"] = None
                _write_state(state)
                _log("WhatsApp conectado com sucesso!")
                break

            # Detecta erros conhecidos
            if any(k in line.lower() for k in ["logged out", "session logged", "failed", "error"]):
                if not connected:
                    state = _read_state()
                    state["status"] = "failed"
                    state["error"] = line[:200]
                    _write_state(state)
                    _log(f"Falha no login: {line}")
                break

        proc.wait(timeout=5)
        _log(f"Processo login encerrou (rc={proc.returncode})")

        # Se não conectou, marca como failed
        final = _read_state()
        if final.get("status") in ("starting", "qr_ready"):
            final["status"] = "failed"
            final["error"] = "Processo encerrou sem conectar (QR expirou ou login cancelado)"
            _write_state(final)

    t = threading.Thread(target=_monitor, daemon=True)
    t.start()

    # Aguarda até o QR aparecer (ou falha rápida)
    for _ in range(30):  # 15s max pra gerar QR
        time.sleep(0.5)
        state = _read_state()
        if state.get("status") in ("qr_ready", "connected", "failed"):
            break

    return _read_state()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    result = {}
    if cmd == "start":
        result = cmd_start()
    elif cmd == "status":
        result = cmd_status()
    elif cmd == "cancel":
        result = cmd_cancel()
    else:
        print(json.dumps({"error": f"comando desconhecido: {cmd}"}))
        sys.exit(1)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
