-- =============================================================================
-- Migration: 002 — Auth triggers e custom claims
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Função: setar tenant_id no JWT (app_metadata) quando user é criado
-- Flow: signup → trigger → find-or-create tenant → tenants_users → set app_metadata
--
-- Como funciona:
--   1. Usuário faz signup com email
--   2. Este trigger dispara AFTER INSERT ON auth.users
--   3. Busca tenant existente pelo email_dono (fluxo Hotmart: tenant já foi
--      criado pelo webhook de compra antes do signup do cliente)
--   4. Se não existir, cria tenant novo (fluxo direto / self-service)
--   5. Insere em tenants_users com ON CONFLICT DO NOTHING (idempotente)
--   6. Seta app_metadata.tenant_id no auth.users via update
--      (o JWT passa a conter tenant_id no campo app_metadata)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION handle_new_user_signup()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_tenant_id uuid;
  v_nome text;
BEGIN
  SELECT id INTO v_tenant_id
  FROM public.tenants
  WHERE email_dono = NEW.email
  LIMIT 1;

  IF v_tenant_id IS NULL THEN
    v_nome := split_part(NEW.email, '@', 1);
    INSERT INTO public.tenants (nome, email_dono, plano, status, metadata)
    VALUES (v_nome, NEW.email, 'starter', 'active',
            jsonb_build_object('llm_budget_brl', 50, 'alert_wa_disconnect_minutes', 60))
    RETURNING id INTO v_tenant_id;
  END IF;

  INSERT INTO public.tenants_users (user_id, tenant_id, role)
  VALUES (NEW.id, v_tenant_id, 'owner')
  ON CONFLICT (user_id, tenant_id) DO NOTHING;

  UPDATE auth.users
  SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) ||
    jsonb_build_object('tenant_id', v_tenant_id::text)
  WHERE id = NEW.id;

  RETURN NEW;
END;
$$;

-- Disparar após insert em auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION handle_new_user_signup();

-- ---------------------------------------------------------------------------
-- Função: gerar license_key com prefixo lk_ + uuid sem hífens
-- Usada internamente ou via API admin para criar novas licenças.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION generate_license_key()
RETURNS text
LANGUAGE sql
AS $$
  SELECT 'lk_' || replace(gen_random_uuid()::text, '-', '');
$$;

-- ---------------------------------------------------------------------------
-- pg_cron: marca instâncias offline se heartbeat > 15 minutos atrás
-- Roda toda hora. Requer pg_cron habilitado no projeto Supabase.
-- ---------------------------------------------------------------------------
-- NOTA: pg_cron jobs não são aplicáveis via migration SQL puro no Supabase
-- free tier sem SQL Editor. Manter aqui como referência; aplicar via
-- Dashboard > SQL Editor após as migrations.
--
-- SELECT cron.schedule(
--   'mark-instances-offline',
--   '*/15 * * * *',   -- a cada 15 minutos
--   $$
--     UPDATE public.instances
--     SET status = 'offline'
--     WHERE status != 'offline'
--       AND (last_heartbeat IS NULL OR last_heartbeat < now() - interval '15 minutes');
--   $$
-- );
