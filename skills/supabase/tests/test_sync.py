#!/usr/bin/env python3
"""
Smoke test do supabase_sync.py + render_mcp_config.py.
Não precisa de credenciais reais nem hit na API.
"""
import json
import sys
import os
from pathlib import Path

# Adiciona scripts/ ao path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── 1. Import sem erros ───────────────────────────────────────────────────────
def test_imports():
    from render_mcp_config import slugify, render_mcp_entry, render_mcp_block
    print("✓ render_mcp_config importado com sucesso")
    return slugify, render_mcp_entry, render_mcp_block


# ── 2. slugify ────────────────────────────────────────────────────────────────
def test_slugify(slugify):
    cases = [
        ("Minha Empresa", "minha_empresa"),
        ("Projeto #1!", "projeto_1"),
        ("ERP — Produção", "erp_producao"),
        ("  STAGING  ", "staging"),
        ("café", "cafe"),
        ("", "project"),
        ("123", "123"),
        ("a___b___c", "a_b_c"),
    ]
    for input_val, expected in cases:
        result = slugify(input_val)
        assert result == expected, f"slugify({input_val!r}) → {result!r}, esperado {expected!r}"
    print(f"✓ slugify: {len(cases)} casos OK")


# ── 3. render_mcp_entry ───────────────────────────────────────────────────────
def test_render_entry(render_mcp_entry):
    project = {
        "id": "abc",
        "name": "Minha Empresa",
        "project_url": "https://xyzabc.supabase.co",
        "service_role_key": "eyJtest.key",
        "active": True,
    }
    result = render_mcp_entry(project)
    assert isinstance(result, dict), "Deve retornar dict"
    assert "supabase_minha_empresa" in result
    entry = result["supabase_minha_empresa"]
    assert entry["command"] == "npx"
    assert "-y" in entry["args"]
    assert "@supabase/mcp-server-supabase@latest" in entry["args"]
    assert entry["env"]["SUPABASE_URL"] == "https://xyzabc.supabase.co"
    assert entry["env"]["SUPABASE_SERVICE_ROLE_KEY"] == "eyJtest.key"
    # Deve ser JSON-serializável
    json.dumps(result)
    print("✓ render_mcp_entry: estrutura correta, JSON-serializável")


# ── 4. render_mcp_block com ativos e inativos ─────────────────────────────────
def test_render_block(render_mcp_block):
    projects = [
        {
            "id": "1",
            "name": "ERP Produção",
            "project_url": "https://erp.supabase.co",
            "service_role_key": "key1",
            "active": True,
        },
        {
            "id": "2",
            "name": "Staging",
            "project_url": "https://staging.supabase.co",
            "service_role_key": "key2",
            "active": False,  # não deve aparecer
        },
        {
            "id": "3",
            "name": "Analytics",
            "project_url": "https://analytics.supabase.co",
            "service_role_key": "key3",
            "active": True,
        },
    ]
    block = render_mcp_block(projects)
    assert "supabase_erp_producao" in block
    assert "supabase_analytics" in block
    assert "supabase_staging" not in block, "Inativo não deve aparecer"
    assert len(block) == 2
    json.dumps(block)  # JSON-serializável
    print("✓ render_mcp_block: filtra inativos, 2 ativos → 2 entradas")


# ── 5. render_mcp_block vazio não crasha ─────────────────────────────────────
def test_empty_block(render_mcp_block):
    block = render_mcp_block([])
    assert block == {}
    block = render_mcp_block([{"id": "x", "name": "X", "project_url": "u", "service_role_key": "k", "active": False}])
    assert block == {}
    print("✓ render_mcp_block: lista vazia / só inativos → {}")


# ── 6. supabase_sync: import + funções auxiliares ────────────────────────────
def test_sync_import():
    import supabase_sync as ss
    assert hasattr(ss, "sync")
    assert hasattr(ss, "fetch_projects")
    assert hasattr(ss, "read_openclaw_config")
    assert hasattr(ss, "get_current_supabase_entries")
    print("✓ supabase_sync importado, funções presentes")


# ── 7. get_current_supabase_entries filtra corretamente ──────────────────────
def test_filter_entries():
    import supabase_sync as ss
    config = {
        "mcpServers": {
            "supabase_erp": {"command": "npx"},
            "supabase_staging": {"command": "npx"},
            "omie": {"command": "python3"},  # não é supabase
        }
    }
    result = ss.get_current_supabase_entries(config)
    assert "supabase_erp" in result
    assert "supabase_staging" in result
    assert "omie" not in result
    assert len(result) == 2
    print("✓ get_current_supabase_entries: filtra apenas supabase_*")


# ── Runner ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Rodando smoke tests do supabase_sync...\n")
    slugify, render_entry, render_block = test_imports()
    test_slugify(slugify)
    test_render_entry(render_entry)
    test_render_block(render_block)
    test_empty_block(render_block)
    test_sync_import()
    test_filter_entries()
    print("\n✅ Todos os smoke tests passaram!")
