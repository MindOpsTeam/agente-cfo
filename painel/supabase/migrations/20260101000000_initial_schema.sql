-- =============================================================================
-- Migration: 001 — Schema inicial single-tenant (Agente CFO)
--
-- Single-tenant: cada cliente tem seu próprio projeto Supabase.
-- Sem tenant_id, sem license key. Auth VPS↔painel via X-Panel-Token.
-- Auth do front Lovable: Supabase Auth padrão (usuário autenticado).
-- =============================================================================

-- instances: VPS rodando OpenClaw + skill agente-cfo
CREATE TABLE IF NOT EXISTS instances (
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

-- Unique por hostname para upsert no instance-register.
-- Sem WHERE: supabase-js exige constraint não-parcial para ON CONFLICT.
-- NULLs não conflitam entre si por padrão no Postgres.
CREATE UNIQUE INDEX IF NOT EXISTS instances_hostname_unique
  ON instances(hostname);

ALTER TABLE instances ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'instances' AND policyname = 'authenticated_select'
  ) THEN
    CREATE POLICY "authenticated_select" ON instances
      FOR SELECT TO authenticated USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'instances' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY "service_role_all" ON instances
      FOR ALL USING (auth.role() = 'service_role');
  END IF;
END $$;

-- events: log de eventos enviados pela skill
CREATE TABLE IF NOT EXISTS events (
  id          bigserial   PRIMARY KEY,
  instance_id uuid        NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  type        text        NOT NULL,
  severity    text        NOT NULL DEFAULT 'info',
  payload     jsonb       NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS events_instance_created_idx ON events(instance_id, created_at DESC);
CREATE INDEX IF NOT EXISTS events_type_idx             ON events(type);

ALTER TABLE events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'events' AND policyname = 'authenticated_select'
  ) THEN
    CREATE POLICY "authenticated_select" ON events
      FOR SELECT TO authenticated USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'events' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY "service_role_all" ON events
      FOR ALL USING (auth.role() = 'service_role');
  END IF;
END $$;

-- llm_usage: custo agregado por sessão e período
CREATE TABLE IF NOT EXISTS llm_usage (
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

CREATE UNIQUE INDEX IF NOT EXISTS llm_usage_upsert_key
  ON llm_usage(instance_id, session_id, period);

CREATE INDEX IF NOT EXISTS llm_usage_instance_period_idx
  ON llm_usage(instance_id, period);

ALTER TABLE llm_usage ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'llm_usage' AND policyname = 'authenticated_select'
  ) THEN
    CREATE POLICY "authenticated_select" ON llm_usage
      FOR SELECT TO authenticated USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'llm_usage' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY "service_role_all" ON llm_usage
      FOR ALL USING (auth.role() = 'service_role');
  END IF;
END $$;

-- omie_errors: erros da API Omie
CREATE TABLE IF NOT EXISTS omie_errors (
  id          bigserial   PRIMARY KEY,
  instance_id uuid        NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  command     text,
  http_status int,
  message     text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS omie_errors_instance_created_idx
  ON omie_errors(instance_id, created_at DESC);

ALTER TABLE omie_errors ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'omie_errors' AND policyname = 'authenticated_select'
  ) THEN
    CREATE POLICY "authenticated_select" ON omie_errors
      FOR SELECT TO authenticated USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'omie_errors' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY "service_role_all" ON omie_errors
      FOR ALL USING (auth.role() = 'service_role');
  END IF;
END $$;

-- whatsapp_status: histórico de status da conexão WA
CREATE TABLE IF NOT EXISTS whatsapp_status (
  id          bigserial   PRIMARY KEY,
  instance_id uuid        NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
  status      text        NOT NULL,
  jid         text,
  last_check  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS whatsapp_status_instance_idx
  ON whatsapp_status(instance_id, created_at DESC);

ALTER TABLE whatsapp_status ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'whatsapp_status' AND policyname = 'authenticated_select'
  ) THEN
    CREATE POLICY "authenticated_select" ON whatsapp_status
      FOR SELECT TO authenticated USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'whatsapp_status' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY "service_role_all" ON whatsapp_status
      FOR ALL USING (auth.role() = 'service_role');
  END IF;
END $$;

-- audit_log: ações do painel (push command, etc)
CREATE TABLE IF NOT EXISTS audit_log (
  id            bigserial   PRIMARY KEY,
  actor_user_id uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  action        text        NOT NULL,
  payload       jsonb       NOT NULL DEFAULT '{}',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_created_idx ON audit_log(created_at DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'audit_log' AND policyname = 'authenticated_select'
  ) THEN
    CREATE POLICY "authenticated_select" ON audit_log
      FOR SELECT TO authenticated USING (true);
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'audit_log' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY "service_role_all" ON audit_log
      FOR ALL USING (auth.role() = 'service_role');
  END IF;
END $$;
