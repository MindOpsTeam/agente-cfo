#!/usr/bin/env python3
"""
marcos_insight_generator.py — Gera insights financeiros via Marcos (CFO IA).
Roda a cada 15 min via cron. Coleta métricas locais, envia para o LLM,
e publica insights no painel via dashboard-publish-insights.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Secrets ──────────────────────────────────────────────────────────────────

def load_secrets(skill_name: str) -> None:
    """Load ~/.openclaw/secrets/<skill>.env into os.environ."""
    path = os.path.expanduser(f"~/.openclaw/secrets/{skill_name}.env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{now_iso()}] {msg}", flush=True)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    load_secrets("agente-cfo")

    hooks_url = os.environ.get("HOOKS_URL", "").rstrip("/")
    hooks_token = os.environ.get("HOOKS_TOKEN", "")
    panel_base_url = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
    panel_token = os.environ.get("PANEL_TOKEN", "")
    active_skills = os.environ.get("ACTIVE_SKILLS", "")

    if not hooks_url or not hooks_token:
        log("ERRO: HOOKS_URL e HOOKS_TOKEN são obrigatórios.")
        return

    if not panel_base_url or not panel_token:
        log("ERRO: PANEL_BASE_URL e PANEL_TOKEN são obrigatórios.")
        return

    if not active_skills:
        log("ERRO: ACTIVE_SKILLS está vazio — nenhuma skill para coletar.")
        return

    skills = [s.strip() for s in active_skills.split(",") if s.strip()]
    log(f"Coletando métricas de {len(skills)} skills: {', '.join(skills)}")

    # ── Coleta métricas localmente ───────────────────────────────────────
    results: dict[str, dict] = {}
    for skill in skills:
        script = f"/opt/agente-cfo/skills/{skill}/scripts/dashboard_metrics.py"
        try:
            proc = subprocess.run(
                ["python3", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                results[skill] = json.loads(proc.stdout.strip())
                log(f"  {skill}: OK")
            else:
                results[skill] = {"health": {"status": "error", "error": proc.stderr[:200], "last_sync": now_iso()}}
                log(f"  {skill}: exit={proc.returncode}")
        except subprocess.TimeoutExpired:
            results[skill] = {"health": {"status": "error", "error": "timeout", "last_sync": now_iso()}}
            log(f"  {skill}: timeout")
        except Exception as e:
            results[skill] = {"health": {"status": "error", "error": str(e), "last_sync": now_iso()}}
            log(f"  {skill}: {e}")

    # ── Agrega snapshot local ────────────────────────────────────────────
    kpis = {
        "balance_brl": 0.0,
        "receivables_30d_brl": 0.0,
        "payables_30d_brl": 0.0,
        "pipeline_weighted_brl": 0.0,
        "ecommerce_revenue_month_brl": 0.0,
        "overdue_total_brl": 0.0,
    }
    pipeline_by_stage: list = []
    cash_projection_90d: list = []
    top_debtors: list = []
    integrations_health: list = []
    balance_set = False
    pipeline_set = False
    erp_set = False

    for name, d in results.items():
        health = d.get("health", {})
        integrations_health.append({
            "name": name,
            "status": health.get("status", "unknown"),
            "last_sync": health.get("last_sync"),
        })

        bal = float(d.get("balance_brl", 0) or 0)
        if not balance_set and bal > 0:
            kpis["balance_brl"] = bal
            balance_set = True

        kpis["receivables_30d_brl"] += float(d.get("receivables_brl", 0) or 0)
        kpis["payables_30d_brl"] += float(d.get("payables_brl", 0) or 0)
        kpis["overdue_total_brl"] += float(d.get("overdue_total_brl", 0) or 0)
        kpis["pipeline_weighted_brl"] += float(d.get("pipeline_weighted_brl", 0) or 0)
        kpis["ecommerce_revenue_month_brl"] += float(d.get("ecommerce_revenue_month_brl", 0) or 0)

        if not pipeline_set and isinstance(d.get("pipeline_by_stage"), list) and d["pipeline_by_stage"]:
            pipeline_by_stage = d["pipeline_by_stage"]
            pipeline_set = True

        if not erp_set and isinstance(d.get("cash_projection_90d"), list) and d["cash_projection_90d"]:
            cash_projection_90d = d["cash_projection_90d"]
            top_debtors = d.get("top_debtors", []) or []
            erp_set = True

    snapshot = {
        "as_of": now_iso(),
        "kpis": kpis,
        "pipeline_by_stage": pipeline_by_stage,
        "cash_projection_90d": cash_projection_90d,
        "top_debtors": top_debtors,
        "integrations_health": integrations_health,
    }

    log(f"Snapshot agregado: balance={kpis['balance_brl']}, receivables={kpis['receivables_30d_brl']}, overdue={kpis['overdue_total_brl']}")

    # ── Gera insights via LLM (Marcos) ───────────────────────────────────
    prompt = f"""Você é Marcos, CFO IA. Analise esses números e gere até 8 insights curtos (uma frase cada, máximo 120 chars).

DADOS:
{json.dumps(snapshot, indent=2, default=str)}

Foque em:
- Saúde do caixa
- Recebíveis críticos
- Pipeline em risco
- Concentração / inadimplência
- Tendência vs mês passado

Para cada insight, retorne EXATAMENTE neste formato JSON (array):
[{{"section": "balance|pipeline|overdue|integrations", "text": "frase curta", "severity": "info|warn|critical"}}]"""

    log("Enviando prompt para LLM via hooks/agent...")

    try:
        payload = json.dumps({
            "message": prompt,
            "name": "InsightDaemon",
            "deliver": False,
            "timeoutSeconds": 60,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{hooks_url}/hooks/agent",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {hooks_token}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=90) as resp:
            llm_response = resp.read().decode("utf-8", errors="replace")

        log(f"LLM response length: {len(llm_response)} chars")
    except Exception as e:
        log(f"ERRO ao chamar LLM: {e}")
        return

    # ── Extrai JSON do response ──────────────────────────────────────────
    insights: list[dict] = []
    try:
        # Tenta parsear direto
        insights = json.loads(llm_response)
    except (json.JSONDecodeError, TypeError):
        # Busca por "[{" no texto
        match = re.search(r'\[\s*\{', llm_response)
        if match:
            start = match.start()
            # Busca o "]" correspondente
            bracket_count = 0
            end = start
            for i in range(start, len(llm_response)):
                if llm_response[i] == '[':
                    bracket_count += 1
                elif llm_response[i] == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end = i + 1
                        break
            try:
                insights = json.loads(llm_response[start:end])
            except (json.JSONDecodeError, TypeError):
                log("ERRO: não conseguiu parsear JSON de insights do LLM.")
                return

    if not isinstance(insights, list) or len(insights) == 0:
        log("AVISO: LLM retornou 0 insights.")
        return

    # Valida formato
    valid_insights = []
    valid_sections = {"balance", "pipeline", "overdue", "integrations"}
    valid_severities = {"info", "warn", "critical"}
    for item in insights:
        if (
            isinstance(item, dict)
            and item.get("section") in valid_sections
            and item.get("text")
            and item.get("severity") in valid_severities
        ):
            valid_insights.append({
                "section": item["section"],
                "text": str(item["text"])[:120],
                "severity": item["severity"],
            })

    if not valid_insights:
        log("AVISO: nenhum insight válido após filtragem.")
        return

    log(f"Publicando {len(valid_insights)} insights no painel...")

    # ── Publica insights ─────────────────────────────────────────────────
    try:
        pub_payload = json.dumps(valid_insights).encode("utf-8")
        pub_req = urllib.request.Request(
            f"{panel_base_url}/dashboard-publish-insights",
            data=pub_payload,
            headers={
                "Content-Type": "application/json",
                "X-Panel-Token": panel_token,
            },
            method="POST",
        )

        with urllib.request.urlopen(pub_req, timeout=30) as resp:
            pub_response = resp.read().decode("utf-8", errors="replace")

        log(f"Insights publicados: {pub_response}")
    except Exception as e:
        log(f"ERRO ao publicar insights: {e}")
        return

    log("Ciclo concluído com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[{now_iso()}] FATAL: {e}", flush=True)
    sys.exit(0)
