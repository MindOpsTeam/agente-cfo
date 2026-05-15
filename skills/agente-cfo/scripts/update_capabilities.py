#!/usr/bin/env python3
"""
update_capabilities.py — Gera marcos_capabilities.md com as integrações ativas.

Sprint 53 — Auto-gera capabilities de Marcos baseado no estado real da VPS:
  - MCP servers registrados em openclaw.json
  - Skills disponíveis localmente (com mcp_server.py)
  - Status dos canais WhatsApp/Telegram
  - Configuração de automações

Output: skills/agente-cfo/identity/marcos_capabilities.md

Uso:
  python3 update_capabilities.py [--output <path>]
  (ou importa generate_capabilities() de outros scripts)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_DIR      = Path(__file__).parent.parent.parent.parent  # agente-cfo/
SKILLS_DIR    = REPO_DIR / "skills"
OPENCLAW_JSON = Path.home() / ".openclaw" / "openclaw.json"
SECRETS_DIR   = Path.home() / ".openclaw" / "secrets"
OUTPUT_PATH   = REPO_DIR / "skills" / "agente-cfo" / "identity" / "marcos_capabilities.md"

# Tool counts conhecidos por skill (fallback se não conseguir rodar o MCP)
KNOWN_TOOL_COUNTS: dict[str, int] = {
    "omie": 96, "bling": 116, "tiny": 28, "granatum": 39, "vhsys": 54,
    "nibo": 40, "contaazul": 32, "hubspot": 463, "rd-station": 27,
    "piperun": 27, "pipedrive": 144, "kommo": 85, "asaas": 33, "iugu": 33,
    "mercado-livre": 27, "nuvemshop": 35,
}

# Categorias e descrições
SKILL_META: dict[str, dict] = {
    "omie":        {"cat": "ERP",        "desc": "saldo, contas a pagar/receber, pedidos, NF-e, fluxo de caixa"},
    "bling":       {"cat": "ERP",        "desc": "saldo, contas, pedidos, produtos, estoque, NF-e"},
    "tiny":        {"cat": "ERP",        "desc": "pedidos, NF-e, produtos, clientes, estoque"},
    "granatum":    {"cat": "ERP",        "desc": "lançamentos, categorias, saldo, contas a pagar/receber"},
    "vhsys":       {"cat": "ERP",        "desc": "clientes, produtos, pedidos de venda/compra, financeiro"},
    "nibo":        {"cat": "ERP",        "desc": "contas bancárias, contas a pagar/receber, categorias"},
    "contaazul":   {"cat": "ERP",        "desc": "clientes, produtos, pedidos, contas, NF-e"},
    "hubspot":     {"cat": "CRM",        "desc": "deals, contacts, companies, tickets, marketing, properties"},
    "rd-station":  {"cat": "CRM",        "desc": "contatos, leads, oportunidades, funil, automações"},
    "piperun":     {"cat": "CRM",        "desc": "deals, pipeline, atividades, contatos, empresas"},
    "pipedrive":   {"cat": "CRM",        "desc": "deals, leads, persons, organizations, activities"},
    "kommo":       {"cat": "CRM",        "desc": "leads, contacts, companies, tasks, pipelines (amoCRM)"},
    "asaas":       {"cat": "Cobrança",   "desc": "cobranças boleto/PIX/cartão, assinaturas, extrato, clientes"},
    "iugu":        {"cat": "Cobrança",   "desc": "faturas, assinaturas, transferências, extrato, marketplace"},
    "mercado-livre": {"cat": "E-commerce", "desc": "pedidos, publicações, perguntas, envios, devoluções"},
    "nuvemshop":   {"cat": "E-commerce", "desc": "produtos, variantes, pedidos, cupons, clientes, webhooks"},
}


# ── Estado do sistema ─────────────────────────────────────────────────────────

def read_openclaw_json() -> dict:
    if OPENCLAW_JSON.exists():
        try:
            return json.loads(OPENCLAW_JSON.read_text())
        except Exception:
            pass
    return {}


def get_active_mcp_servers() -> dict:
    """Retorna MCP servers registrados em openclaw.json."""
    data = read_openclaw_json()
    return data.get("mcp", {}).get("servers", {})


def get_skills_with_secrets() -> list[str]:
    """Skills que têm arquivo .env em secrets/ (credenciais materializadas)."""
    if not SECRETS_DIR.exists():
        return []
    return [
        f.stem for f in SECRETS_DIR.glob("*.env")
        if f.stem not in ("wacli", "stages")
    ]


def get_skills_with_mcp() -> list[str]:
    """Skills que têm mcp_server.py."""
    return [
        s.name for s in SKILLS_DIR.iterdir()
        if (s / "mcp_server.py").exists()
        and s.name not in ("agente-cfo",)
    ]


def get_whatsapp_status() -> str:
    """Status do canal WhatsApp via openclaw channels status."""
    try:
        result = subprocess.run(
            ["openclaw", "channels", "status"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if "whatsapp" in line.lower():
                # Extrai status resumido
                if "linked" in line.lower() and "connected" not in line.lower():
                    return "pareado (conectando)"
                if "linked" in line.lower() and "error" in line.lower():
                    return "pareado mas com erro de sessão"
                if "linked" in line.lower():
                    return "ativo"
                if "configured" in line.lower():
                    return "configurado (não pareado)"
                return line.strip()[:80]
        return "não configurado"
    except Exception:
        return "desconhecido"


def get_telegram_status() -> str:
    """Verifica status do Telegram via systemd + log."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "cfo-telegram-sync"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip() == "active":
            return "ativo (daemon rodando)"
        return "parado"
    except FileNotFoundError:
        # macOS — verifica processo
        return "ativo" if _proc_running("telegram_sync") else "não iniciado"
    except Exception:
        return "desconhecido"


def _proc_running(name: str) -> bool:
    try:
        result = subprocess.run(["pgrep", "-f", name], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


def get_active_automations_count() -> int:
    """Conta automações ativas no arquivo de state (se existir)."""
    state_file = Path.home() / ".agente-cfo" / "state" / "automation_engine.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text())
            return len(data.get("active_automations", []))
        except Exception:
            pass
    return 0


# ── Geração do markdown ───────────────────────────────────────────────────────

def generate_capabilities(output_path: Optional[Path] = None) -> str:
    """
    Gera markdown de capabilities atualizado e salva no output_path.
    Retorna o conteúdo gerado.
    """
    if output_path is None:
        output_path = OUTPUT_PATH

    now_iso = datetime.now(timezone.utc).isoformat()
    now_br = datetime.now().strftime("%d/%m/%Y %H:%M")

    mcp_servers = get_active_mcp_servers()
    skills_with_secrets = get_skills_with_secrets()
    skills_with_mcp = get_skills_with_mcp()
    wa_status = get_whatsapp_status()
    tg_status = get_telegram_status()

    # Skills ativas = tem MCP server registrado E .env materializado
    active_skills: list[dict] = []
    for skill in sorted(skills_with_mcp):
        has_mcp_registered = skill in mcp_servers
        has_secret = skill in skills_with_secrets
        meta = SKILL_META.get(skill, {"cat": "Outro", "desc": "—"})
        tool_count = KNOWN_TOOL_COUNTS.get(skill, 0)
        active_skills.append({
            "name": skill,
            "cat": meta["cat"],
            "desc": meta["desc"],
            "tools": tool_count,
            "mcp_registered": has_mcp_registered,
            "has_secret": has_secret,
            "is_active": has_mcp_registered and has_secret,
        })

    # Supabase projects (MCP servers com prefixo supabase_)
    supabase_mcps = {k: v for k, v in mcp_servers.items() if k.startswith("supabase_")}

    # Agrupa por categoria
    by_cat: dict[str, list] = {}
    for s in active_skills:
        by_cat.setdefault(s["cat"], []).append(s)

    # Contagem de ativos
    total_active = sum(1 for s in active_skills if s["is_active"])
    total_available = len(active_skills)

    lines = [
        f"# Capabilities Atuais de Marcos",
        f"",
        f"> Gerado automaticamente em {now_br} — não editar manualmente.",
        f"> Fonte: openclaw.json + ~/.openclaw/secrets/",
        f"",
        f"---",
        f"",
        f"## Resumo",
        f"",
        f"- **{total_active} integrações ativas** (MCP registrado + credencial materializada)",
        f"- **{total_available} integrações disponíveis** (com mcp_server.py local)",
        f"- **{len(supabase_mcps)} banco(s) Supabase** conectados",
        f"- **WhatsApp**: {wa_status}",
        f"- **Telegram**: {tg_status}",
        f"",
        f"---",
        f"",
    ]

    # Seção de integrações ativas
    if any(s["is_active"] for s in active_skills) or supabase_mcps:
        lines.append("## Integrações ativas agora")
        lines.append("")
        lines.append("Posso usar essas ferramentas neste momento:")
        lines.append("")

        for cat, skills in sorted(by_cat.items()):
            active_in_cat = [s for s in skills if s["is_active"]]
            if not active_in_cat:
                continue
            lines.append(f"### {cat}")
            lines.append("")
            for s in active_in_cat:
                lines.append(f"- **{s['name']}** ({s['tools']} tools): {s['desc']}")
            lines.append("")

        if supabase_mcps:
            lines.append("### Database (Supabase)")
            lines.append("")
            for name, entry in supabase_mcps.items():
                slug = name.replace("supabase_", "")
                url = entry.get("env", {}).get("SUPABASE_URL", "")
                # Extrai project ref da URL
                project_ref = url.split("//")[-1].split(".")[0] if url else slug
                lines.append(f"- **{name}**: banco PostgreSQL `{project_ref}` — execute SQL, list tables, describe")
            lines.append("")
    else:
        lines.extend([
            "## Integrações ativas agora",
            "",
            "⚠️ Nenhuma integração ativa no momento.",
            "",
            "Para ativar: painel → Configurações → Integrações → adiciona credencial.",
            "",
        ])

    # Seção de skills disponíveis (aguardando credencial)
    waiting = [s for s in active_skills if not s["is_active"]]
    if waiting:
        lines.append("## Skills disponíveis (aguardando credencial)")
        lines.append("")
        lines.append("Tenho suporte a estas integrações — falta credencial do dono:")
        lines.append("")
        for cat, skills in sorted(by_cat.items()):
            waiting_in_cat = [s for s in skills if not s["is_active"]]
            if not waiting_in_cat:
                continue
            names = ", ".join(s["name"] for s in waiting_in_cat)
            lines.append(f"- **{cat}**: {names}")
        lines.append("")
        lines.append("Para ativar qualquer uma: painel → Configurações → Integrações")
        lines.append("")

    # Roteamento padrão
    lines.extend([
        "---",
        "",
        "## Roteamento padrão",
        "",
    ])

    # ERP ativo
    erp_active = [s["name"] for s in active_skills if s["cat"] == "ERP" and s["is_active"]]
    crm_active = [s["name"] for s in active_skills if s["cat"] == "CRM" and s["is_active"]]
    cobranca_active = [s["name"] for s in active_skills if s["cat"] == "Cobrança" and s["is_active"]]
    ecommerce_active = [s["name"] for s in active_skills if s["cat"] == "E-commerce" and s["is_active"]]

    def _route(label: str, active: list[str], none_msg: str) -> str:
        if active:
            return f"**{label}**: usa **{', '.join(active)}** → {SKILL_META.get(active[0], {}).get('desc', '')}"
        return f"**{label}**: {none_msg}"

    lines.append(_route("Saldo/caixa/contas", erp_active, "⚠️ sem ERP ativo — configure em /integrations"))
    lines.append(_route("Deals/pipeline CRM", crm_active, "⚠️ sem CRM ativo — configure em /integrations"))
    lines.append(_route("Cobranças/inadimplência", cobranca_active, "⚠️ sem cobrança ativa — configure Asaas ou Iugu"))
    lines.append(_route("Pedidos/estoque", ecommerce_active, "sem e-commerce ativo (opcional)"))
    if supabase_mcps:
        lines.append(f"**Dados do banco Supabase**: usa {list(supabase_mcps.keys())[0]} (e outros {len(supabase_mcps)-1} se houver)")
    else:
        lines.append("**Dados do banco Supabase**: nenhum projeto conectado ainda")
    lines.append("**Automações/alertas**: usa automation-engine + alerts-checker (sempre disponíveis)")
    lines.append("")
    lines.append(f"*Última atualização: {now_br}*")

    content = "\n".join(lines)

    # Salva
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)

    return content


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gera marcos_capabilities.md")
    parser.add_argument("--output", help="Caminho de saída (default: identity/marcos_capabilities.md)")
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else None
    content = generate_capabilities(out_path)
    print(content)
    effective_path = out_path or OUTPUT_PATH
    print(f"\n✓ Salvo em: {effective_path}", file=sys.stderr)
