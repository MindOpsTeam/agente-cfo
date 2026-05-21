#!/usr/bin/env python3
"""
cruzar.py — Conciliação cobrança (Asaas/Iugu) vs ERP (Omie/Bling/etc).

Uso:
  python3 cruzar.py --periodo 30          # últimos 30 dias
  python3 cruzar.py --periodo 7           # última semana
  python3 cruzar.py --format json         # output JSON estruturado
  python3 cruzar.py --format text         # output WA-friendly
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
PERIODO = 30
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--formato" and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--format" and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--periodo" and i + 1 < len(sys.argv):
        PERIODO = int(sys.argv[i + 1]); i += 2
    else:
        i += 1


def run_gateway(gateway: str, cmd: list[str]) -> dict:
    script = SCRIPTS_DIR / f"{gateway}_gateway.py"
    if not script.exists():
        return {"error": f"{gateway}_gateway.py não encontrado"}
    r = subprocess.run(
        ["python3", str(script)] + cmd,
        capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR),
    )
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {"error": r.stdout[:200]}


def extract_list(r: dict) -> list:
    lst = r.get("records") or r.get("items") or r.get("data") or r.get("payments") or []
    return lst if isinstance(lst, list) else []


def safe_float(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def fmt(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def values_match(a: float, b: float, tolerance_pct: float = 2.0, abs_tol: float = 5.0) -> bool:
    """Considera match se diferença < tolerance_pct% OU < abs_tol."""
    diff = abs(a - b)
    if diff <= abs_tol:
        return True
    if min(a, b) > 0:
        pct = diff / min(a, b) * 100
        return pct <= tolerance_pct
    return False


def dates_match(d1: str, d2: str, window: int = 3) -> bool:
    """Datas compatíveis se diferença <= window dias."""
    try:
        dt1 = date.fromisoformat(str(d1)[:10])
        dt2 = date.fromisoformat(str(d2)[:10])
        return abs((dt1 - dt2).days) <= window
    except Exception:
        return False


def extract_amount(item: dict) -> float:
    for key in ("value", "amount", "amount_brl", "valor", "netAmount", "totalAmount"):
        if item.get(key) is not None:
            return safe_float(item[key])
    return 0.0


def extract_date(item: dict) -> str:
    for key in ("paymentDate", "dueDate", "due_date", "confirmedDate", "data",
                "date", "competencia", "created_at"):
        if item.get(key):
            return str(item[key])[:10]
    return ""


def main():
    today = date.today()
    start = (today - timedelta(days=PERIODO)).isoformat()
    end = today.isoformat()

    # Lê pagamentos confirmados da cobrança
    cobranca_r = run_gateway("cobranca", [
        "list_invoices", "--status", "paid", "--limit", "200"
    ])
    cobranca_items = extract_list(cobranca_r)

    # Lê recebimentos no ERP
    erp_r = run_gateway("erp", [
        "list_receivables", "--from", start, "--to", end, "--limit", "200"
    ])
    erp_items = extract_list(erp_r)

    # Filtra cobrança pelo período
    cobranca_period = []
    for item in cobranca_items:
        d = extract_date(item)
        if d and start <= d <= end:
            cobranca_period.append(item)

    # Match por valor + data
    matched_erp_idx = set()
    match_ok = []
    pago_so_cobranca = []

    for cob in cobranca_period:
        cob_val = extract_amount(cob)
        cob_date = extract_date(cob)
        found = False
        for j, erp in enumerate(erp_items):
            if j in matched_erp_idx:
                continue
            erp_val = extract_amount(erp)
            erp_date = extract_date(erp)
            if values_match(cob_val, erp_val) and dates_match(cob_date, erp_date):
                match_ok.append({
                    "cobranca_id": str(cob.get("id") or cob.get("codigo") or ""),
                    "erp_id": str(erp.get("id") or erp.get("codigo") or ""),
                    "valor": cob_val,
                    "data": cob_date,
                })
                matched_erp_idx.add(j)
                found = True
                break
        if not found:
            pago_so_cobranca.append({
                "cobranca_id": str(cob.get("id") or ""),
                "valor": cob_val,
                "data": cob_date,
                "cliente": str(cob.get("customer") or cob.get("name") or cob.get("clientName") or "?"),
                "descricao": str(cob.get("description") or cob.get("billingType") or ""),
            })

    recebido_so_erp = [
        {
            "erp_id": str(erp.get("id") or ""),
            "valor": extract_amount(erp),
            "data": extract_date(erp),
            "cliente": str(erp.get("customer") or erp.get("nome") or "?"),
        }
        for j, erp in enumerate(erp_items)
        if j not in matched_erp_idx
    ]

    result = {
        "periodo_dias": PERIODO,
        "periodo": f"{start} a {end}",
        "total_cobranca": len(cobranca_period),
        "total_erp": len(erp_items),
        "match_ok": len(match_ok),
        "pago_so_cobranca": pago_so_cobranca,
        "recebido_so_erp": recebido_so_erp,
        "divergencias": len(pago_so_cobranca) + len(recebido_so_erp),
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False))
        return

    print(f"🔀 Conciliação Cobrança ↔ ERP — últimos {PERIODO} dias")
    print(f"  Cobrança: {len(cobranca_period)} itens | ERP: {len(erp_items)} itens | Match OK: {len(match_ok)}")
    print()
    if pago_so_cobranca:
        print(f"  ❌ Pago na cobrança mas SEM lançamento no ERP ({len(pago_so_cobranca)}):")
        for item in pago_so_cobranca[:5]:
            print(f"    • {item['cliente'][:30]:<30} {fmt(item['valor'])} em {item['data']}")
        if len(pago_so_cobranca) > 5:
            print(f"    ... +{len(pago_so_cobranca) - 5} outros")
    if recebido_so_erp:
        print(f"  ⚠️  Recebido no ERP sem boleto correspondente ({len(recebido_so_erp)}):")
        for item in recebido_so_erp[:5]:
            print(f"    • {item['cliente'][:30]:<30} {fmt(item['valor'])} em {item['data']}")
    if not pago_so_cobranca and not recebido_so_erp:
        print(f"  ✅ Sem divergências — todos os {len(match_ok)} pagamentos conciliados.")


if __name__ == "__main__":
    main()
