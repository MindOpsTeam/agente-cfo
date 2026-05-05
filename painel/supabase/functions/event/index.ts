/**
 * POST /event
 * Recebe eventos da skill agente-cfo e os persiste.
 * Para tipos específicos, cria registros derivados:
 *   - omie_error       → insere em omie_errors
 *   - wa_status_changed → insere em whatsapp_status
 *
 * Auth: X-License header
 * Body: { instance_id, type, severity?, payload? }
 * Retorna: { event_id }
 */

import {
  adminClient,
  corsHeaders,
  errorResponse,
  jsonResponse,
  validateLicense,
} from "../_shared/auth.ts";

const VALID_SEVERITIES = ["info", "warn", "error", "critical"] as const;
type Severity = typeof VALID_SEVERITIES[number];

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
    type?: string;
    severity?: string;
    payload?: Record<string, unknown>;
  };

  try {
    body = await req.json();
  } catch {
    return errorResponse("Body JSON inválido", 400);
  }

  if (!body.instance_id) return errorResponse("instance_id obrigatório", 400);
  if (!body.type)        return errorResponse("type obrigatório", 400);

  const severity: Severity = VALID_SEVERITIES.includes(body.severity as Severity)
    ? (body.severity as Severity)
    : "info";

  const payload = body.payload ?? {};

  const supabase = adminClient();

  // ── Verificar que instance pertence a este tenant ───────────────────────
  const { data: instance } = await supabase
    .from("instances")
    .select("id")
    .eq("id", body.instance_id)
    .eq("tenant_id", license.tenantId)
    .maybeSingle();

  if (!instance) {
    return errorResponse("instance_id não encontrado ou não autorizado", 404);
  }

  // ── Inserir evento principal ────────────────────────────────────────────
  const { data: event, error: eventError } = await supabase
    .from("events")
    .insert({
      tenant_id: license.tenantId,
      instance_id: body.instance_id,
      type: body.type,
      severity,
      payload,
    })
    .select("id")
    .single();

  if (eventError || !event) {
    console.error("Event insert error:", eventError);
    return errorResponse("Erro ao inserir evento", 500);
  }

  // ── Registros derivados ─────────────────────────────────────────────────

  // omie_error → omie_errors
  if (body.type === "omie_error") {
    await supabase.from("omie_errors").insert({
      tenant_id: license.tenantId,
      instance_id: body.instance_id,
      command: payload.command as string ?? null,
      http_status: payload.http_status as number ?? null,
      message: payload.message as string ?? null,
    });
  }

  // wa_status_changed → whatsapp_status
  if (body.type === "wa_status_changed") {
    const wa_status = payload.status as string ?? "unknown";
    const valid_statuses = ["connected", "disconnected", "qr_expired", "unknown"];
    await supabase.from("whatsapp_status").insert({
      tenant_id: license.tenantId,
      instance_id: body.instance_id,
      status: valid_statuses.includes(wa_status) ? wa_status : "unknown",
      jid: payload.jid as string ?? null,
      last_check: new Date().toISOString(),
    });
  }

  // whatsapp_disconnected / whatsapp_repaired (de repare.sh / whatsapp-watch.sh)
  if (body.type === "whatsapp_disconnected") {
    await supabase.from("whatsapp_status").insert({
      tenant_id: license.tenantId,
      instance_id: body.instance_id,
      status: "disconnected",
      jid: null,
      last_check: new Date().toISOString(),
    });
  }

  if (body.type === "whatsapp_reconnected" || body.type === "whatsapp_repaired") {
    await supabase.from("whatsapp_status").insert({
      tenant_id: license.tenantId,
      instance_id: body.instance_id,
      status: "connected",
      jid: payload.jid as string ?? null,
      last_check: new Date().toISOString(),
    });
  }

  return jsonResponse({ event_id: event.id }, 201);
});
