/**
 * _shared/auth.ts
 * Helpers de autenticação para edge functions do Agente CFO.
 */

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Supabase admin client (service_role) — para operações que ignoram RLS
// ---------------------------------------------------------------------------
export function adminClient(): SupabaseClient {
  const url = Deno.env.get("SUPABASE_URL")!;
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  return createClient(url, key, {
    auth: { persistSession: false },
  });
}

// ---------------------------------------------------------------------------
// Validar X-License header e retornar { license, tenant }
// Retorna null se a license_key for inválida ou revogada.
// ---------------------------------------------------------------------------
export interface LicenseContext {
  licenseId: string;
  tenantId: string;
  maxInstances: number;
  tenantMetadata: Record<string, unknown>;
}

export async function validateLicense(
  req: Request,
): Promise<LicenseContext | null> {
  const licenseKey = req.headers.get("X-License");
  if (!licenseKey) return null;

  const supabase = adminClient();

  const { data, error } = await supabase
    .from("licenses")
    .select("id, tenant_id, status, expires_at, max_instances, tenants(metadata)")
    .eq("license_key", licenseKey)
    .single();

  if (error || !data) return null;

  // Checar status
  if (data.status !== "active") return null;

  // Checar expiração
  if (data.expires_at && new Date(data.expires_at) < new Date()) return null;

  return {
    licenseId: data.id,
    tenantId: data.tenant_id,
    maxInstances: data.max_instances ?? 1,
    tenantMetadata: (data.tenants as any)?.metadata ?? {},
  };
}

// ---------------------------------------------------------------------------
// Resposta de erro padronizada
// ---------------------------------------------------------------------------
export function errorResponse(
  message: string,
  status: number,
): Response {
  return new Response(
    JSON.stringify({ error: message }),
    {
      status,
      headers: { "Content-Type": "application/json" },
    },
  );
}

// ---------------------------------------------------------------------------
// Resposta de sucesso padronizada
// ---------------------------------------------------------------------------
export function jsonResponse(
  data: unknown,
  status = 200,
): Response {
  return new Response(
    JSON.stringify(data),
    {
      status,
      headers: { "Content-Type": "application/json" },
    },
  );
}

// ---------------------------------------------------------------------------
// CORS headers padrão
// ---------------------------------------------------------------------------
export const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-license",
};
