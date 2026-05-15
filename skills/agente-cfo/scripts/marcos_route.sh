#!/usr/bin/env bash
# marcos_route.sh — Roteamento rápido de perguntas para skills (sem LLM, <100ms).
#
# Dado um texto de pergunta (stdin ou argumento), retorna JSON com:
#   category         : financeiro|vendas|cobrança|ecommerce|database|automação|admin|geral
#   recommended_skill: nome da skill ativa recomendada (ou null)
#   reason           : por que essa skill (ou por que null)
#   fallback         : o que fazer se não tem skill (avisar|perguntar_qual|usar_memoria)
#   tools_hint       : lista de tools sugeridas pra começar
#
# Uso:
#   echo "qual o saldo?" | bash marcos_route.sh
#   bash marcos_route.sh "lista os deals do HubSpot"
#
# Não usa LLM — puro regex/heuristics sobre palavras-chave.

set -euo pipefail

# Lê input
if [[ $# -ge 1 ]]; then
    QUERY="$1"
else
    QUERY="$(cat)"
fi

QUERY_LOWER=$(echo "$QUERY" | tr '[:upper:]' '[:lower:]' | \
    sed 's/ã/a/g; s/á/a/g; s/à/a/g; s/â/a/g; s/ä/a/g;
         s/é/e/g; s/ê/e/g; s/è/e/g;
         s/í/i/g; s/ï/i/g;
         s/ó/o/g; s/ô/o/g; s/õ/o/g;
         s/ú/u/g; s/ü/u/g;
         s/ç/c/g')

python3 - "$QUERY_LOWER" << 'PYEOF'
import sys, json, re
from pathlib import Path

query = sys.argv[1]

# ── Lê skills com credencial materializada ─────────────────────────────────
secrets_dir = Path.home() / ".openclaw" / "secrets"
active_skills = set()
if secrets_dir.exists():
    active_skills = {f.stem for f in secrets_dir.glob("*.env")
                     if f.stem not in ("wacli",)}

# ── Lê MCP servers do openclaw.json ────────────────────────────────────────
openclaw_json = Path.home() / ".openclaw" / "openclaw.json"
mcp_servers = set()
supabase_mcps = {}
if openclaw_json.exists():
    try:
        data = json.loads(openclaw_json.read_text())
        servers = data.get("mcp", {}).get("servers", {})
        mcp_servers = set(servers.keys())
        supabase_mcps = {k: v for k, v in servers.items() if k.startswith("supabase_")}
    except Exception:
        pass

# Skills ativas (têm MCP OU secret)
def is_active(skill: str) -> bool:
    return skill in active_skills or skill in mcp_servers

# ── Tabela de roteamento ────────────────────────────────────────────────────
ROUTES = {
    "financeiro": {
        "keywords": [
            "saldo", "caixa", "contas a pagar", "contas a receber", "fluxo de caixa",
            "dre", "extrato", "transferencia", "faturamento", "receita", "despesa",
            "projecao financeira", "nf-e", "nota fiscal", "provisao", "inadimplencia",
            "pagar", "receber", "financeiro", "balancete", "patrimonio", "ativo", "passivo",
            "fluxo", "capital de giro", "devedores", "credores"
        ],
        "skills": ["omie", "bling", "tiny", "granatum", "vhsys", "nibo", "contaazul"],
        "label": "ERP financeiro",
    },
    "vendas": {
        "keywords": [
            "deal", "oportunidade", "pipeline", "funil", "lead", "contato", "prospect",
            "cliente", "negociacao", "proposta", "ganho", "perdido", "atividade", "crm",
            "follow-up", "empresa", "vendas", "comercial", "venda", "conversao", "ticket",
            "forecast", "previsao de vendas", "metas", "quota"
        ],
        "skills": ["hubspot", "rd-station", "piperun", "pipedrive", "kommo"],
        "label": "CRM",
    },
    "cobranca": {
        "keywords": [
            "boleto", "pix", "cobranca", "inadimplente", "vencido", "fatura", "assinatura",
            "link de pagamento", "pagamento", "cobrar", "inadimplencia", "clientes em atraso",
            "cobrar cliente", "cobrancas", "recebimento", "liquidacao", "baixa manual"
        ],
        "skills": ["asaas", "iugu"],
        "label": "Cobrança",
    },
    "ecommerce": {
        "keywords": [
            "pedido", "venda online", "e-commerce", "estoque", "produto", "marketplace",
            "envio", "entrega", "devolucao", "loja virtual", "mercado livre", "nuvemshop",
            "loja", "item", "sku", "variante", "categoria", "preco", "cupon"
        ],
        "skills": ["mercado-livre", "nuvemshop"],
        "label": "E-commerce",
    },
    "database": {
        "keywords": [
            "sql", "supabase", "banco de dados", "tabela", "query", "consultar banco",
            "dados raw", "banco", "database", "postgre", "select", "dados do sistema"
        ],
        "skills": list(supabase_mcps.keys()),
        "label": "Database Supabase",
    },
    "automacao": {
        "keywords": [
            "automatizar", "automacao", "cron", "agendar", "todo dia", "toda semana",
            "regra automatica", "se x entao y", "alerta automatico", "criar alerta",
            "configurar alerta", "relatorio periodico", "lembrete automatico"
        ],
        "skills": [],  # não precisa de skill externa
        "label": "Automação",
    },
    "admin": {
        "keywords": [
            "reiniciar", "restart", "logs", "daemon", "servico", "status do sistema",
            "openclaw", "gateway", "backup", "update", "atualizar", "memoria do marcos",
            "configuracao", "plugin", "mcp"
        ],
        "skills": [],  # admin_action.sh
        "label": "Admin",
    },
}

# ── Matching por palavras-chave ─────────────────────────────────────────────
scores = {}
for cat, info in ROUTES.items():
    score = 0
    for kw in info["keywords"]:
        if kw in query:
            score += len(kw.split())  # pontuação proporcional ao tamanho do keyword
    if score > 0:
        scores[cat] = score

if not scores:
    # Fallback: categoria geral
    result = {
        "category": "geral",
        "recommended_skill": None,
        "reason": "Pergunta não se encaixa em categoria específica",
        "fallback": "usar_llm_direto",
        "tools_hint": [],
        "active_skills": sorted(list(active_skills)),
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)

# Categoria com maior score
best_cat = max(scores, key=lambda c: scores[c])
cat_info = ROUTES[best_cat]

# Encontra skill recomendada
recommended = None
reason = ""
tools_hint = []
fallback = "avisar_dono"

if best_cat == "automacao":
    recommended = None
    reason = "Automações via automation-engine (sempre disponível)"
    tools_hint = ["bash admin_action.sh '...'"]
    fallback = "criar_automacao"

elif best_cat == "admin":
    recommended = None
    reason = "Ação administrativa via admin_action.sh"
    tools_hint = ["bash marco_route.sh pra confirmar", "admin_action.sh"]
    fallback = "usar_admin_action"

elif best_cat == "database":
    if supabase_mcps:
        recommended = list(supabase_mcps.keys())[0]
        reason = f"Projeto Supabase ativo: {recommended}"
        slug = recommended.replace("supabase_", "")
        tools_hint = [f"{recommended}_list_tables", f"{recommended}_execute_sql"]
        fallback = "usar_supabase"
    else:
        recommended = None
        reason = "Nenhum projeto Supabase conectado"
        fallback = "avisar_dono"
else:
    # Skills externas — verifica qual está ativa
    active_in_cat = [s for s in cat_info["skills"] if is_active(s)]
    if active_in_cat:
        recommended = active_in_cat[0]
        reason = f"{cat_info['label']} ativo: {recommended}"
        # Gera tools_hint baseado na categoria
        tool_prefix = recommended.replace("-", "_")
        hint_map = {
            "financeiro": ["_saldo", "_contas_pagar_listar", "_contas_receber_listar"],
            "vendas":     ["_deals_list", "_contacts_list"],
            "cobranca":   ["_charges_list", "_customers_list"],
            "ecommerce":  ["_orders_list", "_products_list"],
        }
        suffixes = hint_map.get(best_cat, ["_list"])
        tools_hint = [f"{tool_prefix}{s}" for s in suffixes[:2]]
        fallback = "usar_skill"
    else:
        recommended = None
        all_skills = cat_info["skills"]
        reason = f"Nenhum {cat_info['label']} conectado ({', '.join(all_skills[:3]) if all_skills else 'nenhum disponível'})"
        fallback = "avisar_dono"

result = {
    "category": best_cat,
    "recommended_skill": recommended,
    "reason": reason,
    "fallback": fallback,
    "tools_hint": tools_hint,
    "confidence": round(scores[best_cat] / max(scores.values()), 2),
    "active_skills": sorted([s for s in cat_info["skills"] if is_active(s)]) if cat_info["skills"] else [],
}
print(json.dumps(result, ensure_ascii=False))
PYEOF
