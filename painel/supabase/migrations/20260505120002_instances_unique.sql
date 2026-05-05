-- =============================================================================
-- Migration: 003 — Unique index em instances(license_id, hostname)
-- Necessário para o upsert em clients-register funcionar sem erro 42P10.
-- Sem cláusula WHERE: o supabase-js exige constraint não-parcial para o
-- ON CONFLICT funcionar. NULLs em hostname não conflitam entre si por
-- padrão no Postgres, então múltiplas rows com hostname NULL continuam
-- permitidas — comportamento equivalente ao parcial, sem o 42P10.
-- =============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS instances_license_hostname_unique
  ON instances(license_id, hostname);
