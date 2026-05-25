#!/usr/bin/env python3
"""OAuth token refresh para skill mercado-livre — Agente CFO. Sprint INT-2.

Uso: python3 oauth_refresh.py [--force]
Saída JSON stdout: {"ok": bool, "skill": "mercado-livre", "refreshed": bool, "expires_at": str|None}
Exit 0 = ok, Exit 1 = falha crítica.

Mercado Livre usa grant_type=refresh_token sem Basic auth —
client_id e client_secret vão no body URL-encoded.
"""
import sys, os, json, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

SKILL_NAME = "mercado-livre"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/mercado-livre.env")
CFO_ENV_FILE = os.path.expanduser("~/.agente-cfo/.env")
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
REFRESH_THRESHOLD_S = 3600

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


def _save_tokens(access_token: str, refresh_token: str, user_id: str, expiry: float) -> None:
    skip = {"ML_ACCESS_TOKEN", "ML_REFRESH_TOKEN", "ML_TOKEN_EXPIRY", "ML_USER_ID"}
    lines = []
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                key = line.split('=', 1)[0].strip()
                if key not in skip:
                    lines.append(line.rstrip('\n'))
    lines.extend([
        f"ML_ACCESS_TOKEN={access_token}",
        f"ML_REFRESH_TOKEN={refresh_token}",
        f"ML_TOKEN_EXPIRY={int(expiry)}",
        f"ML_USER_ID={user_id}",
    ])
    os.makedirs(os.path.dirname(SECRETS_FILE), exist_ok=True)
    with open(SECRETS_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(SECRETS_FILE, 0o600)
    os.environ["ML_ACCESS_TOKEN"] = access_token
    os.environ["ML_REFRESH_TOKEN"] = refresh_token
    os.environ["ML_TOKEN_EXPIRY"] = str(int(expiry))
    os.environ["ML_USER_ID"] = user_id


def _push_to_panel(access_token: str, refresh_token: str, expires_in: int) -> None:
    panel_url = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    instance_id = os.environ.get("INSTANCE_ID", "")
    if not panel_url or not panel_token or not instance_id:
        return
    payload = json.dumps({
        "instance_id": instance_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "client_id": os.environ.get("ML_CLIENT_ID", ""),
        "client_secret": os.environ.get("ML_CLIENT_SECRET", ""),
    }).encode()
    req = urllib.request.Request(
        f"{panel_url}/functions/v1/mercado-livre-push-tokens",
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

    client_id = os.environ.get("ML_CLIENT_ID", "")
    client_secret = os.environ.get("ML_CLIENT_SECRET", "")
    refresh_token = os.environ.get("ML_REFRESH_TOKEN", "")

    if not client_id or not client_secret or not refresh_token:
        _out({"ok": False, "skill": SKILL_NAME,
              "error": "ML_CLIENT_ID, ML_CLIENT_SECRET ou ML_REFRESH_TOKEN ausentes"})
        sys.exit(1)

    expiry = float(os.environ.get("ML_TOKEN_EXPIRY", "0"))
    needs_refresh = FORCE or (expiry == 0) or (time.time() + REFRESH_THRESHOLD_S >= expiry)

    if not needs_refresh:
        exp_iso = datetime.fromtimestamp(expiry, timezone.utc).isoformat()
        _out({"ok": True, "skill": SKILL_NAME, "refreshed": False, "expires_at": exp_iso})
        sys.exit(0)

    # ML não usa Basic auth — client_id/secret vão no body
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode(errors="replace")[:200]
        _out({"ok": False, "skill": SKILL_NAME, "error": f"HTTP {e.code}: {body_err}"})
        sys.exit(1)
    except Exception as e:
        _out({"ok": False, "skill": SKILL_NAME, "error": f"Erro de rede: {e}"})
        sys.exit(1)

    new_access = data.get("access_token", "")
    new_refresh = data.get("refresh_token", refresh_token)
    user_id = str(data.get("user_id", os.environ.get("ML_USER_ID", "")))
    expires_in = int(data.get("expires_in", 21600))

    if not new_access:
        _out({"ok": False, "skill": SKILL_NAME, "error": f"access_token ausente: {str(data)[:200]}"})
        sys.exit(1)

    new_expiry = time.time() + expires_in
    _save_tokens(new_access, new_refresh, user_id, new_expiry)
    _push_to_panel(new_access, new_refresh, expires_in)

    exp_iso = datetime.fromtimestamp(new_expiry, timezone.utc).isoformat()
    _out({"ok": True, "skill": SKILL_NAME, "refreshed": True, "expires_at": exp_iso})


if __name__ == "__main__":
    main()
