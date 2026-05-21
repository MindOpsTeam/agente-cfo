#!/usr/bin/env python3
"""
proximos_eventos.py — Calendário acionável: fiscal + cobrança + pagamentos + relatórios.

Uso:
  python3 proximos_eventos.py --dias 30
  python3 proximos_eventos.py --dias 7 --tipos fiscal,pagamento
  python3 proximos_eventos.py --format json --dias 14
"""
import json
import subprocess
import sys
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
TRIB_DIR = Path(__file__).parent.parent.parent / "cfo-tributacao-br" / "scripts"

FORMAT = "text"
DIAS = 30
TIPOS = ["fiscal", "cobranca", "pagamento", "relatorio"]
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--dias" and i + 1 < len(sys.argv): DIAS = int(sys.argv[i + 1]); i += 2
    elif a == "--tipos" and i + 1 < len(sys.argv):
        raw = sys.argv[i + 1]
        TIPOS = ["fiscal","cobranca","pagamento","relatorio"] if raw == "all" else raw.split(",")
        i += 2
    else: i += 1


def run_erp(cmd: list) -> dict:
    s = SCRIPTS_DIR / "erp_gateway.py"
    if not s.exists(): return {}
    r = subprocess.run(["python3", str(s)] + cmd, capture_output=True, text=True,
                       timeout=30, cwd=str(SCRIPTS_DIR))
    try: return json.loads(r.stdout) if r.stdout.strip() else {}
    except: return {}


def get_fiscal_events(today: date, end: date) -> list:
    """Chama calendario_fiscal.py e retorna lista de obrigações."""
    trib_script = TRIB_DIR / "calendario_fiscal.py"
    if not trib_script.exists(): return []
    r = subprocess.run(
        ["python3", str(trib_script), "--dias", str(DIAS), "--format", "json"],
        capture_output=True, text=True, timeout=15,
    )
    try:
        d = json.loads(r.stdout) if r.stdout.strip() else {}
        return [
            {"data": o["vencimento"], "tipo": "fiscal", "titulo": o["obrigacao"],
             "acao": f"Recolher/pagar: {o['obrigacao']}", "urgencia": "alta" if
             (date.fromisoformat(o["vencimento"]) - today).days <= 7 else "normal"}
            for o in d.get("obrigacoes", []) if o.get("vencimento")
        ]
    except: return []


def get_receivables_events(today: date, end: date) -> list:
    """Recebíveis a vencer: ação = cobrar D-3."""
    r = run_erp(["list_receivables", "--from", today.isoformat(), "--to", end.isoformat(), "--limit", "100"])
    items = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(items, list): return []
    events = []
    for item in items:
        due = str(item.get("due_date") or item.get("date") or "")[:10]
        if not due: continue
        val = float(item.get("amount_brl") or item.get("amount") or item.get("valor") or 0)
        cliente = str(item.get("customer") or item.get("nome") or "Cliente")[:25]
        due_d = date.fromisoformat(due)
        remind = (due_d - timedelta(days=3)).isoformat()  # ação D-3
        events.append({
            "data": remind, "tipo": "cobranca", "titulo": f"Lembrete: {cliente} vence em {due}",
            "acao": f"Verificar se {cliente} vai pagar (R$ {val:,.0f})", "urgencia": "normal",
            "valor": val,
        })
    return events


def get_payables_events(today: date, end: date) -> list:
    r = run_erp(["list_payables", "--from", today.isoformat(), "--to", end.isoformat(), "--limit", "100"])
    items = r.get("records") or r.get("items") or r.get("data") or []
    if not isinstance(items, list): return []
    events = []
    for item in items:
        due = str(item.get("due_date") or item.get("date") or "")[:10]
        if not due: continue
        val = float(item.get("amount_brl") or item.get("amount") or item.get("valor") or 0)
        forn = str(item.get("supplier") or item.get("fornecedor") or "Fornecedor")[:25]
        due_d = date.fromisoformat(due)
        urgencia = "alta" if (due_d - today).days <= 3 else "normal"
        events.append({
            "data": due, "tipo": "pagamento", "titulo": f"Pagar: {forn}",
            "acao": f"Verificar caixa e pagar {forn} (R$ {val:,.0f})", "urgencia": urgencia,
            "valor": val,
        })
    return events


def get_relatorio_events(today: date, end: date) -> list:
    events = []
    # Semanal: proxima sexta
    days_until_fri = (4 - today.weekday()) % 7 or 7
    next_fri = today + timedelta(days=days_until_fri)
    if today <= next_fri <= end:
        events.append({"data": next_fri.isoformat(), "tipo": "relatorio",
                       "titulo": "Relatório semanal CFO", "acao": "bash relatorio_semanal.sh", "urgencia": "normal"})
    # Mensal: dia 1 do próximo mês
    m = today.month + 1; y = today.year
    if m > 12: m = 1; y += 1
    dia1 = date(y, m, 1)
    if today <= dia1 <= end:
        events.append({"data": dia1.isoformat(), "tipo": "relatorio",
                       "titulo": "Relatório mensal CFO", "acao": "bash relatorio_mensal.sh", "urgencia": "normal"})
    return events


def fmt(v): return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")


def main():
    today = date.today()
    end = today + timedelta(days=DIAS)
    all_events = []

    if "fiscal" in TIPOS: all_events += get_fiscal_events(today, end)
    if "cobranca" in TIPOS: all_events += get_receivables_events(today, end)
    if "pagamento" in TIPOS: all_events += get_payables_events(today, end)
    if "relatorio" in TIPOS: all_events += get_relatorio_events(today, end)

    # Filtra e ordena
    all_events = [e for e in all_events if today.isoformat() <= e.get("data", "9999") <= end.isoformat()]
    all_events.sort(key=lambda e: e.get("data", ""))

    result = {"periodo_dias": DIAS, "hoje": today.isoformat(), "ate": end.isoformat(),
              "total": len(all_events), "eventos": all_events}

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"📅 Calendário de Ações — próximos {DIAS} dias ({today.strftime('%d/%m')} → {end.strftime('%d/%m')})")
    if not all_events:
        print("  ✅ Nenhum evento relevante no período."); return
    print()
    current_week = None
    for e in all_events:
        d = date.fromisoformat(e["data"])
        week = d.isocalendar()[1]
        if week != current_week:
            print(f"  Semana {week} ({d.strftime('%d/%m')}):")
            current_week = week
        urgency = "🔴 " if e.get("urgencia") == "alta" else ""
        tipo_emoji = {"fiscal": "🧾", "cobranca": "💰", "pagamento": "💸", "relatorio": "📑"}.get(e["tipo"], "📌")
        print(f"    {urgency}{tipo_emoji} {d.strftime('%d/%m')} — {e['titulo']}")
        print(f"         ▶ {e['acao']}")


if __name__ == "__main__":
    main()
