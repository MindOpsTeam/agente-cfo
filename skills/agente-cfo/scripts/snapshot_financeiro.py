#!/usr/bin/env python3
"""
snapshot_financeiro.py — Gerencia o snapshot financeiro de memória do Marcos.

Uso:
  python3 snapshot_financeiro.py --get            # retorna JSON do snapshot atual
  python3 snapshot_financeiro.py --set            # lê JSON de stdin, salva
  python3 snapshot_financeiro.py --diff           # lê JSON novo de stdin, retorna delta %
  python3 snapshot_financeiro.py --update-now     # captura dados do ERP e atualiza snapshot

O snapshot fica em ~/.agente-cfo/memory/snapshot-financeiro.json
"""
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

MEMORY_DIR = Path.home() / ".agente-cfo" / "memory"
SNAPSHOT_FILE = MEMORY_DIR / "snapshot-financeiro.json"
SCRIPTS_DIR = Path(__file__).parent


def load() -> dict:
    if SNAPSHOT_FILE.exists():
        try:
            return json.loads(SNAPSHOT_FILE.read_text())
        except Exception:
            pass
    return {}


def save(data: dict):
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    data["_saved_at"] = datetime.now().isoformat()
    SNAPSHOT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def run_erp(cmd: list[str]) -> dict:
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
        capture_output=True, text=True, timeout=30,
        cwd=str(SCRIPTS_DIR),
    )
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {}


def capture_now() -> dict:
    """Captura saldo + payables + receivables + overdue do ERP e retorna snapshot."""
    today = date.today()
    mes_ini = today.replace(day=1).isoformat()
    mes_fim = today.isoformat()

    bal = run_erp(["get_balance"])
    pay = run_erp(["list_payables", "--from", mes_ini, "--to", mes_fim, "--limit", "200"])
    rec = run_erp(["list_receivables", "--from", mes_ini, "--to", mes_fim, "--limit", "200"])
    over = run_erp(["list_overdue"])

    def sum_r(r):
        lst = r.get("records") or r.get("items") or r.get("data") or []
        if not isinstance(lst, list): return 0.0
        return sum(float(x.get("amount_brl") or x.get("amount") or x.get("valor") or 0)
                   for x in lst if isinstance(x, dict))

    balance = float(
        bal.get("balance") or bal.get("saldo") or bal.get("saldo_total") or 0
    )
    total_pay = sum_r(pay)
    total_rec = sum_r(rec)
    total_over = sum_r(over)
    days = max(today.day, 1)
    burn = (total_pay / days) * 30
    runway = round(balance / burn, 1) if burn > 0 else 99.0
    inad_pct = round(total_over / max(total_rec + total_over, 1) * 100, 1)

    return {
        "date": today.isoformat(),
        "balance": balance,
        "total_payables_mes": total_pay,
        "total_receivables_mes": total_rec,
        "total_overdue": total_over,
        "burn_mensal_estimado": round(burn, 2),
        "runway_meses": runway,
        "inadimplencia_pct": inad_pct,
    }


def compute_diff(current: dict, previous: dict) -> dict:
    """Retorna delta percentual entre current e previous para campos numéricos."""
    diff = {}
    for k, v in current.items():
        if k.startswith("_") or not isinstance(v, (int, float)):
            continue
        prev_v = previous.get(k)
        if prev_v is None or not isinstance(prev_v, (int, float)) or prev_v == 0:
            diff[k] = {"current": v, "previous": None, "delta_pct": None}
        else:
            pct = round((v - prev_v) / abs(prev_v) * 100, 1)
            diff[k] = {"current": v, "previous": prev_v, "delta_pct": pct}
    return diff


def main():
    mode = None
    for arg in sys.argv[1:]:
        if arg in ("--get", "--set", "--diff", "--update-now"):
            mode = arg

    if mode is None or mode == "--get":
        snap = load()
        print(json.dumps(snap, indent=2, ensure_ascii=False))

    elif mode == "--set":
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"JSON inválido: {e}"}))
            sys.exit(1)
        save(data)
        print(json.dumps({"ok": True, "saved_at": data.get("_saved_at", "")}))

    elif mode == "--diff":
        try:
            new_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"JSON inválido: {e}"}))
            sys.exit(1)
        previous = load()
        diff = compute_diff(new_data, previous)
        print(json.dumps(diff, indent=2, ensure_ascii=False))

    elif mode == "--update-now":
        current = capture_now()
        previous = load()
        diff = compute_diff(current, previous)
        save(current)
        print(json.dumps({"snapshot": current, "diff": diff}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
