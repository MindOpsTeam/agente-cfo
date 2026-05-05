/**
 * POST /push-command
 * Envia um comando do painel para a instância cliente via Cloudflare Tunnel.
 * O cliente recebe via POST /hooks/agent (endpoint OpenClaw).
 *
 * Auth: Supabase JWT (dono do painel — auth.uid() válido)
 * Body: { tenant_id, instance_id, command }
 *   command: string livre executado como message no hooks/agent
 *   Ex: "Execute: openclaw plugins update agente-cfo"
 *
 * Retorna: { ok: true, openclaw_response: <response do cliente> }
 *
 * Segurança:
 *   - JWT validado pelo Supabase (Authorization: Bearer <jwt>)
 *   - tenant_id do body deve bater com app_metadata.tenant_id do JWT
 *   - instance_id deve pertencer ao tenant
 *   - hooks_token da instância usado para autenticar no cliente
 */

import {
  adminClient,
  corsHeaders,
  errorResponse,
  jsonResponse,
} from "../_shared/auth.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  // ── Validar JWT do dono (Supabase Auth) ────────────────────────────────
  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return errorResponse("Authorization header obrigatório", 401);
  }

  // Client com o JWT do usuário para verificar identidade
  const supabaseUser = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } },
  );

  const { data: { user }, error: userError } = await supabaseUser.auth.getUser();
  if (userError || !user) {
    return errorResponse("JWT inválido ou expirado", 401);
  }

  // Extrair tenant_id do custom claim
  const jwtTenantId = user.app_metadata?.tenant_id as string | undefined;
  if (!jwtTenantId) {
    return errorResponse("tenant_id não encontrado no JWT (custom claim ausente)", 403);
  }

  // ── Parsear body ────────────────────────────────────────────────────────
  let body: {
    tenant_id?: string;
    instance_id?: string;
    command?: string;
  };

  try {
    body = await req.json();
  } catch {
    return errorResponse("Body JSON inválido", 400);
  }

  if (!body.tenant_id)   return errorResponse("tenant_id obrigatório", 400);
  if (!body.instance_id) return errorResponse("instance_id obrigatório", 400);
  if (!body.command)     return errorResponse("command obrigatório", 400);

  // Validar que o tenant_id do body bate com o JWT
  if (body.tenant_id !== jwtTenantId) {
    return errorResponse("tenant_id não autorizado", 403);
  }

  const supabase = adminClient();

  // ── Buscar instância e validar posse ────────────────────────────────────
  const { data: instance } = await supabase
    .from("instances")
    .select("id, ingress_url, hooks_token, status")
    .eq("id", body.instance_id)
    .eq("tenant_id", body.tenant_id)
    .maybeSingle();

  if (!instance) {
    return errorResponse("instance_id não encontrado ou não autorizado", 404);
  }

  if (!instance.ingress_url) {
    return errorResponse("Instância não possui ingress_url configurado", 422);
  }

  if (!instance.hooks_token) {
    return errorResponse(
      "Instância não possui hooks_token — cliente precisa se re-registrar",
      422,
    );
  }

  // ── Disparar comando no cliente via OpenClaw /hooks/agent ───────────────
  const hookPayload = {
    message: body.command,
    name: "PainelCFO",
    wakeMode: "now",
    deliver: false,  // não precisamos da resposta no WhatsApp do cliente
    timeoutSeconds: 60,
  };

  let clientResponse: Response;
  let clientBody: string;

  try {
    clientResponse = await fetch(`${instance.ingress_url}/hooks/agent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${instance.hooks_token}`,
      },
      body: JSON.stringify(hookPayload),
      signal: AbortSignal.timeout(30_000),  // 30s timeout
    });
    clientBody = await clientResponse.text();
  } catch (err) {
    // Falha de rede — cliente offline ou tunnel down
    await supabase.from("audit_log").insert({
      tenant_id: body.tenant_id,
      actor_user_id: user.id,
      action: "push_command_failed",
      payload: {
        instance_id: body.instance_id,
        command: body.command,
        error: String(err),
      },
    });

    // Marcar instância como degraded
    await supabase
      .from("instances")
      .update({ status: "degraded" })
      .eq("id", body.instance_id);

    return errorResponse(`Falha ao contatar a instância: ${String(err)}`, 502);
  }

  // ── Logar no audit_log ──────────────────────────────────────────────────
  await supabase.from("audit_log").insert({
    tenant_id: body.tenant_id,
    actor_user_id: user.id,
    action: "push_command",
    payload: {
      instance_id: body.instance_id,
      command: body.command,
      client_status: clientResponse.status,
    },
  });

  if (!clientResponse.ok) {
    return errorResponse(
      `Cliente retornou erro ${clientResponse.status}: ${clientBody}`,
      502,
    );
  }

  return jsonResponse({
    ok: true,
    openclaw_response: clientBody,
  });
});
