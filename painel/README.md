# Agente CFO — Painel Central (Backend)

Backend Supabase do painel multi-tenant. O front (Lovable) conecta neste mesmo projeto.

## Pré-requisitos

- [Supabase CLI](https://supabase.com/docs/guides/cli) >= 2.75
- Conta Supabase (free tier é suficiente)

```bash
# Instalar CLI (macOS)
brew install supabase/tap/supabase
```

---

## 1. Criar projeto Supabase novo

```bash
# Login
supabase login
# Abre browser para autenticação

# Criar projeto via CLI (região sa-east-1 = São Paulo)
supabase projects create agente-cfo-painel \
  --region sa-east-1 \
  --db-password "<senha-forte-aqui>"

# Anotar o project_ref retornado (ex: abcdefghijklmnop)
```

Alternativamente, crie pelo dashboard em https://supabase.com/dashboard e copie o `project_ref` da URL.

---

## 2. Linkar e configurar

```bash
cd painel/

# Linkar ao projeto criado
supabase link --project-ref <project_ref>

# Copiar .env.example e preencher
cp .env.example .env
# Editar .env com SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
# (valores em: https://supabase.com/dashboard/project/<project_ref>/settings/api)
```

---

## 3. Aplicar migrations

```bash
# Push de todas as migrations em supabase/migrations/
supabase db push

# Verificar que as tabelas foram criadas
supabase db remote query \
  "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1;"
```

**Migrations incluídas:**
- `20260505120000_initial_schema.sql` — Schema completo (tabelas + índices + RLS + policies)
- `20260505120001_auth_triggers.sql` — Trigger de signup (custom claim tenant_id) + generate_license_key()

### Ativar pg_cron (mark_offline worker)

O pg_cron não é aplicável via migration no Supabase free tier. Rode manualmente no SQL Editor após o push:

```sql
-- Dashboard > SQL Editor
SELECT cron.schedule(
  'mark-instances-offline',
  '*/15 * * * *',
  $$
    UPDATE public.instances
    SET status = 'offline'
    WHERE status != 'offline'
      AND (last_heartbeat IS NULL OR last_heartbeat < now() - interval '15 minutes');
  $$
);
```

---

## 4. Deploy das edge functions

```bash
# Deploy de todas as funções de uma vez
supabase functions deploy clients-register
supabase functions deploy heartbeat
supabase functions deploy event
supabase functions deploy llm-usage
supabase functions deploy push-command

# Verificar status
supabase functions list
```

As funções leem `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` do ambiente Supabase automaticamente.
Não é necessário setar secrets para essas variáveis — o runtime Deno as injeta.

---

## 5. Referência dos endpoints

Base URL: `https://<project_ref>.supabase.co/functions/v1`

### POST `/clients-register`

Registra ou atualiza uma instância VPS do cliente.

**Auth:** `X-License: lk_xxxxx`

**Body:**
```json
{
  "hostname": "vps-cliente-abc",
  "openclaw_version": "2026.3.28",
  "agente_cfo_version": "1.0.0",
  "ingress_url": "https://tunnel-abc.trycloudflare.com",
  "hooks_token": "tok_xxxx"
}
```

**Resposta 200:**
```json
{
  "instance_id": "uuid",
  "panel_config": {
    "llm_budget_brl": 50,
    "alert_thresholds": {
      "wa_disconnect_minutes": 60
    }
  }
}
```

**Curl:**
```bash
curl -X POST https://<project_ref>.supabase.co/functions/v1/clients-register \
  -H "X-License: lk_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "vps-teste",
    "openclaw_version": "2026.3.28",
    "agente_cfo_version": "1.0.0",
    "ingress_url": "https://tunnel.example.com",
    "hooks_token": "tok_abc"
  }'
```

---

### POST `/heartbeat`

Atualiza last_heartbeat da instância (chamar a cada ~5 min).

**Auth:** `X-License: lk_xxxxx`

**Body:**
```json
{
  "instance_id": "uuid",
  "openclaw_version": "2026.3.28"
}
```

**Resposta:** `204 No Content`

**Curl:**
```bash
curl -X POST https://<project_ref>.supabase.co/functions/v1/heartbeat \
  -H "X-License: lk_abc123" \
  -H "Content-Type: application/json" \
  -d '{"instance_id": "uuid-da-instancia"}'
```

---

### POST `/event`

Envia evento de telemetria. Tipos especiais (`omie_error`, `wa_status_changed`,
`whatsapp_disconnected`, `whatsapp_reconnected`) criam registros derivados.

**Auth:** `X-License: lk_xxxxx`

**Body:**
```json
{
  "instance_id": "uuid",
  "type": "omie_error",
  "severity": "error",
  "payload": {
    "command": "resumo_financeiro",
    "http_status": 401,
    "message": "Invalid credentials"
  }
}
```

**Severity válidos:** `info` | `warn` | `error` | `critical`

**Resposta 201:**
```json
{ "event_id": 42 }
```

**Curl:**
```bash
curl -X POST https://<project_ref>.supabase.co/functions/v1/event \
  -H "X-License: lk_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "uuid",
    "type": "doctor",
    "severity": "info",
    "payload": {"overall": "ok"}
  }'
```

---

### POST `/llm-usage`

Upsert de uso LLM por sessão e período.

**Auth:** `X-License: lk_xxxxx`

**Body:**
```json
{
  "instance_id": "uuid",
  "session_id": "agent:main:main:abc123",
  "model": "anthropic/claude-sonnet-4-6",
  "input_tokens": 1500,
  "output_tokens": 350,
  "cost_brl": 0.03,
  "period": "2026-05"
}
```

**Resposta 200:**
```json
{
  "id": 7,
  "cost_brl_total_period": 12.45
}
```

**Curl:**
```bash
curl -X POST https://<project_ref>.supabase.co/functions/v1/llm-usage \
  -H "X-License: lk_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "uuid",
    "session_id": "sess_abc",
    "model": "anthropic/claude-sonnet-4-6",
    "input_tokens": 1000,
    "output_tokens": 200,
    "cost_brl": 0.02,
    "period": "2026-05"
  }'
```

---

### POST `/push-command`

Envia comando do painel para a instância cliente.

**Auth:** `Authorization: Bearer <supabase-jwt>` (JWT do dono logado no painel)

**Body:**
```json
{
  "tenant_id": "uuid-do-tenant",
  "instance_id": "uuid-da-instancia",
  "command": "Execute: bash ~/.openclaw/workspace/skills/agente-cfo/scripts/doctor.sh"
}
```

**Resposta 200:**
```json
{
  "ok": true,
  "openclaw_response": "..."
}
```

**Curl (exemplo com JWT):**
```bash
curl -X POST https://<project_ref>.supabase.co/functions/v1/push-command \
  -H "Authorization: Bearer <jwt-do-dono>" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "uuid",
    "instance_id": "uuid",
    "command": "Execute: openclaw plugins update agente-cfo"
  }'
```

---

## 6. Criar primeira licença (admin)

Não há UI ainda (Fase 3). Use o SQL Editor do Supabase:

```sql
-- Criar tenant manualmente (ou deixar o trigger de signup fazer)
INSERT INTO tenants (nome, email_dono, plano)
VALUES ('Empresa Teste', 'dono@empresa.com.br', 'starter')
RETURNING id;

-- Criar licença para o tenant
INSERT INTO licenses (tenant_id, license_key, max_instances)
VALUES (
  '<tenant_id>',
  generate_license_key(),  -- usa a função criada na migration
  1
)
RETURNING license_key;
-- Anotar o license_key retornado e enviar ao cliente
```

---

## 7. Decisões técnicas documentadas

| Decisão | Escolha | Motivo |
|---|---|---|
| Auth cliente→painel | X-License header | Sem JWT para evitar sessão no servidor da VPS |
| Auth painel→cliente (push) | hooks_token Bearer | Token gerado pelo setup.sh no cliente, enviado no register |
| Upsert instância | license_id + hostname | Permite re-registro sem duplicar (mesmo hostname, mesma licença) |
| Coluna `instances.hooks_token` | Adicionada ao schema | Necessária para push-command — sem ela o painel não consegue autenticar no cliente |
| Coluna `tenants.metadata jsonb` | Adicionada ao schema | Evita tabela extra para config por tenant (budget, thresholds) |
| Coluna `licenses.max_instances` | Adicionada ao schema | Limitar VPS por licença é feature de monetização (starter=1, pro=5) |
| pg_cron `mark_offline` | Comentado na migration | pg_cron no free tier requer SQL Editor manual — documentado aqui |
| `push-command` timeout | 30s + AbortSignal | Cloudflare Tunnel pode estar lento; 30s é razoável sem bloquear o dono |
