#!/usr/bin/env python3
"""
marcos_context.py — Gera o system prompt completo de Marcos.

Sprint 53 — Persona + Capabilities centralizadas.

Concatena:
  1. identity/identity.md      (backstory)
  2. identity/soul.md          (tom e voz)
  3. identity/marcos_persona.md (persona canônica + guardrails)
  4. identity/marcos_capabilities.md (auto-gerado, atualizado sob demanda)
  5. Memórias relevantes de ~/.openclaw/workspace/memory/ (top 3 recentes)
  6. Contexto de runtime: data/hora BR, canal de origem, usuário

Uso:
  python3 marcos_context.py [--channel <canal>] [--user <nome>] [--json]
  (ou importa get_system_prompt() de outros scripts)

Retorna JSON: { system_prompt, hash, generated_at, capabilities_hash }
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

IDENTITY_DIR = Path(__file__).parent.parent / "identity"
WORKSPACE    = Path.home() / ".openclaw" / "workspace"
MEM_DIR      = WORKSPACE / "memory"
CACHE_FILE   = Path("/tmp/cfo-marcos-context-cache.json")
CACHE_TTL_S  = 300  # 5 minutos


def _read_file(path: Path, fallback: str = "") -> str:
    """Lê arquivo de forma segura, retorna fallback se não existir."""
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return fallback


def _get_recent_memories(n: int = 3) -> str:
    """Lê os N diários de memória mais recentes."""
    if not MEM_DIR.exists():
        return ""
    diaries = sorted(MEM_DIR.glob("*.md"), reverse=True)[:n]
    if not diaries:
        return ""
    parts = []
    for d in diaries:
        content = _read_file(d)
        if content:
            date = d.stem  # ex: "2026-05-15"
            parts.append(f"### Memória — {date}\n{content[:800]}")
    return "\n\n".join(parts) if parts else ""


def _get_capabilities(regenerate: bool = False) -> str:
    """Retorna capabilities markdown, regenerando se necessário."""
    capabilities_path = IDENTITY_DIR / "marcos_capabilities.md"

    # Regenera se forçado ou arquivo não existe ou antigo (>1h)
    should_regen = regenerate
    if not capabilities_path.exists():
        should_regen = True
    elif (datetime.now().timestamp() - capabilities_path.stat().st_mtime) > 3600:
        should_regen = True

    if should_regen:
        try:
            update_script = Path(__file__).parent / "update_capabilities.py"
            if update_script.exists():
                import subprocess
                subprocess.run(
                    [sys.executable, str(update_script)],
                    capture_output=True, timeout=30,
                )
        except Exception:
            pass

    return _read_file(capabilities_path, "*(capabilities não disponíveis — execute update_capabilities.py)*")


def get_system_prompt(
    channel: str = "panel",
    user: str = "",
    regenerate_capabilities: bool = False,
) -> dict:
    """
    Monta o system prompt completo de Marcos.

    Args:
        channel: "panel" | "whatsapp:instance" | "telegram:bot"
        user:    nome do usuário (opcional)
        regenerate_capabilities: força regeneração do capabilities.md

    Returns:
        { system_prompt, hash, generated_at, capabilities_hash }
    """
    # Verifica cache
    if CACHE_FILE.exists() and not regenerate_capabilities:
        try:
            cached = json.loads(CACHE_FILE.read_text())
            age = datetime.now().timestamp() - cached.get("_cached_at", 0)
            if age < CACHE_TTL_S and cached.get("channel") == channel:
                return {k: v for k, v in cached.items() if not k.startswith("_")}
        except Exception:
            pass

    # Determina formato de resposta pelo canal
    channel_type = channel.split(":")[0] if ":" in channel else channel
    format_note = {
        "panel":     "Você está respondendo no painel web — pode usar Markdown completo (tabelas, listas, negrito, código).",
        "whatsapp":  "Você está respondendo no WhatsApp — use texto simples, sem Markdown pesado. Emojis moderadamente.",
        "telegram":  "Você está respondendo no Telegram — pode usar negrito (*texto*) e código (`code`), mas evite tabelas.",
    }.get(channel_type, "")

    # Data/hora BR
    now = datetime.now()
    now_br = now.strftime("%A, %d de %B de %Y às %H:%M")
    # Tradução simples do dia/mês
    trans = {
        "Monday": "segunda-feira", "Tuesday": "terça-feira", "Wednesday": "quarta-feira",
        "Thursday": "quinta-feira", "Friday": "sexta-feira", "Saturday": "sábado", "Sunday": "domingo",
        "January": "janeiro", "February": "fevereiro", "March": "março", "April": "abril",
        "May": "maio", "June": "junho", "July": "julho", "August": "agosto",
        "September": "setembro", "October": "outubro", "November": "novembro", "December": "dezembro",
    }
    for en, pt in trans.items():
        now_br = now_br.replace(en, pt)

    # Partes do system prompt
    parts: list[str] = []

    # 1. Identidade e backstory
    identity = _read_file(IDENTITY_DIR / "identity.md")
    if identity:
        parts.append(identity)

    # 2. Tom e voz
    soul = _read_file(IDENTITY_DIR / "soul.md")
    if soul:
        parts.append(soul)

    # 3. Persona canônica + guardrails
    persona = _read_file(IDENTITY_DIR / "marcos_persona.md")
    if persona:
        parts.append(persona)

    # 4. Capabilities (dinâmico)
    capabilities = _get_capabilities(regenerate_capabilities)
    if capabilities:
        parts.append(capabilities)

    # 5. Memórias recentes
    memories = _get_recent_memories(n=3)
    if memories:
        parts.append(f"## Memórias recentes\n\n{memories}")

    # 6. Contexto de runtime
    runtime_ctx = f"""## Contexto de runtime

- **Agora**: {now_br}
- **Canal**: {channel}
- **Usuário**: {user or 'dono'}
{f'- **Formato**: {format_note}' if format_note else ''}

Responda sempre em português brasileiro. Se o canal for WhatsApp, seja ainda mais conciso.
"""
    parts.append(runtime_ctx)

    system_prompt = "\n\n---\n\n".join(p for p in parts if p.strip())

    # Calcula hashes
    prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
    capabilities_hash = hashlib.sha256(capabilities.encode()).hexdigest()[:16]

    result = {
        "system_prompt": system_prompt,
        "hash": prompt_hash,
        "capabilities_hash": capabilities_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "user": user,
        "char_count": len(system_prompt),
    }

    # Salva cache
    try:
        cache_data = {**result, "_cached_at": datetime.now().timestamp()}
        CACHE_FILE.write_text(json.dumps(cache_data, ensure_ascii=False))
    except Exception:
        pass

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gera system prompt do Marcos")
    parser.add_argument("--channel", default="panel", help="canal de origem (panel/whatsapp:x/telegram:y)")
    parser.add_argument("--user", default="", help="nome do usuário")
    parser.add_argument("--json", action="store_true", help="output JSON completo")
    parser.add_argument("--regen", action="store_true", help="força regeneração das capabilities")
    args = parser.parse_args()

    result = get_system_prompt(
        channel=args.channel,
        user=args.user,
        regenerate_capabilities=args.regen,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["system_prompt"])
        print(f"\n[hash={result['hash']} | {result['char_count']} chars | cap_hash={result['capabilities_hash']}]",
              file=sys.stderr)
