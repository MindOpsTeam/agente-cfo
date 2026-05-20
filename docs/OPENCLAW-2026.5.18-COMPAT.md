# OPENCLAW-2026.5.18-COMPAT.md — Sprint COMPAT-1

> **Data:** 2026-05-20  
> **Versão alvo:** OpenClaw 2026.5.18 (VPS produção)  
> **Versão de referência local:** 2026.3.28 (MacBook dev)

---

## Problema

Em produção com OpenClaw 2026.5.18:

| Sintoma | Causa raiz |
|---------|-----------|
| `trajectory.jsonl` mostra `tools: 0` | `tools.profile` não setado → gateway usa perfil sem `exec/bash` |
| `openclaw cron add` falha com `GatewayTransportError: protocol mismatch (1002)` | npm update do CLI não foi acompanhado de gateway restart |
| `/root/.openclaw/agents/main/agent/AGENT.md` vazio | setup.sh não populava workspace bootstrap files |
| `openclaw bundles list` → "Unknown command" | Comando não existe — diagnóstico manual incorreto (não é bug do setup) |
| `openclaw agents show main` → "Too many arguments" | Subcomando `show` não existe em 2026.x — usar `agents list` |

---

## O que mudou (discovery)

Executado em 2026.3.28 local + docs.openclaw.ai:

### Tools profile
- `tools.profile` não é setado por default em instalações não-interativas.
- Perfil `coding` inclui: `group:fs` + `group:runtime` + `group:web` + `group:sessions` + `group:memory` + `cron`
- `group:runtime` = `exec`, `process`, `code_execution` (**bash é alias de exec**)
- **Fix:** `openclaw config set tools.profile coding` adicionado ao setup.sh Passo 5b

### Protocol mismatch ao usar cron
- Ocorre quando o CLI (via npm) é atualizado para 2026.5.x mas o gateway systemd continua rodando 2026.3.x
- O WebSocket do gateway usa protocolo versionado; CLI novo + gateway antigo → handshake falha (1002)
- **Fix:** `systemctl restart openclaw-gateway` adicionado ANTES do bloco de enable/start do gateway

### Workspace bootstrap files
- OpenClaw 2026.5+ lê `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `TOOLS.md` do root do workspace (`agents.defaults.workspace`)
- Sem esses arquivos, o agent `main` opera sem contexto de identidade
- **Fix:** setup.sh Passo 5b cria os arquivos se não existirem; Passo 11 os atualiza após instalar a skill agente-cfo

### Approvals allowlist
- Em 2026.5.x, `exec` dentro de sandbox exige allowlist para scripts fora do workspace padrão
- **Fix:** setup.sh adiciona `openclaw approvals allowlist add` para todos os scripts CFO

---

## Comandos de diagnóstico para rodar na VPS

Se o problema persistir após atualizar o setup.sh, peça ao dono para rodar:

```bash
# 1. Versão instalada
openclaw --version

# 2. Profile atual de tools
openclaw config get tools.profile

# 3. Approvals configuradas
openclaw approvals get

# 4. Agent list (substitui "agents show main")
openclaw agents list --json

# 5. Workspace root do agent main
openclaw config get agents.defaults.workspace

# 6. Conteúdo do workspace bootstrap
ls -la $(openclaw config get agents.defaults.workspace 2>/dev/null || echo ~/.openclaw/workspace)/

# 7. Status do gateway
systemctl status openclaw-gateway --no-pager -l | tail -20
openclaw gateway status 2>/dev/null || openclaw health

# 8. Última trajectory com contagem de tools
tail -1 ~/.openclaw/sessions/*/trajectory.jsonl 2>/dev/null | \
  python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print('tools:', len(d.get('tools',[])))"

# 9. Cron list
openclaw cron list --json 2>/dev/null | python3 -c "
import json,sys
jobs = json.load(sys.stdin)
print(f'{len(jobs)} cron jobs:')
for j in jobs: print(f'  {j.get(\"name\",\"?\")} → {j.get(\"id\",\"?\")}')
"

# 10. Doctor completo
openclaw doctor 2>&1 | tail -30
```

---

## Fixes aplicados no setup.sh

### Passo 1b — detecção de versão
```bash
_OC_VERSION=$(openclaw --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
_oc_semver_gte 2026 5 0 && _OC_COMPAT_MODE="2026.5" || _OC_COMPAT_MODE="legacy"
```

### Passo 2 — re-detecção pós npm update
Re-calcula `_OC_VERSION` e `_OC_COMPAT_MODE` após `npm install -g openclaw@latest`.

### Passo 5b — tools.profile + approvals + workspace bootstrap
```bash
openclaw config set tools.profile coding
openclaw approvals allowlist add "${HOME}/.openclaw/workspace/skills/*/scripts/*.sh"
# ... (outros padrões de scripts)

# AGENTS.md, SOUL.md, IDENTITY.md criados no workspace root se não existirem
```

### Passo 9 (gateway start) — restart preventivo
```bash
if systemctl is-active --quiet openclaw-gateway; then
    systemctl restart openclaw-gateway && sleep 5
fi
systemctl enable --now openclaw-gateway
```

### Passo 11 — fixup pós-instalação da skill
```bash
cp skills/agente-cfo/identity/soul.md ~/.openclaw/workspace/SOUL.md
openclaw agents set-identity --agent main --from-identity
```

---

## SKILL.md — metadata atualizado
```yaml
"openclaw":
  "emoji": "💼"
  "requires":
    "bins": ["wacli", "python3", "curl", "jq"]
    "tools": ["exec", "read", "write", "edit"]  # declaração explícita
  "toolsProfile": "coding"                       # hint para instaladores futuros
```

---

## Notas de suposição vs. comprovação

| Item | Status |
|------|--------|
| `tools.profile coding` habilita exec/bash | ✅ Comprovado via docs.openclaw.ai/gateway/config-tools |
| `approvals allowlist add` habilita exec sem prompt | ✅ Comprovado via `openclaw approvals --help` local |
| Restart do gateway resolve protocol mismatch 1002 | ✅ Lógica comprovada (versão CLI deve = versão gateway) |
| `agents set-identity --from-identity` popula AGENT.md | ✅ Comprovado via docs.openclaw.ai/cli/agents |
| `metadata.openclaw.toolsProfile` é processado pelo installer | ⚠️ ASSUMIDO — não encontrado na doc. Provavelmente ignorado hoje; colocado como hint semântico |
| `metadata.openclaw.requires.tools` é processado pelo installer | ⚠️ ASSUMIDO — idem acima |
