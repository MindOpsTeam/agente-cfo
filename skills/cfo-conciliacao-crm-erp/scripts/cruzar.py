#!/usr/bin/env python3
"""
cruzar.py — Conciliação CRM Deals Won vs receita ERP.

Uso:
  python3 cruzar.py --periodo 60
  python3 cruzar.py --format json
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

FORMAT = "text"
PERIODO = 60
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
        return {"error": f"{gw} não encontrado"}
    r = subprocess.run(["python3", str(s)] + cmd, capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {"error": r.stdout[:200]}


def extract_list(r: dict) -> list:
    for k in ("deals", "records", "items", "data"):
        if r.get(k) and isinstance(r[k], list): return r[k]
    return []


def sf(v) -> float:
    try: return float(v or 0)
    except: return 0.0


def ed(item: dict, keys=None) -> str:
    keys = keys or ("close_date", "closeDate", "won_date", "wonDate", "date", "created_at")
    for k in keys:
        if item.get(k): return str(item[k])[:10]
    return ""


def ea(item: dict) -> float:
    for k in ("amount", "value", "amount_brl", "valor", "dealValue"):
        if item.get(k) is not None: return sf(item[k])
    return 0.0


def fmt(v): return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    today = date.today()
    start = (today - timedelta(days=PERIODO)).isoformat()
    end = today.isoformat()

    # CRM: deals won no período
    crm_r = run_gw("crm", ["list_deals", "--status", "won", "--limit", "100"])
    deals_all = extract_list(crm_r)
    deals_won = [d for d in deals_all if start <= ed(d) <= end]

    # ERP: receitas do período + janela de 30d após
    erp_end = min((today + timedelta(days=30)).isoformat(), today.isoformat())
    erp_r = run_gw("erp", ["list_receivables", "--from", start, "--to", erp_end, "--limit", "300"])
    erp_items = (erp_r.get("records") or erp_r.get("items") or erp_r.get("data") or [])
    if not isinstance(erp_items, list): erp_items = []

    matched_erp = set()
    match_ok = []
    deal_sem_receita = []

    for deal in deals_won:
        val = ea(deal)
        close = ed(deal)
        if not close: continue

        # Janela: close até close+30d
        try:
            close_d = date.fromisoformat(close)
            window_end = (close_d + timedelta(days=30)).isoformat()
        except: continue

        found = False
        for j, erp in enumerate(erp_items):
            if j in matched_erp: continue
            erp_val = ea(erp)
            erp_d = ed(erp, ("due_date", "date", "competencia", "created_at"))
            if not erp_d or not (close <= erp_d <= window_end): continue
            # Valor: tolerância 20% (deal pode ser parcelado)
            if val > 0 and erp_val > 0 and abs(val - erp_val) / max(val, erp_val) <= 0.20:
                match_ok.append({
                    "deal_id": str(deal.get("id") or ""),
                    "deal_title": str(deal.get("title") or deal.get("name") or ""),
                    "erp_id": str(erp.get("id") or ""),
                    "valor": val,
                    "close_date": close,
                })
                matched_erp.add(j)
                found = True
                break
        if not found and val > 0:
            deal_sem_receita.append({
                "deal_id": str(deal.get("id") or ""),
                "titulo": str(deal.get("title") or deal.get("name") or "Deal sem título"),
                "valor": val,
                "close_date": close,
                "cliente": str(deal.get("company") or deal.get("contact") or deal.get("customer") or "?"),
            })

    result = {
        "periodo_dias": PERIODO, "periodo": f"{start} a {end}",
        "deals_won": len(deals_won),
        "match_ok": len(match_ok),
        "deal_sem_receita": deal_sem_receita,
        "divergencias": len(deal_sem_receita),
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🤝 Conciliação CRM ↔ ERP — últimos {PERIODO} dias")
    print(f"  Deals Won: {len(deals_won)} | Conciliados: {len(match_ok)}")
    if deal_sem_receita:
        print(f"\n  ❌ Deals sem receita no ERP ({len(deal_sem_receita)}):")
        for d in deal_sem_receita[:5]:
            print(f"    • {d['titulo'][:35]:<35} {fmt(d['valor'])} — fechado {d['close_date']}")
        if len(deal_sem_receita) > 5:
            print(f"    ... +{len(deal_sem_receita)-5} outros")
    else:
        print(f"\n  ✅ Todos os {len(match_ok)} deals won converteram em receita ERP.")


if __name__ == "__main__":
    main()
