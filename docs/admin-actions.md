# Admin Actions — Agente CFO

Interface whitelisted de comandos OpenClaw/systemd para uso via painel ou chat.
Implementado em `skills/agente-cfo/scripts/admin_action.sh`.

## Uso

```bash
# Via pipe
echo '{"action":"openclaw_health"}' | bash admin_action.sh

# Via argumento
bash admin_action.sh '{"action":"openclaw_config_get","key":"gateway.port"}'
```

Retorna sempre JSON:
```json
{ "ok": true|false, "output": "...", "error": "...", "took_ms": 234 }
```

## Como Marcos usa

No prompt do Marcos (via painel/WhatsApp/Telegram):

```
Execute via admin_action.sh e reporte o resultado:
  echo '{"action":"openclaw_health"}' | bash "$HOME/.openclaw/workspace/skills/agente-cfo/scripts/admin_action.sh"
```

A edge function `vps-admin-action` (Lovable AI implementa) encaminha a ação pro Marcos
que executa `admin_action.sh` e retorna output via `panel_reply.sh`.

---

## Actions disponíveis

### OpenClaw Config

| Action | Params | Descrição |
|--------|--------|-----------|
| `openclaw_config_get` | `key` | Lê valor de config |
| `openclaw_config_set` | `key`, `value` | Seta config (detecta JSON automaticamente) |
| `openclaw_config_unset` | `key` | Remove config |
| `openclaw_config_validate` | — | Valida openclaw.json |

**Exemplo:**
```json
{"action": "openclaw_config_get", "key": "gateway.port"}
→ {"ok": true, "output": "18789", "took_ms": 1270}
```

```json
{"action": "openclaw_config_set", "key": "gateway.controlUi.dangerouslyDisableDeviceAuth", "value": "true"}
```

### OpenClaw Plugins

| Action | Params | Descrição |
|--------|--------|-----------|
| `openclaw_plugins_list` | — | Lista plugins instalados |
| `openclaw_plugins_install` | `plugin` | Instala plugin (charset: `[a-zA-Z0-9@/_:.-]+`) |
| `openclaw_plugins_enable` | `plugin` | Habilita plugin |
| `openclaw_plugins_disable` | `plugin` | Desabilita plugin |

### OpenClaw MCP

| Action | Params | Descrição |
|--------|--------|-----------|
| `openclaw_mcp_list` | — | Lista MCP servers |
| `openclaw_mcp_set` | `name`, `value_json` | Registra MCP server |
| `openclaw_mcp_unset` | `name` | Remove MCP server |

### OpenClaw Status

| Action | Params | Descrição |
|--------|--------|-----------|
| `openclaw_status` | — | Status geral do gateway |
| `openclaw_health` | — | Health check |
| `openclaw_doctor` | — | Diagnóstico completo |

### Systemd (serviços whitelist)

**Whitelist**: só aceita prefixos `cfo-*`, `openclaw-*` ou `cloudflared-cfo`.
Tentativa de usar outro serviço retorna erro 403.

| Action | Params | Descrição |
|--------|--------|-----------|
| `systemctl_restart` | `service` | Reinicia serviço |
| `systemctl_start` | `service` | Inicia serviço |
| `systemctl_stop` | `service` | Para serviço |
| `systemctl_status` | `service` | Status do serviço |
| `service_logs` | `service`, `lines?` (max 500) | Logs do serviço |

**Serviços disponíveis:**
```
cfo-proactive, cfo-automation-engine, cfo-credentials-sync,
cfo-supabase-sync, cfo-evolution-sync, cfo-telegram-sync,
cfo-mcp-warmer, openclaw-gateway, cloudflared-cfo,
cfo-supabase-sync, cfo-telegram-sync
```

**Exemplo:**
```json
{"action": "systemctl_restart", "service": "cfo-automation-engine"}
→ {"ok": true, "output": "reiniciado: cfo-automation-engine", "took_ms": 892}
```

```json
{"action": "service_logs", "service": "cfo-mcp-warmer", "lines": "30"}
```

### Helpers internos

| Action | Params | Descrição |
|--------|--------|-----------|
| `mcp_sync_now` | — | Força sync imediato dos MCP servers |
| `self_update` | — | Atualiza todas as skills via git pull |

---

## Segurança

- **Sem eval**: nenhum argumento é passado para shell sem escape
- **Whitelist exaustiva**: qualquer action fora da lista retorna erro
- **Plugin name**: validado com regex `[a-zA-Z0-9@/_:.-]+` (sem espaços, sem `;`, sem `|`)
- **Service name**: regex `^(cfo-|openclaw-|cloudflared-cfo)[a-z0-9._-]+$`
- **Lines param**: validado como inteiro ≤ 500
- **Value params**: passados como argumentos posicionais (não interpolados no comando)

---

## Exemplos de uso via Marcos (chat/WhatsApp)

> "Marcos, reinicia o serviço cfo-automation-engine"

Marcos executa:
```bash
echo '{"action":"systemctl_restart","service":"cfo-automation-engine"}' | bash admin_action.sh
```

> "Marcos, qual o status do OpenClaw?"

```bash
echo '{"action":"openclaw_status"}' | bash admin_action.sh
```

> "Marcos, instala o plugin meu-plugin"

```bash
echo '{"action":"openclaw_plugins_install","plugin":"meu-plugin"}' | bash admin_action.sh
```

> "Marcos, mostra os últimos 20 logs do cfo-evolution-sync"

```bash
echo '{"action":"service_logs","service":"cfo-evolution-sync","lines":"20"}' | bash admin_action.sh
```
