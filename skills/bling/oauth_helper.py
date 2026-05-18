#!/usr/bin/env python3
"""OAuth helper para Bling API v3. Captura access_token + refresh_token iniciais."""
import base64
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"
TOKENS_PATH = Path(__file__).parent / "tokens.json"


def load_env():
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


ENV = load_env()
CLIENT_ID = ENV["BLING_CLIENT_ID"]
CLIENT_SECRET = ENV["BLING_CLIENT_SECRET"]
REDIRECT_URI = ENV["BLING_REDIRECT_URI"]
STATE = secrets.token_urlsafe(16)

AUTH_URL = (
    "https://www.bling.com.br/Api/v3/oauth/authorize"
    f"?response_type=code&client_id={CLIENT_ID}&state={STATE}"
)
TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"

captured_code = {"code": None, "state": None, "error": None}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        qs = urllib.parse.parse_qs(parsed.query)
        captured_code["code"] = qs.get("code", [None])[0]
        captured_code["state"] = qs.get("state", [None])[0]
        captured_code["error"] = qs.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if captured_code["error"]:
            msg = f"<h1>Erro: {captured_code['error']}</h1>"
        else:
            msg = "<h1>OK! Pode fechar essa aba e voltar ao terminal.</h1>"
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, *args):
        pass


def exchange_code_for_tokens(code):
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
    }).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def main():
    print(f"[bling-oauth] Client ID: {CLIENT_ID[:12]}...")
    print(f"[bling-oauth] Redirect:  {REDIRECT_URI}")
    print(f"[bling-oauth] State:     {STATE}")
    print()
    print("[bling-oauth] Abrindo browser na URL de autorizacao do Bling...")
    print(f"[bling-oauth] Se nao abrir, cole manualmente:\n{AUTH_URL}\n")

    server = HTTPServer(("localhost", 3000), CallbackHandler)
    webbrowser.open(AUTH_URL)
    print("[bling-oauth] Aguardando callback em http://localhost:3000/callback ...")

    while captured_code["code"] is None and captured_code["error"] is None:
        server.handle_request()

    if captured_code["error"]:
        print(f"[bling-oauth] ERRO no callback: {captured_code['error']}", file=sys.stderr)
        sys.exit(1)
    if captured_code["state"] != STATE:
        print(f"[bling-oauth] state mismatch (CSRF) — abortando", file=sys.stderr)
        sys.exit(1)

    print(f"[bling-oauth] Code recebido: {captured_code['code'][:16]}...")
    print("[bling-oauth] Trocando code por tokens...")

    try:
        tokens = exchange_code_for_tokens(captured_code["code"])
    except urllib.error.HTTPError as e:
        print(f"[bling-oauth] HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

    TOKENS_PATH.write_text(json.dumps(tokens, indent=2))
    print(f"[bling-oauth] Tokens salvos em {TOKENS_PATH}")
    print(f"[bling-oauth] access_token expira em {tokens.get('expires_in')}s")
    print(f"[bling-oauth] scope: {tokens.get('scope', '(nao informado)')}")


if __name__ == "__main__":
    main()
