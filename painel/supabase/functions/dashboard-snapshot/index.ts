/**
 * GET/POST /dashboard-snapshot
 * Agrega KPIs de todas as integrações ativas do usuário, com cache de 5 min.
 * Auth: JWT Supabase do dono logado no front Lovable.
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

  // ── Auth JWT ──────────────────────────────────────────────────────────────
  const authHeader = req.headers.get("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return errorResponse("Authorization header obrigatório", 401);
  }

  const anonKey =
    Deno.env.get("SUPABASE_PUBLISHABLE_KEY") ??
    Deno.env.get("SUPABASE_ANON_KEY");
  if (!anonKey) {
    return errorResponse("Configuração do painel incompleta", 500);
  }

  const supabaseUser = createClient(
    Deno.env.get("SUPABASE_URL")!,
    anonKey,
    { global: { headers: { Authorization: authHeader } } },
  );

  const {
    data: { user },
    error: userError,
  } = await supabaseUser.auth.getUser();
  if (userError || !user) {
    return errorResponse("JWT inválido ou expirado", 401);
  }

  const supabase = adminClient();

  // ── Busca instância ─────────────────────────────────────────────────────
  const { data: instance } = await supabase
    .from("instances")
    .select("ingress_url, hooks_token")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!instance?.ingress_url || !instance?.hooks_token) {
    return errorResponse("Instância não encontrada ou sem ingress_url/hooks_token", 422);
  }

  // ── Busca tenant → connected_integrations ───────────────────────────────
  const { data: tenant } = await supabase
    .from("tenants")
    .select("metadata")
    .eq("user_id", user.id)
    .maybeSingle();

  const connectedIntegrations: string[] =
    tenant?.metadata?.connected_integrations ?? [];

  if (connectedIntegrations.length === 0) {
    return errorResponse("Nenhuma integração conectada no tenant", 422);
  }

  // ── Cache 5 min ─────────────────────────────────────────────────────────
  const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
  const { data: cached } = await supabase
    .from("dashboard_snapshots")
    .select("data")
    .eq("user_id", user.id)
    .gt("created_at", fiveMinAgo)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (cached?.data) {
    return jsonResponse(cached.data);
  }

  // ── Fetch paralelo de cada integração ──────────────────────────────────
  interface IntegrationResult {
    name: string;
    data: Record<string, unknown> | null;
    error: string | null;
  }

  const results: IntegrationResult[] = await Promise.all(
    connectedIntegrations.map(async (integration: string): Promise<IntegrationResult> => {
      try {
        const resp = await fetch(`${instance.ingress_url}/hooks/agent`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${instance.hooks_token}`,
          },
          body: JSON.stringify({
            message: `Execute: python3 /opt/agente-cfo/skills/${integration}/scripts/dashboard_metrics.py`,
            name: "DashboardSnapshot",
            deliver: false,
            timeoutSeconds: 30,
          }),
          signal: AbortSignal.timeout(35_000),
        });

        const text = await resp.text();
        let parsed: Record<string, unknown> | null = null;

        // Tenta parsear JSON do body (pode ter texto extra)
        try {
          parsed = JSON.parse(text);
        } catch {
          const jsonMatch = text.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            try {
              parsed = JSON.parse(jsonMatch[0]);
            } catch {
              // ignore
            }
          }
        }

        return { name: integration, data: parsed, error: null };
      } catch (err) {
        return { name: integration, data: null, error: String(err) };
      }
    }),
  );

  // ── Agregação ──────────────────────────────────────────────────────────
  const kpis = {
    balance_brl: 0,
    receivables_30d_brl: 0,
    payables_30d_brl: 0,
    pipeline_weighted_brl: 0,
    ecommerce_revenue_month_brl: 0,
    overdue_total_brl: 0,
  };

  const byChannelRevenue: { channel: string; brl: number }[] = [];
  let pipelineByStage: unknown[] = [];
  let cashProjection90d: unknown[] = [];
  let topDebtors: unknown[] = [];
  const integrationsHealth: { name: string; status: string; last_sync: string | null }[] = [];

  let balanceSet = false;
  let pipelineSet = false;
  let erpSet = false;

  for (const r of results) {
    if (!r.data) {
      integrationsHealth.push({ name: r.name, status: "error", last_sync: null });
      continue;
    }

    const d = r.data as Record<string, unknown>;
    const health = d.health as Record<string, unknown> | undefined;

    integrationsHealth.push({
      name: r.name,
      status: (health?.status as string) ?? "unknown",
      last_sync: (health?.last_sync as string) ?? null,
    });

    // ERP fields
    const balanceBrl = Number(d.balance_brl ?? 0);
    if (!balanceSet && balanceBrl > 0) {
      kpis.balance_brl = balanceBrl;
      balanceSet = true;
    }

    kpis.receivables_30d_brl += Number(d.receivables_brl ?? 0);
    kpis.payables_30d_brl += Number(d.payables_brl ?? 0);
    kpis.overdue_total_brl += Number(d.overdue_total_brl ?? 0);

    // CRM fields
    kpis.pipeline_weighted_brl += Number(d.pipeline_weighted_brl ?? 0);
    if (!pipelineSet && Array.isArray(d.pipeline_by_stage) && d.pipeline_by_stage.length > 0) {
      pipelineByStage = d.pipeline_by_stage as unknown[];
      pipelineSet = true;
    }

    // ERP projection/debtors (first available)
    if (!erpSet && Array.isArray(d.cash_projection_90d) && d.cash_projection_90d.length > 0) {
      cashProjection90d = d.cash_projection_90d as unknown[];
      topDebtors = (d.top_debtors as unknown[]) ?? [];
      erpSet = true;
    }

    // Ecommerce
    const ecomRev = Number(d.ecommerce_revenue_month_brl ?? 0);
    kpis.ecommerce_revenue_month_brl += ecomRev;

    // by_channel_revenue
    const rev =
      Number(d.receivables_brl ?? 0) +
      ecomRev;
    if (rev > 0) {
      byChannelRevenue.push({ channel: r.name, brl: rev });
    }
  }

  const snapshotPayload = {
    as_of: new Date().toISOString(),
    kpis,
    by_channel_revenue_30d: byChannelRevenue,
    pipeline_by_stage: pipelineByStage,
    cash_projection_90d: cashProjection90d,
    top_debtors: topDebtors,
    integrations_health: integrationsHealth,
  };

  // ── Salva cache ────────────────────────────────────────────────────────
  await supabase.from("dashboard_snapshots").insert({
    user_id: user.id,
    data: snapshotPayload,
    created_at: new Date().toISOString(),
  });

  return jsonResponse(snapshotPayload);
});
