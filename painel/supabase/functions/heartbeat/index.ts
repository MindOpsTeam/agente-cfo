/**
 * POST /heartbeat
 * Atualiza last_heartbeat e status da instância. Chamado a cada ~5 minutos
 * pelo cfo-reporter.sh ou por um cron separado no cliente.
 *
 * Auth: X-License header
 * Body: { instance_id, openclaw_version?, ingress_url? }
 * Retorna: 204 No Content em sucesso
 */

import {
  adminClient,
  corsHeaders,
  errorResponse,
  validateLicense,
} from "../_shared/auth.ts";

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  // ── Validar licença ─────────────────────────────────────────────────────
  const license = await validateLicense(req);
  if (!license) {
    return errorResponse("License inválida", 401);
  }

  // ── Parsear body ────────────────────────────────────────────────────────
  let body: {
    instance_id?: string;
    openclaw_version?: string;
    ingress_url?: string;
  };

  try {
    body = await req.json();
  } catch {
    return errorResponse("Body JSON inválido", 400);
  }

  if (!body.instance_id) {
    return errorResponse("instance_id obrigatório", 400);
  }

  const supabase = adminClient();

  // ── Verificar que instance_id pertence a este tenant ────────────────────
  const { data: instance } = await supabase
    .from("instances")
    .select("id")
    .eq("id", body.instance_id)
    .eq("tenant_id", license.tenantId)
    .maybeSingle();

  if (!instance) {
    return errorResponse("instance_id não encontrado ou não autorizado", 404);
  }

  // ── Atualizar heartbeat ─────────────────────────────────────────────────
  const updateData: Record<string, unknown> = {
    last_heartbeat: new Date().toISOString(),
    status: "online",
  };

  if (body.openclaw_version) {
    updateData.openclaw_version = body.openclaw_version;
  }
  if (body.ingress_url) {
    updateData.ingress_url = body.ingress_url;
  }

  const { error: updateError } = await supabase
    .from("instances")
    .update(updateData)
    .eq("id", body.instance_id);

  if (updateError) {
    console.error("Heartbeat update error:", updateError);
    return errorResponse("Erro ao atualizar heartbeat", 500);
  }

  return new Response(null, { status: 204, headers: corsHeaders });
});
