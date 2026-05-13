#!/usr/bin/env python3
"""
mcp_manager.py — Helper unificado para registrar/remover MCP servers no OpenClaw.

Caminho canônico (descoberto no Sprint 28): mcp.servers.<name>
Usa `openclaw config set/unset/get` — NUNCA escreve openclaw.json diretamente.

API pública:
  register_mcp(name, command, args, env, *, log_fn)  → bool (True se registrou/atualizou)
  unregister_mcp(name, *, log_fn)                    → bool (True se removeu)
  list_registered_mcps()                             → set[str]  (nomes ativos)
  mcp_state_hash(name, command, args, env)           → str (hash pra detectar mudanças)
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

MCP_LOG = Path.home() / ".agente-cfo" / "logs" / "mcp-sync.log"
MCP_STATE = Path.home() / ".agente-cfo" / "state" / "mcp_registered.json"

OPENCLAW_CMD = os.environ.get("OPENCLAW_BIN", "openclaw")


# ── Logging ───────────────────────────────────────────────────────────────────

def _mcp_log(msg: str, log_fn=None) -> None:
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        MCP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(MCP_LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    if log_fn:
        log_fn(msg)


# ── State (hash pra detectar mudanças sem ler env redactado) ──────────────────

def _load_state() -> dict:
    MCP_STATE.parent.mkdir(parents=True, exist_ok=True)
    if MCP_STATE.exists():
        try:
            return json.loads(MCP_STATE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    MCP_STATE.write_text(json.dumps(state, indent=2, default=str))


def mcp_state_hash(name: str, command: str, args: list, env: dict) -> str:
    """Hash estável do estado desejado — para detectar se mudou sem usar config get."""
    payload = json.dumps(
        {"name": name, "command": command, "args": sorted(args) if args else [], "env": {k: v for k, v in sorted(env.items())}},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── openclaw config wrappers ──────────────────────────────────────────────────

def _run_openclaw(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    """Roda openclaw CLI e retorna (returncode, stdout, stderr)."""
    cmd = [OPENCLAW_CMD] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"openclaw não encontrado em PATH ({OPENCLAW_CMD})"
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def _config_set(dot_path: str, value_json: str) -> tuple[bool, str]:
    """openclaw config set <path> <json> --strict-json → (ok, msg)"""
    rc, out, err = _run_openclaw("config", "set", dot_path, value_json, "--strict-json")
    return rc == 0, out or err


def _config_unset(dot_path: str) -> tuple[bool, str]:
    """openclaw config unset <path> → (ok, msg)"""
    rc, out, err = _run_openclaw("config", "unset", dot_path)
    return rc == 0, out or err


def _config_validate() -> tuple[bool, str]:
    """openclaw config validate → (ok, msg)"""
    rc, out, err = _run_openclaw("config", "validate")
    return rc == 0, out or err


def _config_get_servers() -> set:
    """Retorna set de nomes de servers registrados (lê openclaw.json diretamente pra não depender de redact)."""
    config_file = Path.home() / ".openclaw" / "openclaw.json"
    if not config_file.exists():
        return set()
    try:
        data = json.loads(config_file.read_text())
        servers = data.get("mcp", {}).get("servers", {})
        return set(servers.keys())
    except Exception:
        return set()


# ── API pública ───────────────────────────────────────────────────────────────

def register_mcp(
    name: str,
    command: str,
    args: list,
    env: Optional[dict] = None,
    *,
    log_fn=None,
) -> bool:
    """
    Registra (ou atualiza se mudou) um MCP server no OpenClaw.
    Usa state file para detectar mudanças sem depender de config get redactado.
    Retorna True se registrou/atualizou, False se sem mudança ou erro.
    """
    env = env or {}
    new_hash = mcp_state_hash(name, command, args, env)
    state = _load_state()

    # Sem mudança → skip
    if state.get(name) == new_hash and name in _config_get_servers():
        return False

    # Monta entrada JSON
    entry: dict = {"command": command}
    if args:
        entry["args"] = args
    if env:
        entry["env"] = {k: str(v) for k, v in env.items()}

    entry_json = json.dumps(entry)
    dot_path = f"mcp.servers.{name}"

    ok, msg = _config_set(dot_path, entry_json)
    if not ok:
        _mcp_log(f"[register] ERRO {name}: {msg}", log_fn)
        return False

    # Valida config resultante
    valid, vmsg = _config_validate()
    if not valid:
        # Rollback: remove o que acabou de setar
        _mcp_log(f"[register] Config inválida após set de {name}, fazendo rollback: {vmsg}", log_fn)
        _config_unset(dot_path)
        return False

    # Salva hash no state
    state[name] = new_hash
    _save_state(state)

    action = "atualizado" if state.get(name) else "registrado"
    _mcp_log(f"[register] {name}: {action} (cmd={command}, args={args}, hash={new_hash})", log_fn)
    return True


def unregister_mcp(name: str, *, log_fn=None) -> bool:
    """
    Remove MCP server do OpenClaw.
    Retorna True se removeu, False se já não existia ou erro.
    """
    registered = _config_get_servers()
    if name not in registered:
        # Remove do state se estiver lá
        state = _load_state()
        if name in state:
            del state[name]
            _save_state(state)
        return False

    dot_path = f"mcp.servers.{name}"
    ok, msg = _config_unset(dot_path)
    if not ok:
        _mcp_log(f"[unregister] ERRO {name}: {msg}", log_fn)
        return False

    # Atualiza state
    state = _load_state()
    state.pop(name, None)
    _save_state(state)

    _mcp_log(f"[unregister] {name}: removido", log_fn)
    return True


def list_registered_mcps() -> set:
    """Retorna set de nomes de MCP servers registrados no openclaw.json."""
    return _config_get_servers()


def restart_gateway_if_needed(changed: bool, log_fn=None) -> None:
    """Reinicia o openclaw-gateway apenas se houve mudança real."""
    if not changed:
        return
    try:
        result = subprocess.run(
            ["systemctl", "restart", "openclaw-gateway"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            _mcp_log("[gateway] openclaw-gateway reiniciado", log_fn)
        else:
            _mcp_log(f"[gateway] restart retornou {result.returncode}: {result.stderr[:80]}", log_fn)
    except FileNotFoundError:
        # macOS dev — tenta openclaw gateway restart
        rc, out, err = _run_openclaw("gateway", "restart")
        if rc == 0:
            _mcp_log("[gateway] openclaw-gateway reiniciado via CLI", log_fn)
        else:
            _mcp_log(f"[gateway] CLI restart falhou: {err[:80]}", log_fn)
    except Exception as e:
        _mcp_log(f"[gateway] Erro ao reiniciar: {e}", log_fn)
