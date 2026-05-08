#!/usr/bin/env python3
"""Bling ERP v3 Client (OAuth 2.0) — Agente CFO skill."""

import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "_lib"))
from base import BaseERPClient, http_request, emit, emit_error, now_iso, make_list_response

SECRETS_FILE = os.path.expanduser("~/.openclaw/secrets/bling.env")


def _save_tokens(access_token, refresh_token, expiry):
    """Update tokens in secrets file."""
    lines = []
    if os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BLING_ACCESS_TOKEN="):
                    continue
                if line.startswith("BLING_REFRESH_TOKEN="):
                    continue
                if line.startswith("BLING_TOKEN_EXPIRY="):
                    continue
                if line:
                    lines.append(line)
    lines.append(f"BLING_ACCESS_TOKEN={access_token}")
    lines.append(f"BLING_REFRESH_TOKEN={refresh_token}")
    lines.append(f"BLING_TOKEN_EXPIRY={int(expiry)}")

    # Simple file locking
    lock_path = SECRETS_FILE + ".lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        time.sleep(1)
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            os.unlink(lock_path)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)

    try:
        with open(SECRETS_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.chmod(SECRETS_FILE, 0o600)
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass

    os.environ["BLING_ACCESS_TOKEN"] = access_token
    os.environ["BLING_REFRESH_TOKEN"] = refresh_token
    os.environ["BLING_TOKEN_EXPIRY"] = str(int(expiry))


class BlingClient(BaseERPClient):
    SKILL_NAME = "bling"
    BASE_URL = "https://api.bling.com.br/Api/v3"

    def _validate_env(self):
        for var in ("BLING_CLIENT_ID", "BLING_CLIENT_SECRET", "BLING_ACCESS_TOKEN", "BLING_REFRESH_TOKEN"):
            if not os.environ.get(var):
                raise RuntimeError(f"{var} nao definido. Execute connect.sh.")
        self._ensure_token()

    def _ensure_token(self):
        expiry = int(os.environ.get("BLING_TOKEN_EXPIRY", "0") or "0")
        if time.time() + 300 > expiry:
            self._refresh()

    def _refresh(self):
        client_id = os.environ["BLING_CLIENT_ID"]
        client_secret = os.environ["BLING_CLIENT_SECRET"]
        refresh_token = os.environ["BLING_REFRESH_TOKEN"]
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        body = f"grant_type=refresh_token&refresh_token={refresh_token}".encode()
        data = http_request("POST", f"{self.BASE_URL}/oauth/token", headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }, body=body)
        if "access_token" not in data:
            raise RuntimeError(f"Falha no refresh token: {data}")
        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", refresh_token)
        expires_in = int(data.get("expires_in", 7200))
        new_expiry = time.time() + expires_in
        _save_tokens(new_access, new_refresh, new_expiry)

    def _headers(self):
        return {
            "Authorization": f"Bearer {os.environ['BLING_ACCESS_TOKEN']}",
            "Content-Type": "application/json",
        }

    def _get(self, path, params=""):
        self._ensure_token()
        url = f"{self.BASE_URL}/{path}{'?' + params if params else ''}"
        return http_request("GET", url, headers=self._headers())

    def get_balance(self):
        data = self._get("contas-correntes")
        contas = data.get("data", []) if isinstance(data, dict) else []
        saldo = sum(float(c.get("saldo", 0) or 0) for c in contas)
        return {"balance_brl": round(saldo, 2), "as_of": now_iso()}

    def list_payables(self, from_date=None, to_date=None, limit=50, page=1):
        params = f"pagina={page}&limite={min(limit, 100)}&situacoes[]=1&situacoes[]=2"
        if from_date:
            params += f"&dataVencimentoInicio={from_date}"
        if to_date:
            params += f"&dataVencimentoFinal={to_date}"
        data = self._get("contas-pagar", params)
        items = []
        records = data.get("data", []) if isinstance(data, dict) else []
        for r in records:
            fornecedor = r.get("fornecedor", {}) or {}
            sit = int(r.get("situacao", 1) or 1)
            items.append({
                "id": str(r.get("id", "")),
                "due_date": (r.get("dataVencimento", "") or "")[:10],
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": fornecedor.get("nome", ""),
                "status": "paid" if sit == 3 else "pending",
                "category": None,
                "raw": r,
            })
        total = len(items)
        return make_list_response(items, page=page, total_count=total)

    def list_receivables(self, from_date=None, to_date=None, limit=50, page=1):
        params = f"pagina={page}&limite={min(limit, 100)}&situacoes[]=1"
        if from_date:
            params += f"&dataVencimentoInicio={from_date}"
        if to_date:
            params += f"&dataVencimentoFinal={to_date}"
        data = self._get("contas-receber", params)
        items = []
        records = data.get("data", []) if isinstance(data, dict) else []
        for r in records:
            contato = r.get("contato", {}) or {}
            sit = int(r.get("situacao", 1) or 1)
            items.append({
                "id": str(r.get("id", "")),
                "due_date": (r.get("dataVencimento", "") or "")[:10],
                "amount_brl": float(r.get("valor", 0) or 0),
                "counterparty": contato.get("nome", ""),
                "status": "received" if sit == 3 else "pending",
                "category": None,
                "raw": r,
            })
        total = len(items)
        return make_list_response(items, page=page, total_count=total)

    def company_info(self):
        try:
            data = self._get("empresas")
            empresas = data.get("data", []) if isinstance(data, dict) else []
            if empresas:
                e = empresas[0]
                return {"name": e.get("nome", "N/A"), "cnpj": e.get("cnpj"), "segment": "ERP"}
        except Exception:
            pass
        return {"name": "N/A", "cnpj": None, "segment": "ERP"}


if __name__ == "__main__":
    try:
        client = BlingClient()
        client.run_cli()
    except RuntimeError as e:
        emit_error(str(e))
