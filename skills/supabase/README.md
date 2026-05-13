# Supabase Projects Sync

Daemon que sincroniza projetos Supabase do painel com os MCPs locais da VPS.

## Pré-requisitos

- Node.js 18+ com `npx` disponível
- Variáveis de ambiente: `PANEL_BASE_URL`, `PANEL_TOKEN`, `HOOKS_TOKEN` (em `~/.agente-cfo/.env`)
- Edge function `supabase-projects-vps-list` deployada no painel

## Como funciona

1. A cada `SUPABASE_SYNC_INTERVAL_MIN` minutos (default: 5), o daemon chama
   `GET /supabase-projects-vps-list` com `X-Panel-Token` + `X-Hooks-Token`.
2. A edge function retorna a lista de projetos ativos com a `service_role_key`
   descriptografada (a chave existe apenas na memória do Edge Runtime).
3. O daemon atualiza `~/.openclaw/openclaw.json`, seção `mcpServers`, com
   uma entrada `supabase_<slug>` por projeto.
4. Se houve mudança, executa `openclaw gateway restart` para recarregar os MCPs.

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `PANEL_BASE_URL` | Sim | URL base das edge functions |
| `PANEL_TOKEN` | Sim | Token de autenticação da VPS |
| `HOOKS_TOKEN` | Sim | Token de hooks |
| `SUPABASE_SYNC_INTERVAL_MIN` | Não | Intervalo entre syncs (default: 5) |

## Gerenciamento do serviço

```bash
# Status
systemctl status cfo-supabase-sync

# Logs em tempo real
journalctl -u cfo-supabase-sync -f

# Forçar sync imediato
systemctl restart cfo-supabase-sync

# Desativar
systemctl disable --now cfo-supabase-sync
```

## Smoke test

```bash
cd /opt/agente-cfo
python3 skills/supabase/tests/test_sync.py
```
