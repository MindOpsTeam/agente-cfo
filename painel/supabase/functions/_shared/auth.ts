/**
 * _shared/auth.ts
 * Helpers de autenticação para edge functions do Agente CFO (single-tenant).
 *
 * Auth da VPS → painel: header X-Panel-Token validado contra env PANEL_TOKEN.
 * Auth do front → painel: JWT Supabase padrão (push-command).
 */

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Supabase admin client (service_role) — ignora RLS
// ---------------------------------------------------------------------------
export function adminClient(): SupabaseClient {
  const url = Deno.env.get("SUPABASE_URL")!;
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  return createClient(url, key, {
    auth: { persistSession: false },
  });
}

// ---------------------------------------------------------------------------
// Validar X-Panel-Token contra env PANEL_TOKEN
// Retorna true se válido, false caso contrário.
// ---------------------------------------------------------------------------
export function validatePanelToken(req: Request): boolean {
  const token = req.headers.get("X-Panel-Token");
  if (!token) return false;
  const expected = Deno.env.get("PANEL_TOKEN");
  if (!expected) return false;
  // Comparação constante (evita timing attacks)
  if (token.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < token.length; i++) {
    diff |= token.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}

// ---------------------------------------------------------------------------
// Resposta de erro padronizada
// ---------------------------------------------------------------------------
export function errorResponse(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Resposta de sucesso padronizada
// ---------------------------------------------------------------------------
export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// CORS headers padrão
// ---------------------------------------------------------------------------
export const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-panel-token",
};
