#!/usr/bin/env python3
"""
kpis.py — KPIs financeiros: DSO, DPO, CCC, Working Capital, Runway, Burn.

Uso:
  python3 kpis.py                        # todos os KPIs
  python3 kpis.py --kpi dso              # KPI específico
  python3 kpis.py --format json          # output JSON

Lê dados via erp_gateway.py (usa CFO_ERP_NAME do .env).
Compara com memory/snapshot-financeiro.json se existir.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
MEMORY_DIR = Path.home() / ".agente-cfo" / "memory"
SNAPSHOT_FILE = MEMORY_DIR / "snapshot-financeiro.json"

FORMAT = "text"
FILTER_KPI = None
for i, arg in enumerate(sys.argv[1:]):
    if arg == "--format" and i + 1 < len(sys.argv) - 1:
        FORMAT = sys.argv[i + 2]
    if arg == "--kpi" and i + 1 < len(sys.argv) - 1:
        FILTER_KPI = sys.argv[i + 2]


def run_erp(cmd: list[str]) -> dict:
    r = subprocess.run(
        ["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
        capture_output=True, text=True, timeout=30,
        cwd=str(SCRIPTS_DIR),
    )
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"error": r.stdout[:200]}


def safe_float(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def sum_amounts(records: list, key: str = "amount_brl") -> float:
    return sum(safe_float(r.get(key) or r.get("amount") or r.get("valor") or 0)
               for r in records if isinstance(r, dict))


def load_snapshot() -> dict:
    if SNAPSHOT_FILE.exists():
        try:
            return json.loads(SNAPSHOT_FILE.read_text())
        except Exception:
            pass
    return {}


def save_snapshot(data: dict):
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def format_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def delta_str(current: float, prev: float) -> str:
    if prev == 0:
        return ""
    pct = ((current - prev) / abs(prev)) * 100
    sign = "▲" if pct > 0 else "▼"
    return f" ({sign}{abs(pct):.1f}% vs anterior)"


def main():
    today = date.today()
    mes_inicio = today.replace(day=1).isoformat()
    mes_fim = today.isoformat()

    # Coleta dados do ERP
    balance_r = run_erp(["get_balance"])
    payables_r = run_erp(["list_payables", "--from", mes_inicio, "--to", mes_fim, "--limit", "200"])
    receivables_r = run_erp(["list_receivables", "--from", mes_inicio, "--to", mes_fim, "--limit", "200"])
    overdue_r = run_erp(["list_overdue"])

    balance = safe_float(
        balance_r.get("balance") or balance_r.get("saldo") or
        balance_r.get("saldo_total") or balance_r.get("total")
    )

    payables_list = payables_r.get("records") or payables_r.get("items") or \
                    payables_r.get("data") or ([] if "error" in payables_r else [payables_r])
    receivables_list = receivables_r.get("records") or receivables_r.get("items") or \
                       receivables_r.get("data") or ([] if "error" in receivables_r else [receivables_r])
    overdue_list = overdue_r.get("records") or overdue_r.get("items") or \
                   overdue_r.get("data") or []

    total_payables = sum_amounts(payables_list if isinstance(payables_list, list) else [])
    total_receivables = sum_amounts(receivables_list if isinstance(receivables_list, list) else [])
    total_overdue = sum_amounts(overdue_list if isinstance(overdue_list, list) else [])

    # KPIs
    days_in_period = max(today.day, 1)

    # DSO: dias médios pra receber (aproximação com dados do mês)
    dso = (total_receivables / max(total_receivables + total_payables, 1)) * 30 \
        if total_receivables > 0 else 0

    # DPO: dias médios pra pagar
    dpo = (total_payables / max(total_receivables + total_payables, 1)) * 30 \
        if total_payables > 0 else 0

    # CCC
    ccc = dso - dpo

    # Working capital (aproximação: receivables - payables)
    working_capital = total_receivables - total_payables

    # Burn: total payables do mês / dias corridos → mensal estimado
    burn_mensal = (total_payables / days_in_period) * 30 if days_in_period > 0 else total_payables

    # Runway
    runway_meses = (balance / burn_mensal) if burn_mensal > 0 else 99.0

    # Inadimplência %
    inadimplencia_pct = (total_overdue / max(total_receivables + total_overdue, 1)) * 100

    snapshot_prev = load_snapshot()
    prev_balance = safe_float(snapshot_prev.get("balance"))
    prev_receivables = safe_float(snapshot_prev.get("total_receivables"))

    kpis = {
        "date": today.isoformat(),
        "balance": balance,
        "total_payables_mes": total_payables,
        "total_receivables_mes": total_receivables,
        "total_overdue": total_overdue,
        "dso_dias": round(dso, 1),
        "dpo_dias": round(dpo, 1),
        "ccc_dias": round(ccc, 1),
        "working_capital": working_capital,
        "burn_mensal_estimado": burn_mensal,
        "runway_meses": round(runway_meses, 1),
        "inadimplencia_pct": round(inadimplencia_pct, 1),
    }

    # Salva snapshot
    save_snapshot({**kpis, "saved_at": datetime.now().isoformat()})

    if FORMAT == "json":
        print(json.dumps(kpis, ensure_ascii=False))
        return

    # Texto WA-friendly
    runway_signal = "🔴" if runway_meses < 2 else ("🟡" if runway_meses < 4 else "🟢")
    inad_signal = "🔴" if inadimplencia_pct > 15 else ("🟡" if inadimplencia_pct > 8 else "🟢")
    wc_signal = "🔴" if working_capital < 0 else ("🟡" if working_capital < burn_mensal else "🟢")

    lines = [
        f"📊 KPIs Financeiros — {today.strftime('%d/%m/%Y')}",
        f"",
        f"Caixa: {format_brl(balance)}{delta_str(balance, prev_balance)}",
        f"A receber (mês): {format_brl(total_receivables)}{delta_str(total_receivables, prev_receivables)}",
        f"A pagar (mês): {format_brl(total_payables)}",
        f"Vencidas: {format_brl(total_overdue)} {inad_signal} ({inadimplencia_pct:.1f}% inadimplência)",
        f"",
        f"Runway: {runway_meses:.1f} meses {runway_signal}",
        f"Burn estimado: {format_brl(burn_mensal)}/mês",
        f"Capital de giro: {format_brl(working_capital)} {wc_signal}",
        f"",
        f"DSO: {dso:.0f}d | DPO: {dpo:.0f}d | CCC: {ccc:.0f}d",
    ]

    if FILTER_KPI:
        val = kpis.get(FILTER_KPI)
        print(f"{FILTER_KPI}: {val}")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
