#!/usr/bin/env python3
"""Base classes for ERP and CRM adapters — Agente CFO skill library."""

from __future__ import annotations
import json
import os
import sys
import time
import random
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

# ── Output helpers ────────────────────────────────────────────────────────────

def emit(data: Any) -> None:
    """Print JSON to stdout — the only output channel for clients."""
    print(json.dumps(data, ensure_ascii=False, default=str))

def emit_error(message: str, code: str = "error", status: int = 1) -> None:
    """Print error JSON and exit."""
    emit({"error": message, "code": code})
    sys.exit(status)

def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ── HTTP with retry/backoff ───────────────────────────────────────────────────

def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    backoff_base: float = 1.0,
) -> dict[str, Any]:
    """
    HTTP request with exponential backoff + jitter.
    Returns parsed JSON dict or raises on unrecoverable errors.
    """
    headers = headers or {}
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            time.sleep(min(wait, 60))

        req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"_raw": raw}

        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            if e.code in (429, 503):  # rate limit / overload — retry
                last_error = e
                continue
            if 400 <= e.code < 500:  # client error — no retry
                try:
                    detail = json.loads(raw)
                except Exception:
                    detail = raw
                raise RuntimeError(f"HTTP {e.code}: {detail}") from e
            last_error = e  # 5xx — retry

        except Exception as e:
            last_error = e

    raise RuntimeError(f"Request failed after {max_retries + 1} attempts: {last_error}") from last_error


def load_secrets(skill_name: str) -> None:
    """Load ~/.openclaw/secrets/<skill>.env into os.environ."""
    path = os.path.expanduser(f"~/.openclaw/secrets/{skill_name}.env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ── Normalized schemas ────────────────────────────────────────────────────────

def make_payable_item(
    id: str,
    due_date: str,  # YYYY-MM-DD
    amount_brl: float,
    counterparty: str,
    status: str,  # pending|paid|overdue
    category: str | None = None,
    raw: dict | None = None,
) -> dict:
    return {
        "id": str(id),
        "due_date": due_date,
        "amount_brl": float(amount_brl),
        "counterparty": counterparty,
        "status": status,
        "category": category,
        "raw": raw or {},
    }

def make_receivable_item(
    id: str,
    due_date: str,
    amount_brl: float,
    counterparty: str,
    status: str,  # pending|received|overdue
    category: str | None = None,
    raw: dict | None = None,
) -> dict:
    return {
        "id": str(id),
        "due_date": due_date,
        "amount_brl": float(amount_brl),
        "counterparty": counterparty,
        "status": status,
        "category": category,
        "raw": raw or {},
    }

def make_list_response(items: list, page: int = 1, total_pages: int = 1, total_count: int | None = None) -> dict:
    return {
        "items": items,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count if total_count is not None else len(items),
    }

def make_deal_item(
    id: str,
    title: str,
    amount_brl: float | None,
    stage: str,
    status: str,  # open|won|lost
    expected_close_date: str | None = None,
    owner: str | None = None,
    raw: dict | None = None,
) -> dict:
    return {
        "id": str(id),
        "title": title,
        "amount_brl": float(amount_brl) if amount_brl is not None else None,
        "stage": stage,
        "status": status,
        "expected_close_date": expected_close_date,
        "owner": owner,
        "raw": raw or {},
    }


# ── CLI arg parser ────────────────────────────────────────────────────────────

def parse_cli_args() -> tuple[str, dict[str, Any]]:
    """
    Parse sys.argv: first arg = command, rest = --key value flags.
    Returns (command, kwargs).
    """
    args = sys.argv[1:]
    if not args:
        emit_error("Uso: client.py <command> [--from DATE] [--to DATE] [--limit N] [--status STATUS]")

    command = args[0]
    kwargs: dict[str, Any] = {}
    i = 1
    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args):
            key = args[i][2:].replace("-", "_")
            val = args[i + 1]
            kwargs[key] = val
            i += 2
        else:
            i += 1

    return command, kwargs


# ── Base adapters ─────────────────────────────────────────────────────────────

class BaseERPClient(ABC):
    SKILL_NAME: str = ""

    def __init__(self):
        load_secrets(self.SKILL_NAME)
        self._validate_env()

    @abstractmethod
    def _validate_env(self) -> None:
        """Raise RuntimeError if required env vars are missing."""
        ...

    @abstractmethod
    def get_balance(self) -> dict:
        """Returns {"balance_brl": float, "as_of": ISO8601}"""
        ...

    @abstractmethod
    def list_payables(self, from_date: str | None = None, to_date: str | None = None, limit: int = 50, page: int = 1) -> dict:
        """Returns make_list_response([make_payable_item(...)])"""
        ...

    @abstractmethod
    def list_receivables(self, from_date: str | None = None, to_date: str | None = None, limit: int = 50, page: int = 1) -> dict:
        """Returns make_list_response([make_receivable_item(...)])"""
        ...

    def list_overdue(self) -> dict:
        """Default: filter pending with due_date < today from payables + receivables."""
        from datetime import date
        today = date.today().isoformat()
        payables = self.list_payables(limit=200)
        receivables = self.list_receivables(limit=200)
        overdue = [
            i for i in payables["items"] + receivables["items"]
            if i.get("status") in ("pending", "overdue") and i.get("due_date", "9999") < today
        ]
        return make_list_response(overdue, total_count=len(overdue))

    def company_info(self) -> dict:
        return {"name": "N/A", "cnpj": None, "segment": None}

    def run_cli(self) -> None:
        command, kwargs = parse_cli_args()
        try:
            if command == "get_balance":
                emit(self.get_balance())
            elif command == "list_payables":
                emit(self.list_payables(
                    from_date=kwargs.get("from"),
                    to_date=kwargs.get("to"),
                    limit=int(kwargs.get("limit", 50)),
                    page=int(kwargs.get("page", 1)),
                ))
            elif command == "list_receivables":
                emit(self.list_receivables(
                    from_date=kwargs.get("from"),
                    to_date=kwargs.get("to"),
                    limit=int(kwargs.get("limit", 50)),
                    page=int(kwargs.get("page", 1)),
                ))
            elif command == "list_overdue":
                emit(self.list_overdue())
            elif command == "company_info":
                emit(self.company_info())
            else:
                emit_error(f"Comando desconhecido: {command}", code="unknown_command")
        except RuntimeError as e:
            emit_error(str(e))
        except Exception as e:
            emit_error(f"Erro interno: {e}", code="internal_error")


class BaseCRMClient(ABC):
    SKILL_NAME: str = ""

    def __init__(self):
        load_secrets(self.SKILL_NAME)
        self._validate_env()

    @abstractmethod
    def _validate_env(self) -> None: ...

    @abstractmethod
    def list_deals(self, status: str = "open", limit: int = 50, page: int = 1) -> dict:
        """Returns make_list_response([make_deal_item(...)])"""
        ...

    def pipeline_summary(self) -> dict:
        deals = self.list_deals(status="open", limit=500)
        by_stage: dict[str, dict] = {}
        total_open = 0.0
        for d in deals["items"]:
            stage = d.get("stage", "unknown")
            amt = d.get("amount_brl") or 0.0
            total_open += amt
            if stage not in by_stage:
                by_stage[stage] = {"count": 0, "total_brl": 0.0}
            by_stage[stage]["count"] += 1
            by_stage[stage]["total_brl"] += amt
        return {"total_open_brl": round(total_open, 2), "deal_count": len(deals["items"]), "by_stage": by_stage}

    def company_info(self) -> dict:
        return {"name": "N/A"}

    def run_cli(self) -> None:
        command, kwargs = parse_cli_args()
        try:
            if command == "list_deals":
                emit(self.list_deals(
                    status=kwargs.get("status", "open"),
                    limit=int(kwargs.get("limit", 50)),
                    page=int(kwargs.get("page", 1)),
                ))
            elif command == "pipeline_summary":
                emit(self.pipeline_summary())
            elif command == "company_info":
                emit(self.company_info())
            else:
                emit_error(f"Comando desconhecido: {command}", code="unknown_command")
        except RuntimeError as e:
            emit_error(str(e))
        except Exception as e:
            emit_error(f"Erro interno: {e}", code="internal_error")
