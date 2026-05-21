#!/usr/bin/env python3
"""
orquestrar_cobranca.py — Workflow agentic de cobrança em lote.

Uso:
  python3 orquestrar_cobranca.py --dry-run         # mostra o plano sem executar
  python3 orquestrar_cobranca.py --executar        # executa (requer --dry-run prévio)
  python3 orquestrar_cobranca.py --bucket 0-30     # filtra bucket específico
  python3 orquestrar_cobranca.py --max 20          # limita registros por execução
  python3 orquestrar_cobranca.py --format json

ATENÇÃO: sempre apresentar --dry-run ao dono antes de --executar.
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"

DRY_RUN = True
FORMAT = "text"
BUCKET_FILTER = None
MAX = 50
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--dry-run": DRY_RUN = True; i += 1
    elif a == "--executar": DRY_RUN = False; i += 1
    elif a == "--format" and i+1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--bucket" and i+1 < len(sys.argv): BUCKET_FILTER = sys.argv[i+1]; i += 2
    elif a == "--max" and i+1 < len(sys.argv): MAX = int(sys.argv[i+1]); i += 2
    else: i += 1

POLITICA = [
    ("0-7",   0,  7,  "send_payment_link",  "Lembrete amigável"),
    ("8-30",  8,  30, "send_payment_link",  "Notificação formal"),
    ("31-60", 31, 60, "send_payment_link",  "Boleto novo + cobrança"),
    (">60",   61, 9999, None,               "Análise manual — não executa automaticamente"),
]

def run_gateway(gateway: str, cmd: list[str]) -> dict:
    script = SCRIPTS_DIR / f"{gateway}_gateway.py"
    if not script.exists(): return {"error": f"{gateway}_gateway.py não encontrado"}
    r = subprocess.run(["python3", str(script)] + cmd,
                       capture_output=True, text=True, timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {"error": r.stdout[:200]}

def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def main():
    today = date.today()

    # Busca overdue via erp_gateway
    r = run_gateway("erp", ["list_overdue"])
    items = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(items, list): items = []

    plano = []
    for item in items[:MAX]:
        if not isinstance(item, dict): continue
        due = item.get("due_date") or item.get("vencimento") or ""
        try: dias = (today - date.fromisoformat(str(due)[:10])).days
        except: dias = 0
        val = float(item.get("amount_brl") or item.get("amount") or item.get("valor") or 0)
        invoice_id = str(item.get("id") or item.get("codigo") or "")
        customer_id = str(item.get("customer_id") or item.get("cliente_id") or "")
        nome = item.get("customer") or item.get("cliente") or item.get("nome") or "?"

        for bkt, lo, hi, acao, desc in POLITICA:
            if lo <= dias <= hi:
                if BUCKET_FILTER and BUCKET_FILTER != bkt: break
                plano.append({
                    "bucket": bkt, "dias": dias, "acao": acao, "descricao": desc,
                    "invoice_id": invoice_id, "customer_id": customer_id,
                    "nome": nome, "valor": val,
                    "executar": acao is not None,
                })
                break

    total_exec = sum(1 for p in plano if p["executar"])
    total_val = sum(p["valor"] for p in plano if p["executar"])
    total_skip = sum(1 for p in plano if not p["executar"])

    if FORMAT == "json":
        print(json.dumps({"date": today.isoformat(), "dry_run": DRY_RUN,
                          "plano": plano, "total_execucao": total_exec,
                          "total_valor": total_val, "total_skip": total_skip},
                         ensure_ascii=False))
        return

    mode = "DRY-RUN (simulação)" if DRY_RUN else "EXECUÇÃO REAL"
    print(f"💸 Orquestração de Cobrança — {mode} — {today.strftime('%d/%m/%Y')}")
    print(f"   {total_exec} cobranças a executar · {fmt(total_val)} · {total_skip} para análise manual")
    print()

    if DRY_RUN:
        for p in plano:
            marker = "✉" if p["executar"] else "⏸"
            print(f"  {marker} [{p['bucket']:6}] {p['nome'][:30]:<30} {fmt(p['valor']):>12}  → {p['descricao']}")
        print()
        print(f"  ⚠ Este é apenas o plano. Para executar: Marcos precisa de SIM explícito do dono.")
        return

    # Execução real
    results = []
    for p in plano:
        if not p["executar"]:
            results.append({**p, "resultado": "skipped"})
            continue
        r = run_gateway("cobranca", [
            p["acao"],
            "--invoice_id", p["invoice_id"],
            "--channel", "whatsapp",
        ])
        ok = not r.get("error") and r.get("success", False)
        results.append({**p, "resultado": "ok" if ok else "error", "response": r})
        print(f"  {'✅' if ok else '❌'} {p['nome'][:30]:<30} {fmt(p['valor'])} → {'OK' if ok else r.get('error','?')[:40]}")

    ok_count = sum(1 for r in results if r.get("resultado") == "ok")
    print(f"\n  {ok_count}/{total_exec} cobranças enviadas com sucesso.")

if __name__ == "__main__":
    main()
