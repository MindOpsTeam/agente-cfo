/**
 * POST /clients-register
 * Registra (ou atualiza) uma instância VPS do cliente no painel.
 *
 * Auth: X-License header
 * Body: { hostname, openclaw_version, agente_cfo_version, ingress_url, hooks_token }
 * Retorna: { instance_id, panel_config: { llm_budget_brl, alert_thresholds } }
 *
 * hooks_token: token Bearer que o painel usará para autenticar no cliente
 *              quando fizer POST /hooks/agent (push-command). Enviado pelo
 *              setup.sh na primeira instalação.
 */

import {
  adminClient,
  corsHeaders,
  errorResponse,
  jsonResponse,
  validateLicense,
} from "../_shared/auth.ts";

Deno.serve(async (req: Request) => {
  // CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  // ── Validar licença ─────────────────────────────────────────────────────
  const license = await validateLicense(req);
  if (!license) {
    return errorResponse("License inválida, revogada ou expirada", 401);
  }

  // ── Parsear body ────────────────────────────────────────────────────────
  let body: {
    hostname?: string;
    openclaw_version?: string;
    agente_cfo_version?: string;
    ingress_url?: string;
    hooks_token?: string;
  };

  try {
    body = await req.json();
  } catch {
    return errorResponse("Body JSON inválido", 400);
  }

  const supabase = adminClient();

  // ── Verificar quantas instâncias já existem para essa licença ──────────
  const { count } = await supabase
    .from("instances")
    .select("id", { count: "exact", head: true })
    .eq("license_id", license.licenseId);

  // Só bloqueia se houver instâncias registradas com hostname DIFERENTE
  // (permite re-registro da mesma VPS)
  if ((count ?? 0) >= license.maxInstances) {
    // Verificar se é re-registro do mesmo hostname
    const { data: existing } = await supabase
      .from("instances")
      .select("id, hostname")
      .eq("license_id", license.licenseId)
      .eq("hostname", body.hostname ?? "")
      .maybeSingle();

    if (!existing) {
      return errorResponse(
        `Limite de instâncias atingido para esta licença (max: ${license.maxInstances})`,
        403,
      );
    }
  }

  // ── Upsert em instances (chave: license_id + hostname) ─────────────────
  const upsertData = {
    tenant_id: license.tenantId,
    license_id: license.licenseId,
    hostname: body.hostname ?? null,
    openclaw_version: body.openclaw_version ?? null,
    agente_cfo_version: body.agente_cfo_version ?? null,
    ingress_url: body.ingress_url ?? null,
    hooks_token: body.hooks_token ?? null,
    last_heartbeat: new Date().toISOString(),
    status: "online",
  };

  const { data: instance, error: upsertError } = await supabase
    .from("instances")
    .upsert(upsertData, {
      onConflict: "license_id,hostname",
      ignoreDuplicates: false,
    })
    .select("id")
    .single();

  if (upsertError || !instance) {
    console.error("Upsert error:", upsertError);
    return errorResponse("Erro ao registrar instância", 500);
  }

  // ── Logar no audit_log ──────────────────────────────────────────────────
  await supabase.from("audit_log").insert({
    tenant_id: license.tenantId,
    actor_user_id: null,  // sistema
    action: "instance_registered",
    payload: {
      instance_id: instance.id,
      hostname: body.hostname,
      agente_cfo_version: body.agente_cfo_version,
    },
  });

  // ── Retornar config do painel ───────────────────────────────────────────
  const panelConfig = {
    llm_budget_brl: (license.tenantMetadata as any)?.llm_budget_brl ?? 50,
    alert_thresholds: {
      wa_disconnect_minutes:
        (license.tenantMetadata as any)?.alert_wa_disconnect_minutes ?? 60,
    },
  };

  return jsonResponse({
    instance_id: instance.id,
    panel_config: panelConfig,
  });
});
