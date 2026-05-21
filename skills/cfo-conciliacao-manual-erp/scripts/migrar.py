#!/usr/bin/env python3
"""
migrar.py — Migra lançamentos dashboard_only para o ERP real.

Uso:
  python3 migrar.py --dry-run           # mostra plano sem executar
  python3 migrar.py --executar          # executa (requer --dry-run prévio + SIM do dono)
  python3 migrar.py --skill omie        # força skill ERP específica
  python3 migrar.py --format json

ATENÇÃO: Sempre apresentar --dry-run ao dono antes de executar.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path.home() / ".agente-cfo" / ".env"
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

DRY_RUN = True
FORMAT = "text"
SKILL_OVERRIDE = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--dry-run": DRY_RUN = True; i += 1
    elif a == "--executar": DRY_RUN = False; i += 1
    elif a in ("--format", "--formato") and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--skill" and i + 1 < len(sys.argv): SKILL_OVERRIDE = sys.argv[i + 1]; i += 2
    else: i += 1

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PANEL_BASE_URL = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
PANEL_TOKEN = os.environ.get("PANEL_TOKEN", "")
ERP_NAME = SKILL_OVERRIDE or os.environ.get("CFO_ERP_NAME", "omie")


def fetch_pending() -> list:
    if not PANEL_BASE_URL or not PANEL_TOKEN:
        return []
    base = PANEL_BASE_URL.replace("/functions/v1", "")
    url = (f"{base}/rest/v1/cfo_write_events"
           f"?erp=eq.dashboard_only&erp_record_id=is.null"
           f"&status=eq.success&order=created_at.asc&limit=50")
    try:
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {PANEL_TOKEN}", "apikey": PANEL_TOKEN})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except: return []


def run_erp(cmd: list) -> dict:
    script = SCRIPTS_DIR / "erp_gateway.py"
    r = subprocess.run(["python3", str(script)] + cmd, capture_output=True, text=True,
                       timeout=30, cwd=str(SCRIPTS_DIR))
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {"error": r.stdout[:200]}


def update_panel_record(record_id: str, erp_record_id: str):
    """Atualiza cfo_write_events com erp e erp_record_id real."""
    if not PANEL_BASE_URL or not PANEL_TOKEN:
        return
    base = PANEL_BASE_URL.replace("/functions/v1", "")
    url = f"{base}/rest/v1/cfo_write_events?id=eq.{record_id}"
    body = json.dumps({"erp": ERP_NAME, "erp_record_id": erp_record_id}).encode()
    try:
        req = urllib.request.Request(
            url, data=body, method="PATCH",
            headers={"Authorization": f"Bearer {PANEL_TOKEN}", "apikey": PANEL_TOKEN,
                     "Content-Type": "application/json", "Prefer": "return=minimal"})
        urllib.request.urlopen(req, timeout=10)
    except: pass


def fmt(v): return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    pending = fetch_pending()
    if not pending:
        msg = "✅ Nenhum lançamento pendente" if PANEL_BASE_URL else "⚠️ PANEL_BASE_URL não configurado"
        print(json.dumps({"pending": 0, "message": msg}) if FORMAT == "json" else msg)
        return

    mode = "DRY-RUN" if DRY_RUN else "EXECUÇÃO"
    results = []

    for item in pending:
        action = item.get("action", "create_payable")
        amount = item.get("amount") or 0
        supplier = item.get("supplier") or ""
        due_date = item.get("due_date") or ""
        category = item.get("category") or ""
        record_id = str(item.get("id") or "")

        cmd = [action, "--amount", str(amount), "--due_date", due_date, "--supplier", supplier]
        if category: cmd += ["--category", category]

        if DRY_RUN:
            results.append({"id": record_id, "action": action, "amount": amount,
                             "supplier": supplier, "dry_run": True})
            if FORMAT == "text":
                print(f"  📝 {action:<20} {fmt(amount):<14} {supplier[:30]:<30} {due_date}")
        else:
            resp = run_erp(cmd)
            ok = resp.get("success") and not resp.get("error_kind")
            erp_id = str(resp.get("erp_record_id") or resp.get("id") or "")
            if ok and erp_id:
                update_panel_record(record_id, erp_id)
            results.append({"id": record_id, "action": action, "amount": amount,
                             "supplier": supplier, "ok": ok, "erp_id": erp_id,
                             "response": resp})
            marker = "✅" if ok else "❌"
            if FORMAT == "text":
                print(f"  {marker} {action:<20} {fmt(amount):<14} {supplier[:25]:<25} → {erp_id or resp.get('error_kind','?')}")

    if FORMAT == "json":
        print(json.dumps({"mode": mode, "total": len(pending), "results": results}, ensure_ascii=False))
        return

    if DRY_RUN:
        total = sum(float(x.get("amount") or 0) for x in pending)
        print(f"\n  {len(pending)} lançamentos / {fmt(total)} — ⚠️ Apenas plano, nada foi executado.")
        print(f"  Para executar: 'migra os lançamentos' + SIM")
    else:
        ok_count = sum(1 for r in results if r.get("ok"))
        print(f"\n  {ok_count}/{len(pending)} migrações concluídas com sucesso.")


if __name__ == "__main__":
    main()
