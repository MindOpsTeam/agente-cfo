#!/usr/bin/env python3
"""
sugestao_cobranca.py — Gera lista priorizada de ações de cobrança por bucket.

Não executa as cobranças (isso é do cfo-cobranca-orquestrada).
Aqui apenas SUGERE quem/como cobrar, em formato legível pra Marcos apresentar ao dono.
"""
import json
import subprocess
import sys
from datetime import date
from collections import defaultdict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
FORMAT = "text"
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    else: i += 1

ACOES = [
    (0,   7,  "Lembrete amigável via WhatsApp"),
    (8,  30,  "Notificação formal — boleto + link pagamento"),
    (31, 60,  "Ligação + boleto novo (sem juros adicionais por ora)"),
    (61, 90,  "Escalation — avisar sobre encaminhamento jurídico"),
    (91, 9999,"Provisionar perda + cobrar via advogado"),
]

def run_erp(cmd):
    r = subprocess.run(["python3", str(SCRIPTS_DIR / "erp_gateway.py")] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def main():
    today = date.today()
    r = run_erp(["list_overdue"])
    items = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(items, list): items = []

    groups = defaultdict(list)
    for item in items:
        if not isinstance(item, dict): continue
        due = item.get("due_date") or item.get("vencimento") or ""
        try: dias = (today - date.fromisoformat(str(due)[:10])).days
        except: dias = 0
        for lo, hi, acao in ACOES:
            if lo <= dias <= hi:
                groups[acao].append({
                    "nome": item.get("customer") or item.get("cliente") or "?",
                    "valor": float(item.get("amount_brl") or item.get("amount") or 0),
                    "dias": dias, "id": item.get("id") or item.get("codigo") or "",
                })
                break

    sugestoes = [{"acao": acao, "total": sum(x["valor"] for x in lst), "count": len(lst), "items": lst}
                 for acao, lst in groups.items() if lst]

    if FORMAT == "json":
        print(json.dumps({"date": today.isoformat(), "sugestoes": sugestoes}, ensure_ascii=False))
        return

    print(f"📋 Sugestão de Cobrança — {today.strftime('%d/%m/%Y')}")
    print()
    for s in sorted(sugestoes, key=lambda x: ACOES.index(next((a for a in ACOES if a[2] == x["acao"]), ACOES[0]))):
        print(f"  ▶ {s['acao']}")
        print(f"    {s['count']} clientes · {fmt(s['total'])}")
        for it in sorted(s["items"], key=lambda x: x["valor"], reverse=True)[:5]:
            print(f"    • {it['nome'][:30]:<30} {fmt(it['valor'])} ({it['dias']}d)")
        print()
    print("  ⚠ Para executar cobranças: 'execute cobrança agora' ou cfo-cobranca-orquestrada")

if __name__ == "__main__":
    main()
