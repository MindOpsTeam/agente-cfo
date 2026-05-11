#!/usr/bin/env python3
"""
migrate_rules_to_automations.py — Migra regras proativas para automações.

Cria automações equivalentes no Supabase para cada regra existente
em proactive_rules/. Idempotente: verifica flag no state antes de rodar.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reutiliza helpers do engine
sys.path.insert(0, str(Path(__file__).parent))
from cfo_automation_engine import load_env, load_state, save_state, supabase_request, log

# Mapeamento: rule_name → automação equivalente
RULE_AUTOMATIONS = [
    {
        "rule": "rule_cash_low",
        "name": "Alerta de caixa baixo",
        "description": "Alerta quando caixa projetado cai abaixo do threshold.",
        "trigger": {"type": "metric", "metric": "balance_brl", "operator": "lt", "value": 50000},
        "conditions": [],
        "actions": [
            {"type": "send_whatsapp", "to": "owner",
             "template": "\U0001f6a8 *Alerta CFO*: Caixa baixo detectado. Verifique o painel."},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": "cash_flow_alert",
    },
    {
        "rule": "rule_overdue_critical",
        "name": "Alerta inadimplência crítica",
        "description": "Todo dia às 10h, alerta sobre inadimplência crítica.",
        "trigger": {"type": "cron", "expression": "0 10 * * *"},
        "conditions": [],
        "actions": [
            {"type": "send_whatsapp", "to": "owner",
             "template": "\u26a0\ufe0f Inadimplência crítica detectada. Acesse o painel."},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_overdue_to_collect",
        "name": "Cobrança automática inadimplentes",
        "description": "Todo dia às 10h, sugere cobrança de inadimplentes.",
        "trigger": {"type": "cron", "expression": "0 10 * * *"},
        "conditions": [{"field": "overdue_days", "op": "gte", "value": 15}],
        "actions": [
            {"type": "cobranca_send", "customer_id": "{customer_id}",
             "message": "Olá! Identificamos uma pendência em seu cadastro. Por favor, regularize seu pagamento."},
        ],
        "require_confirmation": True,
        "active": False,
        "template_key": "auto_collect_overdue",
    },
    {
        "rule": "rule_concentration",
        "name": "Alerta concentração de receita",
        "description": "Toda segunda às 9h, alerta sobre concentração de receita.",
        "trigger": {"type": "cron", "expression": "0 9 * * 1"},
        "conditions": [],
        "actions": [
            {"type": "send_whatsapp", "to": "owner",
             "template": "\U0001f4ca Alerta de concentração de receita. Diversifique sua carteira de clientes."},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_deal_stale",
        "name": "Lembrete deals parados +7 dias",
        "description": "Toda terça às 9h, envia lista de deals sem atividade.",
        "trigger": {"type": "cron", "expression": "0 9 * * 2"},
        "conditions": [{"field": "days_without_activity", "op": "gte", "value": 7}],
        "actions": [
            {"type": "send_whatsapp", "to": "owner",
             "template": "\u26a0\ufe0f *Deals parados*: negócios sem atividade há mais de 7 dias."},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": "stale_deals_reminder",
    },
    {
        "rule": "rule_erp_api_health",
        "name": "Health check ERP/CRM",
        "description": "Todo dia às 8h, verifica saúde da API do ERP/CRM.",
        "trigger": {"type": "cron", "expression": "0 8 * * *"},
        "conditions": [],
        "actions": [
            {"type": "send_whatsapp", "to": "owner",
             "template": "\U0001f527 Health check ERP/CRM concluído. Verifique o painel para detalhes."},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_inadimplencia_high",
        "name": "Relatório de inadimplência alta",
        "description": "Todo dia às 10h, envia relatório de cobrança quando inadimplência está alta.",
        "trigger": {"type": "cron", "expression": "0 10 * * *"},
        "conditions": [],
        "actions": [
            {"type": "send_report", "report_type": "cobranca", "deliver_to": "owner"},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_low_stock",
        "name": "Alerta estoque baixo",
        "description": "Todo dia às 9h, alerta sobre produtos com estoque baixo.",
        "trigger": {"type": "cron", "expression": "0 9 * * *"},
        "conditions": [],
        "actions": [
            {"type": "send_whatsapp", "to": "owner",
             "template": "\U0001f4e6 Produtos com estoque baixo detectados. Verifique o painel."},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_pipeline_drop",
        "name": "Alerta queda no pipeline",
        "description": "Toda segunda às 9h, relatório de pipeline quando há queda.",
        "trigger": {"type": "cron", "expression": "0 9 * * 1"},
        "conditions": [],
        "actions": [
            {"type": "send_report", "report_type": "pipeline", "deliver_to": "owner"},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_pipeline_health",
        "name": "Relatório saúde do pipeline",
        "description": "Toda segunda às 9h, relatório de saúde do pipeline.",
        "trigger": {"type": "cron", "expression": "0 9 * * 1"},
        "conditions": [],
        "actions": [
            {"type": "send_report", "report_type": "pipeline", "deliver_to": "owner"},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_sales_drop",
        "name": "Alerta queda nas vendas",
        "description": "Toda segunda às 9h, relatório dashboard quando há queda nas vendas.",
        "trigger": {"type": "cron", "expression": "0 9 * * 1"},
        "conditions": [],
        "actions": [
            {"type": "send_report", "report_type": "dashboard", "deliver_to": "owner"},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
    {
        "rule": "rule_unfulfilled_orders",
        "name": "Alerta pedidos não enviados",
        "description": "Todo dia às 9h, alerta sobre pedidos não fulfillados.",
        "trigger": {"type": "cron", "expression": "0 9 * * *"},
        "conditions": [],
        "actions": [
            {"type": "send_whatsapp", "to": "owner",
             "template": "\U0001f4e6 Pedidos não fulfillados detectados. Verifique o painel."},
        ],
        "require_confirmation": False,
        "active": True,
        "template_key": None,
    },
]


def main():
    load_env()
    state = load_state()

    if state.get("proactive_rules_migrated"):
        log("Regras já foram migradas. Nada a fazer.")
        return

    # Busca user_id (usa o primeiro user do sistema — single tenant)
    users = supabase_request("GET", "auth/users", params={"limit": "1"})
    user_id = None
    if users and isinstance(users, list) and len(users) > 0:
        user_id = users[0].get("id")

    # Fallback: tenta via instances
    if not user_id:
        instances = supabase_request("GET", "instances", params={"select": "user_id", "limit": "1"})
        if instances and isinstance(instances, list) and len(instances) > 0:
            user_id = instances[0].get("user_id")

    created_count = 0

    for rule_def in RULE_AUTOMATIONS:
        rule_name = rule_def["rule"]

        # Verifica se já existe automação para essa rule
        existing = supabase_request(
            "GET", "automations",
            params={"template_key": f"eq.{rule_def.get('template_key', '')}"} if rule_def.get("template_key") else None,
        )

        record = {
            "name": rule_def["name"],
            "description": rule_def["description"],
            "trigger": rule_def["trigger"],
            "conditions": rule_def["conditions"],
            "actions": rule_def["actions"],
            "require_confirmation": rule_def["require_confirmation"],
            "active": rule_def["active"],
            "template_key": rule_def.get("template_key"),
        }
        if user_id:
            record["user_id"] = user_id

        result = supabase_request("POST", "automations", body=record)
        if result:
            created_count += 1
            log(f"Criada automação para {rule_name}: {rule_def['name']}")
        else:
            log(f"Falha ao criar automação para {rule_name}")

    state["proactive_rules_migrated"] = True
    state["migration_date"] = datetime.now(timezone.utc).isoformat()
    state["rules_migrated_count"] = created_count
    save_state(state)

    log(f"Migração concluída: {created_count} automações criadas de {len(RULE_AUTOMATIONS)} regras.")


if __name__ == "__main__":
    main()
