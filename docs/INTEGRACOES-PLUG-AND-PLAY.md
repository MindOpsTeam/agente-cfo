# INTEGRACOES-PLUG-AND-PLAY.md — Guia de Integrações

> **Versão:** Sprint INTEGRATIONS-1 (2026-05-20)  
> **Escopo:** 17 skills ERP/CRM/cobrança/e-commerce + Supabase multi-projeto + Telegram

---

## TL;DR — Fluxo Completo

```
Painel /integrations → Conectar → Testar → Aguarda 3 min → Marcos reconhece automaticamente
```

---

## 1. Mapa de Integrações

### ERPs

| Skill | Auth | Campos | Docs |
|-------|------|--------|------|
| **Omie** | API Key | `OMIE_APP_KEY`, `OMIE_APP_SECRET` | [developer.omie.com.br](https://developer.omie.com.br/) |
| **Bling** | OAuth 2.0 | Fluxo OAuth | [bling.com.br/developer](https://developer.bling.com.br/) |
| **Tiny ERP** | API Key | `TINY_TOKEN` | [erp.tiny.com.br/configuracoes](https://erp.tiny.com.br/configuracoes_api_web_services) |
| **Granatum** | API Key | `GRANATUM_API_KEY` | [app.granatum.com.br](https://app.granatum.com.br/integracoes) |
| **VHSYS** | API Key | `VHSYS_ACCESS_TOKEN`, `VHSYS_SECRET_TOKEN` | — |
| **Nibo** | API Key | `NIBO_API_TOKEN` | — |
| **ContaAzul** | OAuth 2.0 | Fluxo OAuth | [developers.contaazul.com](https://developers.contaazul.com/) |

### CRMs

| Skill | Auth | Campos | Docs |
|-------|------|--------|------|
| **HubSpot** | OAuth 2.0 | Fluxo OAuth | [developers.hubspot.com](https://developers.hubspot.com/) |
| **RD Station** | API Key | `RD_STATION_API_KEY` | [developers.rdstation.com](https://developers.rdstation.com/) |
| **PipeRun** | API Key | `PIPERUN_TOKEN` | — |
| **Pipedrive** | API Key | `PIPEDRIVE_API_TOKEN`, `PIPEDRIVE_COMPANY_DOMAIN` | [pipedrive.readme.io](https://pipedrive.readme.io/docs/how-to-find-the-api-token) |
| **Kommo** | API Key | `KOMMO_SUBDOMAIN`, `KOMMO_ACCESS_TOKEN` | [kommo.com/developers](https://www.kommo.com/developers/) |

### Cobrança

| Skill | Auth | Campos | Docs |
|-------|------|--------|------|
| **Asaas** | API Key | `ASAAS_API_KEY`, `ASAAS_ENV` (production/sandbox) | [docs.asaas.com](https://docs.asaas.com/) |
| **Iugu** | API Key | `IUGU_API_TOKEN` | [dev.iugu.com](https://dev.iugu.com/) |

### E-commerce

| Skill | Auth | Campos | Docs |
|-------|------|--------|------|
| **Mercado Livre** | OAuth 2.0 | Fluxo OAuth | [developers.mercadolivre.com.br](https://developers.mercadolivre.com.br/) |
| **Nuvemshop** | OAuth 2.0 | Fluxo OAuth | [tiendanube.com/developers](https://tiendanube.com/developers) |

### Banco de Dados

| Skill | Auth | Campos |
|-------|------|--------|
| **Supabase** | Rota dedicada | `project_url`, `service_role_key` (criptografada) |

---

## 2. Fluxo E2E por Tipo de Auth

### 2a. API Key (omie, asaas, tiny, granatum, vhsys, nibo, rd-station, piperun, pipedrive, kommo, iugu)

```
1. Painel → /integrations
2. Clica no card da integração → "Conectar"
3. Dialog abre com campos da skill
4. Cola as credenciais → "Salvar"
5. Clica "Testar" → edge fn integration-credentials-test verifica API real
6. Status muda para 🟢 Conectado
7. credentials-sync daemon (a cada 3 min) detecta nova credential
8. Daemon sincroniza ~/.openclaw/secrets/<skill>.env na VPS
9. mcp_manager.py registra skill no openclaw.json como MCP
10. OpenClaw Gateway recarrega MCPs (hot-reload)
11. Marcos passa a ter as tools da skill disponíveis
```

**Verificação (Marcos):**
```
Usuário: "que integrações estão ativas?"
Marcos executa: bash $SCRIPTS_DIR/integrations_status.sh
Responde: "Integrações ativas (3): Omie ✅, Asaas ✅, HubSpot ✅ ..."
```

### 2b. OAuth 2.0 (bling, contaazul, hubspot, mercado-livre, nuvemshop)

```
1. Painel → /integrations → card da skill → "Conectar"
2. Redireciona para rota dedicada (ex: /integrations/bling)
3. Clica "Autorizar com Bling" → pop-up OAuth do fornecedor
4. Usuário faz login e concede permissão
5. Callback retorna ao painel com code
6. Edge fn {skill}-oauth-exchange troca code por access_token + refresh_token
7. Tokens são salvos criptografados no Vault do Supabase
8. credentials-sync detecta e sincroniza para VPS
9. Mesmos passos 9-11 do fluxo API Key
```

**Token refresh:** daemons `{skill}-push-tokens` na VPS fazem refresh automático antes da expiração.

### 2c. Supabase multi-projeto

```
1. Painel → /integrations → card Supabase → "Gerenciar projetos"
   OU direto: /integrations/supabase
2. "Novo projeto" → preenche name + project_url + service_role_key
3. "Salvar" → key é criptografada antes de salvar no banco
4. Auto-teste: chama supabase-projects-test com a key nova
5. Status: 🟢 Conectado
6. cfo-supabase-sync daemon (a cada 5 min) detecta novo projeto
7. Daemon chama supabase-projects-vps-list (descriptografa key no edge runtime)
8. Registra mcp.servers.supabase_<slug> no openclaw.json
9. Gateway restart → Marcos passa a ter MCP supabase_<slug> disponível
10. Marcos pode executar SQL, consultar dados, chamar edge functions
```

**N projetos:** adicione quantos quiser — cada um vira um MCP `supabase_<slug>`.

### 2d. Telegram bot

```
1. BotFather → /newbot → copia token (123456789:AAxxxxxx)
2. Painel → /settings/telegram → "Adicionar bot"
3. Cola username (@meubot) + token
4. "Salvar e ativar webhook"
5. Painel calcula webhook_secret = sha256(token)[:32]
6. Salva telegram_bots no banco
7. Push command pra VPS → telegram_client.py registra webhook no Telegram
8. Webhook: POST {ingress_url}/hooks/agent (mesmo pipeline do WhatsApp)
9. Marcos recebe e responde via panel_post_reply.sh → telegram/scripts/send_message.sh
```

---

## 3. Sequência de Sincronização na VPS

```
integration_credentials salva no Supabase
        │
        ▼ (a cada 3 min)
credentials-sync daemon
  └── GET /integration-credentials-vps-list (X-Panel-Token + X-Hooks-Token)
  └── Descriptografa via Vault
  └── Grava ~/.openclaw/secrets/<skill>.env
  └── Chama mcp_manager.register_mcp(skill)
  └── openclaw config set mcp.servers.<skill> ...
        │
        ▼ (hot-reload automático)
OpenClaw Gateway recarrega MCP <skill>
        │
        ▼
Marcos tem tools de <skill> disponíveis
```

**Latência total:** ~3-8 minutos da credential salva até Marcos usar.

**Verificar na VPS:**
```bash
openclaw mcp list                            # lista MCPs registrados
openclaw config get mcp.servers.<skill>      # detalhes de uma skill
cat ~/.openclaw/secrets/<skill>.env          # credential sincronizada
```

---

## 4. Diagnóstico de Problemas

### "Conectei mas Marcos não reconhece a skill"

```bash
# 1. Verifica se credential foi sincronizada
ls ~/.openclaw/secrets/<skill>.env && cat ~/.openclaw/secrets/<skill>.env | head -1

# 2. Verifica se MCP foi registrado
openclaw mcp list | grep <skill>

# 3. Verifica log do credentials-sync
tail -50 ~/.agente-cfo/logs/credentials-sync.log

# 4. Força re-sync manual
python3 ~/.openclaw/workspace/skills/agente-cfo/scripts/credentials_sync.py

# 5. Verifica se Gateway recarregou o MCP
openclaw doctor
```

### "Teste de conexão retorna erro"

| Erro | Causa | Fix |
|------|-------|-----|
| `invalid` | Credencial inválida | Verificar a key no portal do fornecedor |
| `unreachable` | API temporariamente fora | Tentar novamente em ~10 min |
| `unknown` | Skill sem teste implementado | Verificar manualmente com curl |

### "Token OAuth expirou"

Para skills OAuth (bling, contaazul, hubspot, mercado-livre, nuvemshop):
- O daemon de refresh roda automaticamente
- Se ainda expirar: painel → integração → "Editar" → "Reautorizar"

---

## 5. Verificação via WhatsApp/Telegram

Perguntas que Marcos responde usando `integrations_status.sh`:

```
Usuário: "quais integrações estão ativas?"
Marcos:  "Integrações ativas (3):
          • Omie (ERP) ✅
          • Asaas (Cobrança) ✅
          • HubSpot (CRM) ✅
          Não conectadas: bling, tiny, granatum..."

Usuário: "que produtos tenho no bling?"
Marcos:  → chama tool MCP bling_produtos_listar
         → retorna lista real do Bling

Usuário: "crie uma cobrança de R$500 para João"
Marcos:  → identifica ERP de cobrança (asaas/iugu)
         → cria cobrança via MCP
         → confirma no canal
```

---

## 6. Adicionando Suporte para Nova Skill

Para adicionar uma nova skill ao ecossistema:

1. **Criar `skills/<nome>/mcp_server.py`** seguindo o padrão das 17 existentes
2. **Adicionar ao `INTEGRATIONS_SPEC`** em `painel-front/src/lib/integrations-spec.ts`:
   ```typescript
   {
     slug: "nova-skill",
     name: "Nova Skill",
     description: "...",
     category: "erp",
     auth_mode: "api_key",
     fields: [{ key: "NOVA_API_KEY", label: "API Key", type: "password", required: true }],
   }
   ```
3. **Implementar teste** em `integration-credentials-test/index.ts` (case `"nova-skill"`)
4. **Registrar skill** no `setup.sh` (seção de skills do monorepo)

---

## 7. Canais de Entrada

| Canal | Configuração | Status |
|-------|-------------|--------|
| **WhatsApp** | Evolution API → settings/sistema → whatsapp_instances | Via Evolution API |
| **Telegram** | BotFather → /settings/telegram | Sprint INTEGRATIONS-1 |
| **Painel web** | Direto no chat.tsx | Sempre disponível |

---

## 8. Checklist Lovable (PM dispara via lovable_send_prompt)

O seguinte está implementado no monorepo mas precisa ser **deployado/ativado via Lovable**:

- [ ] Rota `/settings/telegram` (`settings_.telegram.tsx`) — criada neste sprint
- [ ] Sidebar com link "Telegram" em "Canais" (`app-sidebar.tsx`) — atualizado neste sprint
- [ ] Checar se `routeTree.gen.ts` inclui a nova rota (Lovable regenera automaticamente)
- [ ] Migration para `telegram_bots` com campo `webhook_secret` — verificar se já existe ou criar
- [ ] Edge fn `push-command` suporta `telegram_webhook_set` payload

### SQL pra verificar se tabela telegram_bots tem todos os campos:
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'telegram_bots'
ORDER BY ordinal_position;
```
Campos esperados: `id`, `bot_username`, `bot_name`, `active`, `receives_marcos_chat`, `webhook_secret`, `created_at`.
