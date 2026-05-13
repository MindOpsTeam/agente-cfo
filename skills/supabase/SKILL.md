---
name: supabase
description: >
  Orquestra MCP servers Supabase (@supabase/mcp-server-supabase) para projetos
  do usuário. O daemon supabase_sync.py busca projetos ativos via painel e
  registra cada um como mcpServer em ~/.openclaw/openclaw.json, dando a Marcos
  acesso total aos bancos PostgreSQL via MCP oficial.
category: Ferramenta/Database
---

# Supabase Projects Sync — Skill

## O que faz

Esta skill **não é** um MCP server. Ela orquestra MCP servers externos:

1. O usuário adiciona projetos Supabase no painel web (Lovable).
2. O daemon `supabase_sync.py` roda na VPS a cada 5 minutos.
3. Para cada projeto ativo, ele registra uma entrada em `~/.openclaw/openclaw.json`:
   ```json
   "supabase_<slug>": {
     "command": "npx",
     "args": ["-y", "@supabase/mcp-server-supabase@latest"],
     "env": {
       "SUPABASE_URL": "<project_url>",
       "SUPABASE_SERVICE_ROLE_KEY": "<decrypted_key>"
     }
   }
   ```
4. Se houve mudança, reinicia o OpenClaw Gateway para que os novos MCPs sejam carregados.

## Auth

O daemon usa as mesmas credenciais que o restante do agente:
- `PANEL_BASE_URL` — URL base das edge functions
- `PANEL_TOKEN` — X-Panel-Token
- `HOOKS_TOKEN` — X-Hooks-Token

A `service_role_key` é descriptografada pela edge function `supabase-projects-vps-list`
em runtime (no Supabase Edge Runtime). A VPS nunca armazena chaves em disco.

## Systemd

Serviço: `cfo-supabase-sync.service`

```bash
systemctl status cfo-supabase-sync
journalctl -u cfo-supabase-sync -f
```

## Logs

`~/.agente-cfo/logs/supabase-sync.log`
