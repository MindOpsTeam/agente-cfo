-- =============================================================================
-- Migration: 004 — Simplificação para single-tenant (template gratuito)
--
-- Remove toda a infraestrutura multi-tenant (tenants, licenses, tenant_id em
-- tudo, trigger de signup, license key auth). Recria as tabelas sem tenant_id.
--
-- Auth entre VPS e painel: header X-Panel-Token validado contra secret
-- PANEL_TOKEN configurado pelo próprio cliente nas edge functions.
-- Auth do painel (front Lovable): Supabase Auth padrão (qualquer user logado).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Drop objetos existentes (ordem respeita FKs)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS audit_log       CASCADE;
DROP TABLE IF EXISTS whatsapp_status CASCADE;
DROP TABLE IF EXISTS omie_errors     CASCADE;
DROP TABLE IF EXISTS llm_usage       CASCADE;
DROP TABLE IF EXISTS events          CASCADE;
DROP TABLE IF EXISTS instances       CASCADE;
DROP TABLE IF EXISTS licenses        CASCADE;
DROP TABLE IF EXISTS tenants_users   CASCADE;
DROP TABLE IF EXISTS tenants         CASCADE;

DROP TRIGGER  IF EXISTS on_auth_user_created   ON auth.users;
DROP FUNCTION IF EXISTS handle_new_user_signup();
DROP FUNCTION IF EXISTS generate_license_key();

-- ---------------------------------------------------------------------------
-- 2. Recriar tabelas — single-tenant, sem tenant_id
-- ---------------------------------------------------------------------------

-- instances: VPS rodando OpenClaw + skill agente-cfo
CREATE TABLE instances (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hostname            text,
  openclaw_version    text,
  agente_cfo_version  text,
  ingress_url         text,
  hooks_token         text,
  last_heartbeat      timestamptz,
  status              text        NOT NULL DEFAULT 'unknown',
  created_at          timestamptz NOT NULL DEFAULT now()
);

-- Unique por hostname para upsert no instance-register
CREATE UNIQUE INDEX instances_hostname_unique
  ON instances(hostname) WHERE hostname IS NOT NULL;

ALTER TABLE instances ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_select" ON instances
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "service_role_all" ON instances
  FOR ALL USING (auth.role() = 'service_role');

-- events: log de eventos enviados pela skill
CREATE TABLE events (
  id          bigserial   PRIMARY KEY,
  instance_id uuid        NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  type        text        NOT NULL,
  severity    text        NOT NULL DEFAULT 'info',
  payload     jsonb       NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX events_instance_created_idx ON events(instance_id, created_at DESC);
CREATE INDEX events_type_idx             ON events(type);

ALTER TABLE events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_select" ON events
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "service_role_all" ON events
  FOR ALL USING (auth.role() = 'service_role');

-- llm_usage: custo agregado por sessão e período
CREATE TABLE llm_usage (
  id            bigserial      PRIMARY KEY,
  instance_id   uuid           NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  session_id    text           NOT NULL,
  model         text           NOT NULL DEFAULT 'unknown',
  input_tokens  int            NOT NULL DEFAULT 0,
  output_tokens int            NOT NULL DEFAULT 0,
  cost_brl      numeric(10,2)  NOT NULL DEFAULT 0,
  period        char(7)        NOT NULL,
  created_at    timestamptz    NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX llm_usage_upsert_key
  ON llm_usage(instance_id, session_id, period);

CREATE INDEX llm_usage_instance_period_idx
  ON llm_usage(instance_id, period);

ALTER TABLE llm_usage ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_select" ON llm_usage
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "service_role_all" ON llm_usage
  FOR ALL USING (auth.role() = 'service_role');

-- omie_errors: erros da API Omie
CREATE TABLE omie_errors (
  id          bigserial   PRIMARY KEY,
  instance_id uuid        NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  command     text,
  http_status int,
  message     text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX omie_errors_instance_created_idx
  ON omie_errors(instance_id, created_at DESC);

ALTER TABLE omie_errors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_select" ON omie_errors
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "service_role_all" ON omie_errors
  FOR ALL USING (auth.role() = 'service_role');

-- whatsapp_status: histórico de status da conexão WA
CREATE TABLE whatsapp_status (
  id          bigserial   PRIMARY KEY,
  instance_id uuid        NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  status      text        NOT NULL,
  jid         text,
  last_check  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX whatsapp_status_instance_idx
  ON whatsapp_status(instance_id, created_at DESC);

ALTER TABLE whatsapp_status ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_select" ON whatsapp_status
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "service_role_all" ON whatsapp_status
  FOR ALL USING (auth.role() = 'service_role');

-- audit_log: ações do painel (push command, etc)
CREATE TABLE audit_log (
  id            bigserial   PRIMARY KEY,
  actor_user_id uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  action        text        NOT NULL,
  payload       jsonb       NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_log_created_idx ON audit_log(created_at DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_select" ON audit_log
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "service_role_all" ON audit_log
  FOR ALL USING (auth.role() = 'service_role');
