#!/usr/bin/env python3
"""
importar_extrato.py — Importa extrato bancário em formato OFX ou CSV.

PLACEHOLDER — processa arquivo local e converte para formato interno.

Uso:
  python3 importar_extrato.py --formato ofx --arquivo /tmp/extrato.ofx
  python3 importar_extrato.py --formato csv --arquivo /tmp/extrato.csv
  python3 importar_extrato.py --format json --arquivo /tmp/extrato.ofx
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

FORMAT = "text"
FILE = None
FORMATO = "ofx"
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a in ("--format", "--formato") and i + 1 < len(sys.argv):
        FORMAT = sys.argv[i + 1]; i += 2
    elif a == "--formato" and i + 1 < len(sys.argv):
        FORMATO = sys.argv[i + 1]; i += 2
    elif a == "--arquivo" and i + 1 < len(sys.argv):
        FILE = sys.argv[i + 1]; i += 2
    else:
        i += 1

EXTRATO_FILE = Path.home() / ".agente-cfo" / "extrato-temp.json"


def parse_ofx(content: str) -> list:
    """Parser OFX mínimo para transações STMTTRN."""
    transactions = []
    blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", content, re.DOTALL | re.IGNORECASE)
    for block in blocks:
        def get(tag: str) -> str:
            m = re.search(rf"<{tag}>\s*([^\n<]+)", block, re.IGNORECASE)
            return m.group(1).strip() if m else ""
        ttype = get("TRNTYPE")
        dtposted = get("DTPOSTED")[:8] if get("DTPOSTED") else ""
        try:
            dt = datetime.strptime(dtposted, "%Y%m%d").date().isoformat()
        except Exception:
            dt = dtposted
        amount = float(get("TRNAMT").replace(",", ".") or 0)
        memo = get("MEMO") or get("NAME") or ""
        transactions.append({
            "tipo": ttype,
            "data": dt,
            "valor": amount,
            "descricao": memo,
        })
    return transactions


def parse_csv(content: str) -> list:
    """Parser CSV simples: data,descricao,valor (sem header, vírgula decimal)."""
    transactions = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(";") if ";" in line else line.split(",")
        if len(parts) < 3:
            continue
        try:
            dt = parts[0].strip()
            desc = parts[1].strip()
            val = float(parts[2].strip().replace(",", ".").replace("R$", "").strip())
            transactions.append({"tipo": "CRÉDITO" if val > 0 else "DÉBITO",
                                  "data": dt, "valor": val, "descricao": desc})
        except Exception:
            continue
    return transactions


def main():
    if FILE is None:
        print(json.dumps({"error": "Informe --arquivo <caminho>"}) if FORMAT == "json"
              else "⚠️ PLACEHOLDER ativo. Informe --arquivo <caminho_extrato.ofx|.csv>")
        return

    path = Path(FILE)
    if not path.exists():
        print(json.dumps({"error": f"Arquivo não encontrado: {FILE}"}) if FORMAT == "json"
              else f"❌ Arquivo não encontrado: {FILE}")
        return

    content = path.read_text(errors="replace")
    if FORMATO == "ofx" or path.suffix.lower() in (".ofx", ".qfx"):
        transactions = parse_ofx(content)
    else:
        transactions = parse_csv(content)

    # Salva em extrato temporário para cruzar.py usar
    EXTRATO_FILE.parent.mkdir(parents=True, exist_ok=True)
    EXTRATO_FILE.write_text(json.dumps(transactions, indent=2, ensure_ascii=False))

    result = {"arquivo": str(FILE), "formato": FORMATO,
              "transacoes": len(transactions),
              "creditos": sum(1 for t in transactions if t.get("valor", 0) > 0),
              "debitos": sum(1 for t in transactions if t.get("valor", 0) < 0),
              "salvo_em": str(EXTRATO_FILE)}

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    print(f"🏦 Extrato importado: {len(transactions)} transações")
    print(f"  Créditos: {result['creditos']} | Débitos: {result['debitos']}")
    print(f"  Salvo em: {EXTRATO_FILE}")
    print(f"  Próximo: python3 cruzar.py --periodo 30")


if __name__ == "__main__":
    main()
