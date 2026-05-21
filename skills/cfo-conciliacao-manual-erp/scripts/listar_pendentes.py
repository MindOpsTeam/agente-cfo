#!/usr/bin/env python3
"""
listar_pendentes.py — Lista lançamentos dashboard_only ainda não migrados para o ERP.

Consulta a edge fn do painel (se disponível) ou lê cfo_write_events via PANEL_TOKEN.
Uso:
  python3 listar_pendentes.py
  python3 listar_pendentes.py --format json
  python3 listar_pendentes.py --limite 50
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ENV_FILE = Path.home() / ".agente-cfo" / ".env"
FORMAT = "text"
LIMITE = 100
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a in ("--format", "--formato") and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--limite" and i + 1 < len(sys.argv):
        LIMITE = int(sys.argv[i + 1]); i += 2
    else:
        i += 1

if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PANEL_BASE_URL = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
PANEL_TOKEN = os.environ.get("PANEL_TOKEN", "")


def fetch_pending() -> list:
    """Busca lançamentos dashboard_only via PANEL_TOKEN (PostgREST/Supabase)."""
    if not PANEL_BASE_URL or not PANEL_TOKEN:
        return []

    # Usa a REST API do Supabase diretamente
    base_url = PANEL_BASE_URL.replace("/functions/v1", "")
    url = (f"{base_url}/rest/v1/cfo_write_events"
           f"?erp=eq.dashboard_only&erp_record_id=is.null"
           f"&status=eq.success&order=created_at.asc&limit={LIMITE}")

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {PANEL_TOKEN}",
                "apikey": PANEL_TOKEN,
                "Content-Type": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return []


def fmt(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "N/D"


def main():
    pending = fetch_pending()

    total_valor = sum(float(x.get("amount") or 0) for x in pending if isinstance(x, dict))

    result = {
        "total_pendentes": len(pending),
        "total_valor": total_valor,
        "itens": [
            {
                "id": str(x.get("id") or ""),
                "action": str(x.get("action") or ""),
                "amount": float(x.get("amount") or 0),
                "supplier": str(x.get("supplier") or ""),
                "due_date": str(x.get("due_date") or ""),
                "category": str(x.get("category") or ""),
                "raw_text": str(x.get("raw_text") or ""),
                "created_at": str(x.get("created_at") or "")[:16],
            }
            for x in pending if isinstance(x, dict)
        ]
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    if not pending:
        if not PANEL_BASE_URL:
            print("⚠️  PANEL_BASE_URL não configurado — leitura de pendentes indisponível.")
        else:
            print("✅ Nenhum lançamento dashboard_only pendente de migração.")
        return

    print(f"📋 Lançamentos pendentes de migração pro ERP ({len(pending)} itens / {fmt(total_valor)})")
    print()
    for x in result["itens"][:10]:
        print(f"  • {x['action']:<20} {fmt(x['amount']):<14} {x['supplier'][:25]:<25} {x['due_date']} [{x['created_at']}]")
    if len(pending) > 10:
        print(f"  ... +{len(pending) - 10} outros")
    print()
    print(f"  Para migrar: 'Marcos, migra os lançamentos pro ERP'")


if __name__ == "__main__":
    main()
