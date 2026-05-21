#!/usr/bin/env python3
"""
sugerir_categoria.py — Sugere categoria para um supplier baseado no histórico.

Uso:
  python3 sugerir_categoria.py --supplier "Uber"
  python3 sugerir_categoria.py --supplier "Posto BR" --raw_text "abasteci o carro"
  python3 sugerir_categoria.py --format json --supplier "Netflix"

Retorna:
  {"categoria": "Transporte", "confianca": 8, "auto": true}  → usar sem perguntar
  {"categoria": "Streaming", "confianca": 2, "auto": false}  → sugerir como default
  {"categoria": null, "confianca": 0, "auto": false}         → perguntar ao dono
"""
import json
import re
import sys
from pathlib import Path

MEMORY_FILE = Path.home() / ".agente-cfo" / "memory" / "padroes-categorias.json"
MIN_AUTO_CONFIDENCE = 3  # ocorrências mínimas para auto-fill

FORMAT = "text"
SUPPLIER = None
RAW_TEXT = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--supplier" and i + 1 < len(sys.argv): SUPPLIER = sys.argv[i+1]; i += 2
    elif a == "--raw_text" and i + 1 < len(sys.argv): RAW_TEXT = sys.argv[i+1]; i += 2
    else: i += 1

# Keywords pra inferência quando não há histórico
KEYWORD_CATEGORIES = {
    "uber|99|cabify|taxi|lyft": "Transporte",
    "posto|gasolina|combustivel|etanol|combustível": "Combustível",
    "mercado|supermercado|hortifruti|sacolão": "Alimentação",
    "aluguel|condominio|iptu|água|luz|energia|internet|telefone": "Moradia/Infraestrutura",
    "salario|folha|pagamento.*funcionario|rh|recursos humanos": "Folha de Pagamento",
    "netflix|spotify|amazon|disney|streaming": "Assinaturas/Streaming",
    "restaurante|ifood|rappi|deliveroo|lanchonete": "Alimentação Corporativa",
    "google|azure|aws|oracle|microsoft|softwar": "Tecnologia/Software",
    "contador|contabilidade|juridico|advocacia|advogado": "Serviços Profissionais",
    "fgts|inss|das|simples|darf|imposto": "Tributos/Impostos",
}


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def load_patterns() -> dict:
    if MEMORY_FILE.exists():
        try: return json.loads(MEMORY_FILE.read_text())
        except: pass
    return {}


def fuzzy_match(query: str, key: str, threshold: float = 0.7) -> bool:
    """Match simples por substring + proporção de palavras em comum."""
    q = normalize(query)
    k = normalize(key)
    if k in q or q in k:
        return True
    q_words = set(q.split())
    k_words = set(k.split())
    if not q_words or not k_words:
        return False
    common = len(q_words & k_words)
    return common / max(len(q_words), len(k_words)) >= threshold


def infer_from_keywords(text: str) -> str | None:
    t = normalize(text)
    for pattern, category in KEYWORD_CATEGORIES.items():
        if re.search(pattern, t):
            return category
    return None


def main():
    if not SUPPLIER:
        print(json.dumps({"error": "--supplier obrigatório"}) if FORMAT == "json"
              else "Uso: python3 sugerir_categoria.py --supplier X")
        return

    patterns = load_patterns()
    sup_norm = normalize(SUPPLIER)

    # Busca exata ou fuzzy
    cat_data = patterns.get(sup_norm)
    if not cat_data:
        for k, v in patterns.items():
            if fuzzy_match(sup_norm, k):
                cat_data = v
                break

    best_cat = None
    best_count = 0
    if cat_data:
        for cat, meta in cat_data.items():
            c = meta.get("count", 0)
            if c > best_count:
                best_count = c
                best_cat = cat

    # Fallback: inferir por keywords
    if not best_cat:
        combined = f"{SUPPLIER} {RAW_TEXT or ''}"
        best_cat = infer_from_keywords(combined)
        best_count = 1 if best_cat else 0

    auto = best_count >= MIN_AUTO_CONFIDENCE
    result = {
        "supplier": SUPPLIER,
        "categoria": best_cat,
        "confianca": best_count,
        "auto": auto,
    }

    if FORMAT == "json":
        print(json.dumps(result, ensure_ascii=False)); return

    if best_cat:
        flag = "✅ AUTO" if auto else "💡 Sugestão"
        print(f"🧠 {flag}: '{SUPPLIER}' → '{best_cat}' (confiança: {best_count}x)")
    else:
        print(f"🧠 Sem padrão para '{SUPPLIER}' — perguntar ao dono")


if __name__ == "__main__":
    main()
