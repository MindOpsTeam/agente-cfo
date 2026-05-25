#!/usr/bin/env python3
"""OAuth token refresh para skill nuvemshop — Agente CFO. Sprint INT-2.

Nuvemshop NÃO tem refresh_token — o access_token é permanente (não expira).
Este script valida que o token ainda está ativo fazendo um GET na store.

Uso: python3 oauth_refresh.py [--force]
  --force: força re-sync do token com o painel mesmo sem refresh necessário

Saída JSON stdout:
  {"ok": true, "skill": "nuvemshop", "refreshed": false, "expires_at": null}
  {"ok": false, "skill": "nuvemshop", "error": "<msg>"}

Exit 0 = ok, Exit 1 = token inválido.
"""
import sys, os, json, time, urllib.request, urllib.error
from datetime import datetime, timezone

SKILL_NAME = "nuvemshop"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/nuvemshop.env")
CFO_ENV_FILE = os.path.expanduser("~/.agente-cfo/.env")

FORCE = "--force" in sys.argv


def _load_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())


def _save_last_check() -> None:
    """Salva timestamp de last_check no secrets file."""
    skip = {"NS_LAST_CHECK"}
    lines = []
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                key = line.split('=', 1)[0].strip()
                if key not in skip:
                    lines.append(line.rstrip('\n'))
    ts = str(int(time.time()))
    lines.append(f"NS_LAST_CHECK={ts}")
    try:
        with open(SECRETS_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(SECRETS_FILE, 0o600)
    except Exception:
        pass


def _push_to_panel() -> None:
    """Re-sync token com painel (apenas com --force)."""
    panel_url = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    instance_id = os.environ.get("INSTANCE_ID", "")
    if not panel_url or not panel_token or not instance_id:
        return
    payload = json.dumps({
        "instance_id": instance_id,
        "access_token": os.environ.get("NS_ACCESS_TOKEN", ""),
        "store_id": os.environ.get("NS_STORE_ID", ""),
    }).encode()
    req = urllib.request.Request(
        f"{panel_url}/functions/v1/nuvemshop-push-tokens",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {panel_token}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass


def _out(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False))


def main():
    _load_file(SECRETS_FILE)
    _load_file(CFO_ENV_FILE)

    access_token = os.environ.get("NS_ACCESS_TOKEN", "")
    store_id = os.environ.get("NS_STORE_ID", "")

    if not access_token or not store_id:
        _out({"ok": False, "skill": SKILL_NAME,
              "error": "NS_ACCESS_TOKEN ou NS_STORE_ID ausentes"})
        sys.exit(1)

    # Valida token fazendo GET na store
    req = urllib.request.Request(
        f"https://api.nuvemshop.com.br/v1/{store_id}/store",
        headers={
            "Authentication": f"bearer {access_token}",
            "User-Agent": "agente-cfo/1.0",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                _save_last_check()
                if FORCE:
                    _push_to_panel()
                _out({"ok": True, "skill": SKILL_NAME, "refreshed": False, "expires_at": None})
                sys.exit(0)
            else:
                _out({"ok": False, "skill": SKILL_NAME,
                      "error": f"token inválido: HTTP {resp.status}"})
                sys.exit(1)
    except urllib.error.HTTPError as e:
        _out({"ok": False, "skill": SKILL_NAME,
              "error": f"token inválido: HTTP {e.code}"})
        sys.exit(1)
    except Exception as e:
        _out({"ok": False, "skill": SKILL_NAME, "error": f"Erro de rede: {e}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
