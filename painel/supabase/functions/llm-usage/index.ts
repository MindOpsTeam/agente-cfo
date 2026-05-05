/**
 * POST /llm-usage
 * Upsert de custo LLM por sessão e período.
 * Chave de upsert: (tenant_id, instance_id, session_id, period).
 *
 * Auth: X-License header
 * Body: { instance_id, session_id, model, input_tokens, output_tokens, cost_brl, period }
 * Retorna: { id, cost_brl_total_period }
 *
 * cost_brl_total_period: soma do custo do tenant no período (para o cliente
 * saber se está perto do limite sem precisar de outro endpoint).
 */

import {
  adminClient,
  corsHeaders,
  errorResponse,
  jsonResponse,
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
    session_id?: string;
    model?: string;
    input_tokens?: number;
    output_tokens?: number;
    cost_brl?: number;
    period?: string;  // 'YYYY-MM'
  };

  try {
    body = await req.json();
  } catch {
    return errorResponse("Body JSON inválido", 400);
  }

  if (!body.instance_id) return errorResponse("instance_id obrigatório", 400);
  if (!body.session_id)  return errorResponse("session_id obrigatório", 400);
  if (!body.period)      return errorResponse("period obrigatório (YYYY-MM)", 400);

  // Validar formato do period
  if (!/^\d{4}-\d{2}$/.test(body.period)) {
    return errorResponse("period deve estar no formato YYYY-MM", 400);
  }

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

  // ── Upsert llm_usage ────────────────────────────────────────────────────
  // ON CONFLICT (tenant_id, instance_id, session_id, period):
  // Sobrescreve com os valores mais recentes (o check-budget.sh envia o
  // acumulado da sessão, não incrementos).
  const { data: usage, error: upsertError } = await supabase
    .from("llm_usage")
    .upsert(
      {
        tenant_id: license.tenantId,
        instance_id: body.instance_id,
        session_id: body.session_id,
        model: body.model ?? "unknown",
        input_tokens: body.input_tokens ?? 0,
        output_tokens: body.output_tokens ?? 0,
        cost_brl: body.cost_brl ?? 0,
        period: body.period,
      },
      {
        onConflict: "tenant_id,instance_id,session_id,period",
        ignoreDuplicates: false,
      },
    )
    .select("id")
    .single();

  if (upsertError || !usage) {
    console.error("LLM usage upsert error:", upsertError);
    return errorResponse("Erro ao registrar uso LLM", 500);
  }

  // ── Retornar total do período para feedback ao cliente ──────────────────
  const { data: total } = await supabase
    .from("llm_usage")
    .select("cost_brl")
    .eq("tenant_id", license.tenantId)
    .eq("period", body.period);

  const totalPeriod = (total ?? []).reduce(
    (sum, row) => sum + (Number(row.cost_brl) || 0),
    0,
  );

  return jsonResponse({
    id: usage.id,
    cost_brl_total_period: Number(totalPeriod.toFixed(2)),
  });
});
