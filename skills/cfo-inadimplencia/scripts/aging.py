#!/usr/bin/env python3
"""
aging.py — Aging report de inadimplência por bucket de dias vencidos.

Uso:
  python3 aging.py               # texto WA-friendly
  python3 aging.py --format json
  python3 aging.py --detalhe     # lista individual (pode ser longo)
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"
DETALHE = False
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--detalhe": DETALHE = True; i += 1
    else: i += 1

BUCKETS = [
    ("0–7d",   0,   7,  "🟡 Lembrete amigável"),
    ("8–30d",  8,  30,  "🟠 1ª notificação"),
    ("31–60d", 31, 60,  "🔴 Boleto novo + contato"),
    ("61–90d", 61, 90,  "🆘 Escalation jurídico"),
    (">90d",   91, 9999,"☠️  Provisionar / judicial"),
]

def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def main():
    today = date.today()
    overdue_r = run_erp(["list_overdue"])
    items = overdue_r.get("records") or overdue_r.get("items") or overdue_r.get("data") or []
    if not isinstance(items, list): items = []

    buckets_data = {name: {"total": 0, "count": 0, "items": []} for name, *_ in BUCKETS}
    total_geral = 0

    for item in items:
        if not isinstance(item, dict): continue
        due = item.get("due_date") or item.get("vencimento") or item.get("data_vencimento") or ""
        try:
            due_d = date.fromisoformat(str(due)[:10])
            dias = (today - due_d).days
        except Exception:
            dias = 0
        val = float(item.get("amount_brl") or item.get("amount") or item.get("valor") or 0)
        total_geral += val

        for name, lo, hi, _ in BUCKETS:
            if lo <= dias <= hi:
                buckets_data[name]["total"] += val
                buckets_data[name]["count"] += 1
                buckets_data[name]["items"].append({
                    "nome": item.get("supplier") or item.get("customer") or item.get("nome") or "?",
                    "valor": val, "dias": dias
                })
                break

    result = {
        "date": today.isoformat(),
        "total_overdue": total_geral,
        "total_items": len(items),
        "buckets": {
            name: {"total": b["total"], "count": b["count"],
                   "pct": round(b["total"] / total_geral * 100, 1) if total_geral else 0}
            for name, b in buckets_data.items()
        },
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"⚠️  Aging de Inadimplência — {today.strftime('%d/%m/%Y')}")
    print(f"   Total vencido: {fmt(total_geral)} em {len(items)} registros")
    print()
    for name, lo, hi, acao in BUCKETS:
        b = buckets_data[name]
        if b["count"] == 0: continue
        pct = (b["total"] / total_geral * 100) if total_geral else 0
        print(f"  [{name:7}] {fmt(b['total']):>15} ({b['count']:2}x) {pct:.0f}%  → {acao}")
        if DETALHE:
            for item in sorted(b["items"], key=lambda x: x["valor"], reverse=True)[:5]:
                print(f"    • {item['nome'][:25]:<25} {fmt(item['valor']):<12} ({item['dias']}d)")

if __name__ == "__main__":
    main()
