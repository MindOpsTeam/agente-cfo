-- =============================================================================
-- Migration: 003 — Unique index em instances(license_id, hostname)
-- Necessário para o upsert em clients-register funcionar sem erro 42P10.
-- Index parcial: WHERE hostname IS NOT NULL porque NULLs não conflitam no
-- Postgres e o schema permite hostname NULL no primeiro register.
-- =============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS instances_license_hostname_unique
  ON instances(license_id, hostname) WHERE hostname IS NOT NULL;
