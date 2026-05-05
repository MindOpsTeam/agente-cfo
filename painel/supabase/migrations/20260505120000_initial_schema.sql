-- =============================================================================
-- Migration: 001 — Initial schema
-- Agente CFO — Painel Central
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_cron";

-- ---------------------------------------------------------------------------
-- TENANTS
-- Empresa cliente. Não é tenanted por si (é a raiz do tenant).
-- RLS: cada row acessada via tenants_users join.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome          text NOT NULL,
  email_dono    text NOT NULL,
  plano         text NOT NULL DEFAULT 'starter',  -- starter|pro|enterprise
  status        text NOT NULL DEFAULT 'active',   -- active|suspended|cancelled
  -- Configurações por tenant (budget, thresholds) sem tabela extra
  metadata      jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN tenants.metadata IS
  'Configurações por tenant: llm_budget_brl, alert_wa_disconnect_minutes, etc.';

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

-- Dono acessa seu tenant via tenants_users
CREATE POLICY "tenant_owner_select" ON tenants
  FOR SELECT USING (
    id IN (
      SELECT tenant_id FROM tenants_users
      WHERE user_id = auth.uid()
    )
  );

-- Apenas service_role insere/atualiza tenants (via edge function ou admin)
CREATE POLICY "service_role_all" ON tenants
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- TENANTS_USERS
-- N:N entre auth.users e tenants.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants_users (
  user_id       uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  role          text NOT NULL DEFAULT 'owner',  -- owner|viewer
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, tenant_id)
);

ALTER TABLE tenants_users ENABLE ROW LEVEL SECURITY;

-- Usuário vê suas próprias rows
CREATE POLICY "user_own_rows" ON tenants_users
  FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "service_role_all" ON tenants_users
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- LICENSES
-- Uma license key por instância (VPS). Pode ter N por tenant.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS licenses (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  license_key   text NOT NULL UNIQUE,
  status        text NOT NULL DEFAULT 'active',  -- active|revoked|expired
  max_instances int  NOT NULL DEFAULT 1,          -- quantas VPS essa key pode registrar
  expires_at    timestamptz,                      -- null = sem expiração
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS licenses_tenant_id_idx ON licenses(tenant_id);
CREATE INDEX IF NOT EXISTS licenses_key_idx       ON licenses(license_key);

ALTER TABLE licenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_select" ON licenses
  FOR SELECT USING (
    tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  );

CREATE POLICY "service_role_all" ON licenses
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- INSTANCES
-- VPS do cliente rodando OpenClaw + skill agente-cfo.
-- hooks_token: token gerado na primeira instância para o painel autenticar
--              quando faz POST /hooks/agent no cliente (push-command).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instances (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  license_id            uuid NOT NULL REFERENCES licenses(id) ON DELETE RESTRICT,
  hostname              text,
  openclaw_version      text,
  agente_cfo_version    text,
  ingress_url           text,       -- URL do Cloudflare Tunnel
  hooks_token           text,       -- token Bearer para POST /hooks/agent no cliente
  last_heartbeat        timestamptz,
  status                text NOT NULL DEFAULT 'unknown',  -- online|offline|degraded|unknown
  created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS instances_tenant_id_idx     ON instances(tenant_id);
CREATE INDEX IF NOT EXISTS instances_license_id_idx    ON instances(license_id);
CREATE INDEX IF NOT EXISTS instances_last_heartbeat_idx ON instances(last_heartbeat);

ALTER TABLE instances ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_select" ON instances
  FOR SELECT USING (
    tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  );

CREATE POLICY "service_role_all" ON instances
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- EVENTS
-- Log de todos os eventos enviados pela skill agente-cfo no cliente.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
  id            bigserial PRIMARY KEY,
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  instance_id   uuid NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  type          text NOT NULL,                    -- 'doctor'|'alerta_enviado'|'omie_error'|'wa_status_changed'|...
  severity      text NOT NULL DEFAULT 'info',     -- info|warn|error|critical
  payload       jsonb NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS events_tenant_created_idx ON events(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS events_type_idx           ON events(type);
CREATE INDEX IF NOT EXISTS events_instance_idx       ON events(instance_id);

ALTER TABLE events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_select" ON events
  FOR SELECT USING (
    tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  );

CREATE POLICY "service_role_all" ON events
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- LLM_USAGE
-- Custo agregado por sessão OpenClaw e período (YYYY-MM).
-- Upsert pela edge function usando (tenant_id, instance_id, session_id, period) como chave.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_usage (
  id              bigserial PRIMARY KEY,
  tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  instance_id     uuid NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  session_id      text NOT NULL,
  model           text NOT NULL DEFAULT 'unknown',
  input_tokens    int  NOT NULL DEFAULT 0,
  output_tokens   int  NOT NULL DEFAULT 0,
  cost_brl        numeric(10,2) NOT NULL DEFAULT 0,
  period          char(7) NOT NULL,   -- 'YYYY-MM'
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS llm_usage_upsert_key
  ON llm_usage(tenant_id, instance_id, session_id, period);

CREATE INDEX IF NOT EXISTS llm_usage_tenant_period_idx
  ON llm_usage(tenant_id, period);

ALTER TABLE llm_usage ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_select" ON llm_usage
  FOR SELECT USING (
    tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  );

CREATE POLICY "service_role_all" ON llm_usage
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- OMIE_ERRORS
-- Erros específicos da API Omie. Serve para alertar se a API mudou.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS omie_errors (
  id            bigserial PRIMARY KEY,
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  instance_id   uuid NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  command       text,
  http_status   int,
  message       text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS omie_errors_tenant_created_idx
  ON omie_errors(tenant_id, created_at DESC);

ALTER TABLE omie_errors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_select" ON omie_errors
  FOR SELECT USING (
    tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  );

CREATE POLICY "service_role_all" ON omie_errors
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- WHATSAPP_STATUS
-- Último estado conhecido da conexão WhatsApp por instância.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS whatsapp_status (
  id            bigserial PRIMARY KEY,
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  instance_id   uuid NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  status        text NOT NULL,   -- connected|disconnected|qr_expired|unknown
  jid           text,            -- JID WhatsApp quando conectado
  last_check    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS whatsapp_status_instance_idx
  ON whatsapp_status(instance_id, created_at DESC);

ALTER TABLE whatsapp_status ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_select" ON whatsapp_status
  FOR SELECT USING (
    tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  );

CREATE POLICY "service_role_all" ON whatsapp_status
  FOR ALL USING (auth.role() = 'service_role');

-- ---------------------------------------------------------------------------
-- AUDIT_LOG
-- Ações disparadas pelo painel (push command, revogar licença, etc).
-- actor_user_id null = ação de sistema (pg_cron, edge function interna).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
  id              bigserial PRIMARY KEY,
  tenant_id       uuid REFERENCES tenants(id) ON DELETE SET NULL,
  actor_user_id   uuid REFERENCES auth.users(id) ON DELETE SET NULL,  -- null = system
  action          text NOT NULL,
  payload         jsonb NOT NULL DEFAULT '{}',
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_tenant_created_idx
  ON audit_log(tenant_id, created_at DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- owner vê o audit_log do seu tenant
CREATE POLICY "tenant_select" ON audit_log
  FOR SELECT USING (
    tenant_id::text = (auth.jwt() -> 'app_metadata' ->> 'tenant_id')
  );

CREATE POLICY "service_role_all" ON audit_log
  FOR ALL USING (auth.role() = 'service_role');
