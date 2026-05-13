#!/usr/bin/env python3
"""
render_mcp_config.py — Gera bloco mcpServers para projetos Supabase.

Utilitário importado pelo supabase_sync.py.
Também pode ser invocado standalone para inspeção:
    python3 render_mcp_config.py
"""
import json
import re
import unicodedata


def slugify(text: str) -> str:
    """
    Converte nome de projeto em slug válido para chave JSON.
    Ex: "Meu Projeto #1!" → "meu_projeto_1"
    """
    # Normaliza unicode (remove acentos)
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    # Lowercase
    s = ascii_str.lower()
    # Substitui não-alfanuméricos por underscore
    s = re.sub(r"[^a-z0-9]+", "_", s)
    # Remove underscores nas bordas
    s = s.strip("_")
    # Colapsa underscores múltiplos
    s = re.sub(r"_+", "_", s)
    return s or "project"


def render_mcp_entry(project: dict) -> dict:
    """
    Gera uma entrada mcpServers para um projeto Supabase.

    project: { "id", "name", "project_url", "service_role_key", "active" }
    Returns: { "supabase_<slug>": { "command": "npx", "args": [...], "env": {...} } }
    """
    slug = slugify(project["name"])
    key = f"supabase_{slug}"
    entry = {
        "command": "npx",
        "args": ["-y", "@supabase/mcp-server-supabase@latest"],
        "env": {
            "SUPABASE_URL": project["project_url"],
            "SUPABASE_SERVICE_ROLE_KEY": project["service_role_key"],
        },
    }
    return {key: entry}


def render_mcp_block(projects: list[dict]) -> dict:
    """
    Gera o bloco completo { supabase_slug: entry, ... } para todos os projetos ativos.
    projects: lista de dicts com project_url, service_role_key, name, active.
    Filtra apenas active=True.
    """
    result: dict = {}
    for project in projects:
        if not project.get("active", True):
            continue
        entry = render_mcp_entry(project)
        result.update(entry)
    return result


if __name__ == "__main__":
    # Exemplo de saída
    sample = [
        {
            "id": "abc-123",
            "name": "Minha Empresa ERP",
            "project_url": "https://xyzabc.supabase.co",
            "service_role_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.example",
            "active": True,
        },
        {
            "id": "def-456",
            "name": "Staging",
            "project_url": "https://stagingxyz.supabase.co",
            "service_role_key": "eyJstaging.example",
            "active": False,  # não deve aparecer
        },
    ]
    block = render_mcp_block(sample)
    print(json.dumps(block, indent=2, ensure_ascii=False))
