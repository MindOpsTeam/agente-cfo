#!/usr/bin/env python3
"""
cruzar.py — Conciliação e-commerce (ML/Nuvemshop) vs ERP (receita).

Uso:
  python3 cruzar.py --periodo 30
  python3 cruzar.py --format json
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
    if a in ("--format", "--formato") and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--periodo" and i + 1 < len(sys.argv):
        PERIODO = int(sys.argv[i + 1]); i += 2
    else:
        i += 1


def run_gw(gw: str, cmd: list) -> dict:
    s = SCRIPTS_DIR / f"{gw}_gateway.py"
    if not s.exists():
        return {"error": f"{gw}_gateway.py não encontrado"}
    r = subprocess.run(["python3", str(s)] + cmd, capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except Exception:
        return {"error": r.stdout[:200]}


def extract_list(r: dict) -> list:
    lst = r.get("records") or r.get("items") or r.get("data") or r.get("orders") or []
    return lst if isinstance(lst, list) else []


def sf(v) -> float:
    try: return float(v or 0)
    except: return 0.0


def ea(item: dict) -> float:
    for k in ("total", "amount", "amount_brl", "valor", "totalAmount", "price"):
        if item.get(k) is not None: return sf(item[k])
    return 0.0


def ed(item: dict) -> str:
    for k in ("created_at", "date", "date_created", "data", "paidAt", "order_date"):
        if item.get(k): return str(item[k])[:10]
    return ""


def values_match(a: float, b: float) -> bool:
    if min(a, b) <= 0: return False
    return abs(a - b) / min(a, b) <= 0.10  # 10% tolerance para taxas


def dates_match(d1: str, d2: str, window: int = 5) -> bool:
    try:
        return abs((date.fromisoformat(d1) - date.fromisoformat(d2)).days) <= window
    except: return False


def fmt(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    today = date.today()
    start = (today - timedelta(days=PERIODO)).isoformat()
    end = today.isoformat()

    # E-commerce: vendas pagas
    ecom_r = run_gw("ecommerce", ["list_orders", "--status", "paid", "--limit", "200"])
    ecom_items = [x for x in extract_list(ecom_r)
                  if x.get("created_at") or x.get("date_created") or x.get("date")]
    ecom_period = [x for x in ecom_items if start <= ed(x) <= end]

    # ERP: receitas
    erp_r = run_gw("erp", ["list_receivables", "--from", start, "--to", end, "--limit", "200"])
    erp_items = extract_list(erp_r)

    matched_erp = set()
    match_ok = []
    venda_sem_nf = []

    for item in ecom_period:
        val = ea(item)
        d = ed(item)
        found = False
        for j, erp in enumerate(erp_items):
            if j in matched_erp: continue
            if values_match(val, ea(erp)) and dates_match(d, ed(erp)):
                match_ok.append({"ecom_id": str(item.get("id") or ""), "erp_id": str(erp.get("id") or ""), "valor": val})
                matched_erp.add(j)
                found = True
                break
        if not found:
            venda_sem_nf.append({
                "ecom_id": str(item.get("id") or ""),
                "valor": val,
                "data": d,
                "descricao": str(item.get("title") or item.get("description") or item.get("name") or "Venda"),
            })

    receita_sem_venda = [
        {"erp_id": str(e.get("id") or ""), "valor": ea(e), "data": ed(e),
         "cliente": str(e.get("customer") or e.get("nome") or "?")}
        for j, e in enumerate(erp_items) if j not in matched_erp
    ]

    result = {
        "periodo_dias": PERIODO, "periodo": f"{start} a {end}",
        "total_ecommerce": len(ecom_period), "total_erp": len(erp_items),
        "match_ok": len(match_ok),
        "venda_sem_nf_erp": venda_sem_nf,
        "receita_erp_sem_venda": receita_sem_venda,
        "divergencias": len(venda_sem_nf) + len(receita_sem_venda),
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🛒 Conciliação E-commerce ↔ ERP — últimos {PERIODO} dias")
    print(f"  E-commerce: {len(ecom_period)} | ERP: {len(erp_items)} | Match: {len(match_ok)}")
    if venda_sem_nf:
        print(f"\n  ❌ Vendas SEM lançamento no ERP ({len(venda_sem_nf)}):")
        for x in venda_sem_nf[:5]:
            print(f"    • #{x['ecom_id'][:8]:<10} {fmt(x['valor'])} em {x['data']} — {x['descricao'][:30]}")
    if receita_sem_venda:
        print(f"\n  ⚠️  Receita no ERP sem venda correspondente ({len(receita_sem_venda)}):")
        for x in receita_sem_venda[:5]:
            print(f"    • {x['cliente'][:30]:<30} {fmt(x['valor'])} em {x['data']}")
    if not venda_sem_nf and not receita_sem_venda:
        print(f"\n  ✅ Sem divergências — {len(match_ok)} vendas conciliadas.")


if __name__ == "__main__":
    main()
