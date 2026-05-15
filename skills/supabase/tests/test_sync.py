#!/usr/bin/env python3
"""
Smoke test da skill supabase (Sprint 28).
Valida render_mcp_config, mcp_manager (via mocked openclaw), supabase_sync.
Não precisa de credenciais reais nem hit na API.
"""
import json
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
AGENTE_CFO_SCRIPTS = Path(__file__).parent.parent.parent / "agente-cfo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(AGENTE_CFO_SCRIPTS))


# ── 1. Imports ────────────────────────────────────────────────────────────────
def test_imports():
    from render_mcp_config import slugify, project_mcp_name, project_mcp_entry, desired_mcp_map
    import mcp_manager as mm
    import supabase_sync as ss
    print("✓ render_mcp_config, mcp_manager, supabase_sync importados")
    return slugify, project_mcp_name, project_mcp_entry, desired_mcp_map, mm, ss


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


# ── 3. project_mcp_name ───────────────────────────────────────────────────────
def test_mcp_name(project_mcp_name):
    p = {"name": "Minha Empresa", "project_url": "u", "service_role_key": "k", "active": True}
    assert project_mcp_name(p) == "supabase_minha_empresa"
    print("✓ project_mcp_name OK")


# ── 4. project_mcp_entry ──────────────────────────────────────────────────────
def test_mcp_entry(project_mcp_entry):
    p = {"name": "x", "project_url": "https://abc.supabase.co", "service_role_key": "eyJ.test", "active": True}
    entry = project_mcp_entry(p)
    assert entry["command"] == "npx"
    assert "@supabase/mcp-server-supabase@latest" in entry["args"]
    assert "@supabase/mcp-server-supabase@latest" in entry["args"]
    assert entry["env"]["SUPABASE_URL"] == "https://abc.supabase.co"
    assert entry["env"]["SUPABASE_SERVICE_ROLE_KEY"] == "eyJ.test"
    json.dumps(entry)  # serializável
    print("✓ project_mcp_entry OK")


# ── 5. desired_mcp_map filtra inativos ───────────────────────────────────────
def test_desired_map(desired_mcp_map):
    projects = [
        {"name": "Prod", "project_url": "https://p.supabase.co", "service_role_key": "k1", "active": True},
        {"name": "Staging", "project_url": "https://s.supabase.co", "service_role_key": "k2", "active": False},
    ]
    m = desired_mcp_map(projects)
    assert "supabase_prod" in m
    assert "supabase_staging" not in m
    assert len(m) == 1
    print("✓ desired_mcp_map: filtra inativos OK")


# ── 6. mcp_manager: hash estável ──────────────────────────────────────────────
def test_hash_stable(mm):
    h1 = mm.mcp_state_hash("omie", "python3", ["/path/to/mcp.py"], {"K": "v"})
    h2 = mm.mcp_state_hash("omie", "python3", ["/path/to/mcp.py"], {"K": "v"})
    h3 = mm.mcp_state_hash("omie", "python3", ["/path/to/mcp.py"], {"K": "different"})
    assert h1 == h2, "Hash deve ser determinístico"
    assert h1 != h3, "Hash deve mudar se env muda"
    print("✓ mcp_state_hash: estável e sensível a mudanças")


# ── 7. supabase_sync: funções presentes ──────────────────────────────────────
def test_sync_api(ss):
    assert hasattr(ss, "sync")
    assert hasattr(ss, "fetch_projects")
    assert hasattr(ss, "load_env")
    print("✓ supabase_sync: funções principais presentes")


# ── 8. fetch_projects sem env → [] ───────────────────────────────────────────
def test_fetch_no_env(ss):
    for k in ("PANEL_BASE_URL", "PANEL_TOKEN", "HOOKS_TOKEN"):
        os.environ.pop(k, None)
    result = ss.fetch_projects()
    assert result == []
    print("✓ fetch_projects retorna [] sem env vars")


# ── Runner ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Rodando smoke tests do supabase_sync (Sprint 28)...\n")
    slugify, mcp_name, mcp_entry, desired_map, mm, ss = test_imports()
    test_slugify(slugify)
    test_mcp_name(mcp_name)
    test_mcp_entry(mcp_entry)
    test_desired_map(desired_map)
    test_hash_stable(mm)
    test_sync_api(ss)
    test_fetch_no_env(ss)
    print("\n✅ Todos os smoke tests passaram!")
