# Arquitetura — Agente CFO

## Visão geral

```
┌──────────────────────────────────────────────────────────────────┐
│                    LOVABLE CLOUD                                 │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │               PAINEL WEB (TanStack Start + React)          │ │
│  │  /chat /automations /integrations /settings /alerts        │ │
│  └─────────────────────────────────┬───────────────────────────┘ │
│                                    │                             │
│  ┌─────────────────────────────────▼───────────────────────────┐ │
│  │               SUPABASE                                      │ │
│  │  PostgreSQL · Edge Functions · Realtime · Storage           │ │
│  │                                                              │ │
│  │  Tabelas principais:                                         │ │
│  │  chat_messages · automation_runs · automations               │ │
│  │  integration_credentials · instance_metrics · alerts_config  │ │
│  │  whatsapp_instances · telegram_bots · supabase_projects      │ │
│  └─────────────────────────────────┬───────────────────────────┘ │
└────────────────────────────────────┼─────────────────────────────┘
                                     │ HTTPS / webhooks
                                     │
┌────────────────────────────────────▼─────────────────────────────┐
│                    VPS LINUX (cliente)                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 Cloudflare Tunnel                        │   │
│  │  (ingress público → localhost:18789)                     │   │
│  └──────────────────────────┬─────────────────────────────-─┘   │
│                             │                                    │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │              OpenClaw Gateway (:18789)                  │    │
│  │  WebSocket · HTTP /v1/chat · /tools/invoke · /hooks     │    │
│  │                                                          │    │
│  │  Agente: Marcos (Claude Sonnet 4.6)                     │    │
│  │  Session: agent:main:main (persistente)                  │    │
│  └──────────┬──────────────────────────────────────────────┘    │
│             │ MCP stdio (spawn por tool call)                    │
│  ┌──────────▼──────────────────────────────────────────────┐    │
│  │         17 MCP Servers (Python 3.12 · 1.279 tools)     │    │
│  │                                                          │    │
│  │  ERPs: Omie(96) Bling(116) Tiny(28) Granatum(39)        │    │
│  │        VHSYS(54) Nibo(40) ContaAzul(32)                │    │
│  │  CRMs: HubSpot(463) RDStation(27) PipeRun(27)          │    │
│  │        Pipedrive(144) Kommo(85)                         │    │
│  │  Cobr: Asaas(33) Iugu(33)                              │    │
│  │  Ecom: MercadoLivre(27) Nuvemshop(35)                  │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Daemons CFO (14 systemd units)             │   │
│  │                                                          │   │
│  │  credentials-sync  → materializa secrets do painel     │   │
│  │  evolution-sync    → sync instâncias WhatsApp          │   │
│  │  telegram-sync     → registro webhooks Telegram        │   │
│  │  supabase-sync     → MCP servers Supabase              │   │
│  │  automation-engine → executa automações agendadas      │   │
│  │  mcp-warmer        → pre-warm (reduz cold-start)       │   │
│  │  metrics-publisher → publica métricas pro painel       │   │
│  │  alerts-checker    → avalia alertas configurados       │   │
│  │  health-doctor     → auto-recovery de daemons          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ~/.openclaw/secrets/<skill>.env  (credenciais por skill)       │
│  ~/.agente-cfo/logs/*.log          (logs de cada daemon)        │
│  ~/.agente-cfo/backups/            (backups periódicos)         │
└──────────────────────────────────────────────────────────────────┘
         │                    │                  │
         ▼                    ▼                  ▼
   Evolution API         Telegram API       APIs ERPs/CRMs
   (WhatsApp Multi)      (Bot API)          (Omie, HubSpot...)
```

---

## Fluxo de mensagem (painel → Marcos → MCP → resposta)

```
1. User → POST /chat-send-message (JWT Supabase)
2. Edge fn → INSERT chat_messages (user, status=sent)
3. Edge fn → POST /hooks/agent (VPS ingress + hooks_token)
4. OpenClaw → executa run do agente Marcos
5. Marcos → tool calls → spawna MCP server (ex: omie_clientes_listar)
6. MCP → HTTP request → Omie API → retorna JSON
7. Marcos → sintetiza resposta
8. Marcos → bash panel_reply.sh → POST /chat-marcos-reply (X-Panel-Token)
9. Edge fn → UPDATE chat_messages (marcos, status=sent)
10. Supabase Realtime → push pro browser do cliente
```

### Fluxo canal externo (WhatsApp/Telegram)

```
1. Msg entra → POST /whatsapp-incoming-webhook (X-Webhook-Secret)
2. Wrapper → valida secret → POST /incoming-message (normalizado)
3. incoming-message → INSERT chat_messages (user, channel=whatsapp:X)
4. incoming-message → POST /hooks/agent (VPS)
5. Marcos → processa → bash send_evolution.sh + panel_post_reply.sh
```

---

## Segurança

### Camadas de autenticação

| Camada | Mecanismo | Onde |
|--------|-----------|------|
| Painel web | Supabase Auth (JWT) | Edge functions verify_jwt=true |
| VPS → Painel | `X-Panel-Token` (HMAC) | Heartbeat, metrics, chat-marcos-reply |
| Painel → VPS | `hooks_token` (Bearer) | /hooks/agent da VPS |
| Webhooks externos | `webhook_secret` por instância | Evolution, Telegram |
| MCP → APIs externas | Credentials em `secrets/<skill>.env` | Materializado por credentials-sync |
| Admin actions | Whitelist em admin_action.sh | Sem eval, sem injection |

### Encriptação de credenciais

```
User cola API key no painel
  ↓ AES-256-GCM (CFO_VAULT_ENC_KEY, só no Supabase Edge Runtime)
  ↓ integration_credentials.credentials_encrypted (DB)
  ↓ Edge fn descriptografa em runtime
  ↓ POST /integration-credentials-vps-list (X-Panel-Token + X-Hooks-Token)
  ↓ credentials_sync.py → ~/.openclaw/secrets/<skill>.env (chmod 600)
  ↓ MCP server lê em runtime
```

A `service_role_key` do Supabase e tokens de APIs **nunca ficam em plaintext fora do Edge Runtime ou do .env da VPS**.

---

## Row Level Security (Supabase)

Todas as tabelas principais têm RLS ativa:
- **Leitura**: `auth.uid()` = dono (single-tenant: 1 painel = 1 instância = 1 user)
- **Escrita via painel**: JWT do usuário logado
- **Escrita via VPS**: service_role (edge functions com SUPABASE_SERVICE_ROLE_KEY)

---

## Limitações conhecidas

| Limitação | Detalhe |
|-----------|---------|
| Single-tenant | 1 painel = 1 empresa. Múltiplas empresas = múltiplos deploys |
| Latência LLM | Claude Sonnet 4.6 tem ~3-8s de latência base (não otimizável) |
| WhatsApp QR | Requer varredura manual; não tem WhatsApp Business API |
| MCP cold start | ~200-500ms por MCP server (mitigado pelo mcp-warmer) |
| Histórico cross-channel | Threads separados por canal (não unificados por identidade) |
| Backup de secrets | Backup sanitizado por padrão; `--include-secrets` apenas para migração |

---

## Dependências externas

| Serviço | Plano mínimo | Custo aprox |
|---------|-------------|-------------|
| VPS Linux | 1 vCPU / 1 GB | R$30–80/mês |
| Anthropic (Claude) | API key | R$30–100/mês uso |
| Lovable | Free tier | Gratuito |
| Supabase | Free tier | Gratuito |
| Cloudflare | Free tunnel | Gratuito |
| Evolution API | Self-hosted ou SaaS | Variável |
