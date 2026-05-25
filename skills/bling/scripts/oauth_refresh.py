#!/usr/bin/env python3
"""OAuth token refresh para skill bling — Agente CFO. Sprint INT-2.

Uso: python3 oauth_refresh.py [--force]
  --force: ignora expires_at e faz refresh sempre

Saída JSON stdout:
  {"ok": true, "skill": "bling", "refreshed": true|false, "expires_at": "<iso>"}
  {"ok": false, "skill": "bling", "error": "<msg>"}

Exit 0 = ok (mesmo sem refresh necessário)
Exit 1 = falha crítica (Marcos detecta via credential_error)
"""
import sys, os, json, time, base64, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

SKILL_NAME = "bling"
SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/bling.env")
CFO_ENV_FILE = os.path.expanduser("~/.agente-cfo/.env")
TOKEN_URL = "https://api.bling.com.br/Api/v3/oauth/token"
REFRESH_THRESHOLD_S = 3600  # refresh se expira em < 1h

FORCE = "--force" in sys.argv


def _load_file(path: str) -> None:
    """Carrega .env no os.environ (setdefault)."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())


def _save_tokens(access_token: str, refresh_token: str, expiry: float) -> None:
    """Atualiza tokens no SECRETS_FILE preservando outras linhas."""
    skip = {"BLING_ACCESS_TOKEN", "BLING_REFRESH_TOKEN", "BLING_TOKEN_EXPIRY"}
    lines = []
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                key = line.split('=', 1)[0].strip()
                if key not in skip:
                    lines.append(line.rstrip('\n'))
    lines.append(f"BLING_ACCESS_TOKEN={access_token}")
    lines.append(f"BLING_REFRESH_TOKEN={refresh_token}")
    lines.append(f"BLING_TOKEN_EXPIRY={int(expiry)}")
    os.makedirs(os.path.dirname(SECRETS_FILE), exist_ok=True)
    with open(SECRETS_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(SECRETS_FILE, 0o600)
    os.environ["BLING_ACCESS_TOKEN"] = access_token
    os.environ["BLING_REFRESH_TOKEN"] = refresh_token
    os.environ["BLING_TOKEN_EXPIRY"] = str(int(expiry))


def _push_to_panel(access_token: str, refresh_token: str, expires_in: int) -> None:
    """Envia tokens renovados para o painel via bling-push-tokens."""
    panel_url = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    instance_id = os.environ.get("INSTANCE_ID", "")
    client_id = os.environ.get("BLING_CLIENT_ID", "")
    client_secret = os.environ.get("BLING_CLIENT_SECRET", "")

    if not panel_url or not panel_token or not instance_id:
        return  # Sem config de painel — ok, só salva local

    payload = json.dumps({
        "instance_id": instance_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        f"{panel_url}/functions/v1/bling-push-tokens",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {panel_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            pass  # 200 = ok
    except Exception:
        pass  # Push falhou — não crítico, tokens já salvos localmente


def _out(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False))


def main():
    _load_file(SECRETS_FILE)
    _load_file(CFO_ENV_FILE)

    client_id = os.environ.get("BLING_CLIENT_ID", "")
    client_secret = os.environ.get("BLING_CLIENT_SECRET", "")
    refresh_token = os.environ.get("BLING_REFRESH_TOKEN", "")

    if not client_id or not client_secret or not refresh_token:
        _out({"ok": False, "skill": SKILL_NAME,
              "error": "BLING_CLIENT_ID, BLING_CLIENT_SECRET ou BLING_REFRESH_TOKEN ausentes"})
        sys.exit(1)

    expiry = float(os.environ.get("BLING_TOKEN_EXPIRY", "0"))
    needs_refresh = FORCE or (expiry == 0) or (time.time() + REFRESH_THRESHOLD_S >= expiry)

    if not needs_refresh:
        exp_iso = datetime.fromtimestamp(expiry, timezone.utc).isoformat()
        _out({"ok": True, "skill": SKILL_NAME, "refreshed": False, "expires_at": exp_iso})
        sys.exit(0)

    # Basic auth
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {creds}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode(errors="replace")[:200]
        _out({"ok": False, "skill": SKILL_NAME,
              "error": f"HTTP {e.code} ao renovar token: {body_err}"})
        sys.exit(1)
    except Exception as e:
        _out({"ok": False, "skill": SKILL_NAME, "error": f"Erro de rede: {e}"})
        sys.exit(1)

    new_access = data.get("access_token", "")
    new_refresh = data.get("refresh_token", refresh_token)
    expires_in = int(data.get("expires_in", 21600))

    if not new_access:
        _out({"ok": False, "skill": SKILL_NAME,
              "error": f"access_token não retornado: {str(data)[:200]}"})
        sys.exit(1)

    new_expiry = time.time() + expires_in
    _save_tokens(new_access, new_refresh, new_expiry)
    _push_to_panel(new_access, new_refresh, expires_in)

    exp_iso = datetime.fromtimestamp(new_expiry, timezone.utc).isoformat()
    _out({"ok": True, "skill": SKILL_NAME, "refreshed": True, "expires_at": exp_iso})


if __name__ == "__main__":
    main()
