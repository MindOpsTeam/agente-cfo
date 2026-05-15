# Portabilidade de Memória — Agente CFO

## Sprint 46 — Export/Import de memória do Marcos

---

## memory_stats.sh — Introspectiva da memória

```bash
# Human-readable
bash memory_stats.sh

# JSON (para Marcos usar em prompts)
bash memory_stats.sh --json
```

Saída JSON:
```json
{
  "entries": 83,
  "diary_files": 2,
  "total_lines": 322,
  "oldest_diary": "2026-03-29",
  "newest_diary": "2026-03-30",
  "workspace_size_kb": 3.9,
  "has_memory_md": false,
  "has_soul_md": true,
  "root_files": ["SOUL.md", "USER.md", "IDENTITY.md", "AGENTS.md"],
  "tags": { "financeiro": 12, "vendas": 8 }
}
```

---

## memory_export.sh — Exporta memória

```bash
# Export padrão
bash memory_export.sh

# Com histórico de sessões (pode ser grande)
bash memory_export.sh --include-sessions

# Com canvas snapshots
bash memory_export.sh --include-canvas --output ~/minha-memoria.tar.gz
```

### O que inclui

| Arquivo | Descrição |
|---------|-----------|
| `workspace/memory/*.md` | Diários de memória (logs diários) |
| `workspace/MEMORY.md` | Memória de longa duração (se existir) |
| `workspace/SOUL.md` | Personalidade e valores do Marcos |
| `workspace/USER.md` | Perfil do usuário |
| `workspace/IDENTITY.md` | Identidade do agente |
| `workspace/AGENTS.md` | Regras de workspace |
| `workspace/TOOLS.md` | Notas sobre ferramentas |
| `memory/main.sql` | Dump do índice vetorial (SQLite) |
| `metadata.json` | Stats e timestamp do export |
| `sessions/*.jsonl` | Histórico de runs (com `--include-sessions`) |
| `canvas/` | Snapshots visuais (com `--include-canvas`) |

Output: `~/.agente-cfo/exports/memory-<timestamp>.tar.gz`

---

## memory_import.sh — Importa memória

```bash
# Merge (padrão — seguro, idempotente)
bash memory_import.sh ~/minha-memoria.tar.gz

# Dry-run: mostra mudanças sem aplicar
bash memory_import.sh ~/minha-memoria.tar.gz --dry-run

# Replace: substitui tudo (⚠️ DESTRUCTIVO — faz backup antes)
bash memory_import.sh ~/minha-memoria.tar.gz --replace
```

### Comportamento por modo

| Item | `--merge` (padrão) | `--replace` |
|------|-------------------|-------------|
| Diários novos | Copia | Copia |
| Diários existentes | Appenda linhas novas | Sobrescreve |
| SOUL.md, USER.md | NÃO sobrescreve | Sobrescreve (bak criado) |
| MEMORY.md | NÃO sobrescreve | Sobrescreve (bak criado) |
| Sessions | Não importa | Importa faltantes |

**Idempotente em `--merge`**: importar o mesmo export múltiplas vezes não duplica conteúdo.

---

## Casos de uso

### Backup manual da memória

```bash
bash memory_export.sh
# → ~/.agente-cfo/exports/memory-20260515_131631.tar.gz
```

### Migrar Marcos para nova VPS

```bash
# VPS original
bash memory_export.sh --include-sessions --output ~/marcos-completo.tar.gz

# Nova VPS (após instalar agente)
bash memory_import.sh ~/marcos-completo.tar.gz --replace
```

### Clonar configuração para segundo agente (--merge)

```bash
# Exportar memória base
bash memory_export.sh --output ~/marcos-base.tar.gz

# Importar na segunda instância sem sobrescrever identidade local
bash memory_import.sh ~/marcos-base.tar.gz --merge
```

### Consulta rápida (Marcos usa em heartbeats)

```bash
bash memory_stats.sh --json
# Retorna JSON com contagem de entries, período, tamanho
```

---

## Via painel (Sprint 46 — Lovable AI)

Edge functions necessárias:
- `memory-export` (GET, JWT): dispara Marcos → `memory_export.sh` → upload Storage → signed URL
- `memory-import` (POST, JWT): Marcos baixa URL → `memory_import.sh`

Bucket Supabase Storage: `cfo-memory-exports` (signed URLs TTL 15min, policy auth.uid)
