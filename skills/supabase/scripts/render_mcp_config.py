#!/usr/bin/env python3
"""
render_mcp_config.py — Helpers de MCP para projetos Supabase.

Sprint 28 fix: usa mcp.servers.<name> via `openclaw config set` (NÃO mcpServers top-level).

Exporta:
  slugify(text)              → slug válido pra nome do server
  project_mcp_name(project)  → "supabase_<slug>"
  project_mcp_entry(project) → { "command": "npx", "args": [...], "env": {...} }
"""
import re
import unicodedata


def slugify(text: str) -> str:
    """unicode-safe → snake_case ASCII."""
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    s = ascii_str.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    s = re.sub(r"_+", "_", s)
    return s or "project"


def project_mcp_name(project: dict) -> str:
    return f"supabase_{slugify(project['name'])}"


def project_mcp_entry(project: dict) -> dict:
    """Retorna o objeto de entrada MCP (sem a key name)."""
    return {
        "command": "npx",
        "args": ["-y", "@supabase/mcp-server-supabase@latest"],
        "env": {
            "SUPABASE_URL": project["project_url"],
            "SUPABASE_SERVICE_ROLE_KEY": project["service_role_key"],
        },
    }


def desired_mcp_map(projects: list) -> dict:
    """
    Retorna { mcp_name: entry } apenas para projetos active=True.
    """
    result = {}
    for p in projects:
        if not p.get("active", True):
            continue
        name = project_mcp_name(p)
        result[name] = project_mcp_entry(p)
    return result
