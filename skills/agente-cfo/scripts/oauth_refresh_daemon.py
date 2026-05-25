#!/usr/bin/env python3
"""Daemon de refresh automático de tokens OAuth — Agente CFO. Sprint INT-2.

Loop a cada 600s (10 min). Para cada skill OAuth ativa, roda oauth_refresh.py.
Se o script não existir para uma skill, pula sem erro.

Log: ~/.agente-cfo/logs/oauth-refresh.log

Systemd unit: cfo-oauth-refresh.service
"""
import os, sys, subprocess, time, json
from datetime import datetime, timezone

INTERVAL_S = 600
LOG_FILE = os.path.expanduser("~/.agente-cfo/logs/oauth-refresh.log")

# Resolve base relativo ao workspace OpenClaw real (skills sincronizadas via self_update)
# Fallback retrocompatível: ~/agente-cfo/skills se workspace OpenClaw não existir
BASE = os.environ.get("CFO_SKILLS_DIR")
if not BASE:
    _workspace_dir = os.path.expanduser("~/.openclaw/workspace/skills")
    _legacy_dir = os.path.expanduser("~/agente-cfo/skills")
    BASE = _workspace_dir if os.path.isdir(_workspace_dir) else _legacy_dir

OAUTH_SKILLS = [
    ("bling",         f"{BASE}/bling/scripts/oauth_refresh.py"),
    ("contaazul",     f"{BASE}/contaazul/scripts/oauth_refresh.py"),
    ("mercado-livre", f"{BASE}/mercado-livre/scripts/oauth_refresh.py"),
    ("nuvemshop",     f"{BASE}/nuvemshop/scripts/oauth_refresh.py"),
    ("hubspot",       f"{BASE}/hubspot/scripts/oauth_refresh.py"),
]


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass
    # Também escreve em stderr para journald
    print(f"[{ts}] {msg}", file=sys.stderr)


def run_refresh(skill: str, script: str) -> dict:
    if not os.path.exists(script):
        return {"ok": False, "skill": skill, "error": "script não encontrado", "skipped": True}
    try:
        r = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=45,
        )
        out = r.stdout.strip()
        try:
            result = json.loads(out) if out else {}
        except Exception:
            result = {"ok": r.returncode == 0, "skill": skill, "raw": out[:200]}
        if r.returncode != 0 and not result.get("ok"):
            result.setdefault("error", r.stderr.strip()[:200] or "exit non-zero")
        return result
    except subprocess.TimeoutExpired:
        return {"ok": False, "skill": skill, "error": "timeout 45s"}
    except Exception as e:
        return {"ok": False, "skill": skill, "error": str(e)[:200]}


def run_cycle() -> None:
    _log("--- início de ciclo de refresh ---")
    for skill, script in OAUTH_SKILLS:
        result = run_refresh(skill, script)
        if result.get("skipped"):
            _log(f"[{skill}] SKIP (script não encontrado)")
            continue
        ok = result.get("ok", False)
        refreshed = result.get("refreshed", False)
        err = result.get("error", "")
        expires_at = result.get("expires_at", "")
        if ok:
            if refreshed:
                _log(f"[{skill}] OK refreshed=true expires_at={expires_at}")
            else:
                _log(f"[{skill}] OK sem refresh necessário expires_at={expires_at}")
        else:
            _log(f"[{skill}] ERRO: {err}")
    _log(f"--- próximo ciclo em {INTERVAL_S}s ---")


def main() -> None:
    _log(f"oauth_refresh_daemon START interval={INTERVAL_S}s skills={[s for s,_ in OAUTH_SKILLS]}")
    while True:
        try:
            run_cycle()
        except Exception as e:
            _log(f"ERRO INESPERADO no ciclo: {e}")
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
