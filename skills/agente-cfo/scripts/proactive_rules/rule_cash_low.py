"""
rule_cash_low — Caixa projetado (7, 30 e 90 dias) abaixo dos thresholds.

Severity: warn  (critical se < 50% do threshold)
Cooldown: 24h (global) para horizonte de 7 dias
          48h para 30 dias / 168h para 90 dias
Dependência: ERP

Lógica (Sprint 7 — usa get_cash_projection quando disponível):
  1. Tenta get_cash_projection(days=30) — usa breakdown semanal completo
  2. Fallback: list_receivables + list_payables para os horizonte de 7 dias

Thresholds configuráveis por horizonte:
  CFO_CASH_LOW_THRESHOLD_BRL       — threshold para janela 7 dias (sobreescreve heurística)
  CFO_CASH_LOW_THRESHOLD_30D_BRL   — threshold para janela 30 dias
  CFO_CASH_LOW_THRESHOLD_90D_BRL   — threshold para janela 90 dias
  CFO_CASH_THRESHOLD_MULTIPLIER    — multiplicador sobre LLM_BUDGET_BRL (default: 5 / 7d)

Threshold automático (7d):
  Quando CFO_CASH_LOW_THRESHOLD_BRL não está definido, calcula automaticamente
  15% da média mensal de saídas dos últimos 90 dias via list_payables.
  Fallback para LLM_BUDGET_BRL × 5 se a API falhar ou dados forem insuficientes.
"""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from . import ProactiveRule, Alert

logger = logging.getLogger(__name__)


def _auto_threshold_from_burn(erp_client) -> float | None:
    """
    Calcula threshold automático = 15% da média mensal de saídas dos últimos 90 dias.
    Retorna None se não for possível calcular (API falha, dados insuficientes).
    """
    try:
        today = date.today()
        since_90d = (today - timedelta(days=90)).isoformat()
        today_str = today.isoformat()
        payables_resp = erp_client.list_payables(from_date=since_90d, to_date=today_str, limit=500)
        items = payables_resp.get("items", [])
        if not items:
            logger.warning("rule_cash_low: list_payables retornou 0 itens para os últimos 90 dias — usando fallback de threshold")
            return None
        total_outgoing = sum(float(i.get("amount_brl", 0.0)) for i in items)
        monthly_avg = total_outgoing / 3.0  # 90 dias ≈ 3 meses
        threshold = monthly_avg * 0.15
        logger.info(f"rule_cash_low: threshold automático calculado = R$ {threshold:,.2f} (burn médio mensal R$ {monthly_avg:,.2f})")
        return threshold
    except Exception as e:
        logger.warning(f"rule_cash_low: não foi possível calcular threshold automático via burn: {e}")
        return None


def _cash_threshold(horizon: str = "7d", erp_client=None) -> float:
    """Retorna threshold para o horizonte especificado (7d, 30d, 90d).

    Para janela de 7 dias: se CFO_CASH_LOW_THRESHOLD_BRL não estiver setado,
    tenta calcular automaticamente via burn histórico (últimos 90 dias).
    """
    env_keys = {
        "7d":  ("CFO_CASH_LOW_THRESHOLD_BRL",     "CFO_CASH_THRESHOLD_MULTIPLIER",  5),
        "30d": ("CFO_CASH_LOW_THRESHOLD_30D_BRL",  "CFO_CASH_THRESHOLD_MULTIPLIER", 15),
        "90d": ("CFO_CASH_LOW_THRESHOLD_90D_BRL",  "CFO_CASH_THRESHOLD_MULTIPLIER", 40),
    }
    override_key, mult_key, default_mult = env_keys.get(horizon, env_keys["7d"])
    override = os.environ.get(override_key)
    if override:
        try:
            return float(override)
        except ValueError:
            pass

    # Para horizonte 7d: tenta calcular via burn histórico
    if horizon == "7d" and erp_client is not None:
        auto = _auto_threshold_from_burn(erp_client)
        if auto is not None:
            return auto
        logger.warning(
            "rule_cash_low: threshold automático indisponível — usando fallback LLM_BUDGET_BRL × %d. "
            "Defina CFO_CASH_LOW_THRESHOLD_BRL para um valor adequado ao seu burn.",
            default_mult,
        )

    budget = float(os.environ.get("LLM_BUDGET_BRL", "50"))
    multiplier = float(os.environ.get(mult_key, str(default_mult)))
    return budget * multiplier


class RuleCashLow(ProactiveRule):
    name = "rule_cash_low"
    cooldown_hours = 24

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        if erp_client is None:
            return []

        alerts: list[Alert] = []

        # ── Tenta usar get_cash_projection (Sprint 7) para 30 e 90 dias ─────────
        projection_30 = None
        projection_90 = None
        try:
            projection_30 = erp_client.get_cash_projection(days=30)
        except (NotImplementedError, AttributeError):
            pass
        except Exception:
            pass

        try:
            projection_90 = erp_client.get_cash_projection(days=90)
        except (NotImplementedError, AttributeError):
            pass
        except Exception:
            pass

        # ── Horizonte 30 dias ────────────────────────────────────────────────────
        if projection_30 is not None:
            balance = float(projection_30.get("balance_brl", 0.0))
            incoming_30 = float(projection_30.get("incoming_brl", 0.0))
            outgoing_30 = float(projection_30.get("outgoing_brl", 0.0))
            projected_30 = float(projection_30.get("projected_balance_brl", balance + incoming_30 - outgoing_30))
            threshold_30 = _cash_threshold("30d")

            if projected_30 < threshold_30:
                severity = "critical" if projected_30 < threshold_30 * 0.5 else "warn"

                # Semanas com saldo negativo
                negative_weeks = [
                    w for w in projection_30.get("by_week", []) if w.get("net_brl", 0) < 0
                ]
                neg_hint = ""
                if negative_weeks:
                    neg_hint = (
                        f" Semanas com fluxo negativo: "
                        + ", ".join(f"Sem.{w['week']} ({w['from'][5:]}): R$ {w['net_brl']:,.0f}" for w in negative_weeks[:3])
                        + "."
                    )

                summary = (
                    f"Caixa projetado em 30 dias: R$ {projected_30:,.2f} "
                    f"(threshold R$ {threshold_30:,.2f}).{neg_hint} "
                    f"Saldo: R$ {balance:,.2f} | +R$ {incoming_30:,.2f} | -R$ {outgoing_30:,.2f}."
                )
                alerts.append(Alert(
                    rule_name=self.name,
                    severity=severity,
                    summary=summary,
                    raw_data={
                        "horizon": "30d",
                        "balance_brl": round(balance, 2),
                        "incoming_brl": round(incoming_30, 2),
                        "outgoing_brl": round(outgoing_30, 2),
                        "projected_brl": round(projected_30, 2),
                        "threshold_brl": round(threshold_30, 2),
                        "by_week": projection_30.get("by_week", []),
                    },
                    dedup_key="cash_low:30d",
                ))

        # ── Horizonte 90 dias ────────────────────────────────────────────────────
        if projection_90 is not None:
            balance = float(projection_90.get("balance_brl", 0.0))
            incoming_90 = float(projection_90.get("incoming_brl", 0.0))
            outgoing_90 = float(projection_90.get("outgoing_brl", 0.0))
            projected_90 = float(projection_90.get("projected_balance_brl", balance + incoming_90 - outgoing_90))
            threshold_90 = _cash_threshold("90d")

            if projected_90 < threshold_90:
                severity = "critical" if projected_90 < threshold_90 * 0.5 else "warn"
                summary = (
                    f"Caixa projetado em 90 dias: R$ {projected_90:,.2f} "
                    f"(threshold R$ {threshold_90:,.2f}). "
                    f"Saldo: R$ {balance:,.2f} | +R$ {incoming_90:,.2f} | -R$ {outgoing_90:,.2f}."
                )
                alerts.append(Alert(
                    rule_name=self.name,
                    severity=severity,
                    summary=summary,
                    raw_data={
                        "horizon": "90d",
                        "balance_brl": round(balance, 2),
                        "incoming_brl": round(incoming_90, 2),
                        "outgoing_brl": round(outgoing_90, 2),
                        "projected_brl": round(projected_90, 2),
                        "threshold_brl": round(threshold_90, 2),
                    },
                    dedup_key="cash_low:90d",
                ))

        # ── Horizonte 7 dias (fallback sempre executado) ─────────────────────────
        today = date.today()
        in_7_days = (today + timedelta(days=7)).isoformat()
        today_str = today.isoformat()

        try:
            balance_resp = erp_client.get_balance()
        except NotImplementedError:
            return alerts  # ERP não suporta get_balance — skip silencioso
        except Exception as e:
            logger.warning(f"rule_cash_low: falha ao obter saldo: {e}")
            return alerts  # não conseguiu nem o saldo — retorna o que tiver

        balance = float(balance_resp.get("balance_brl", 0.0))

        try:
            receivables_resp = erp_client.list_receivables(
                from_date=today_str, to_date=in_7_days, limit=200
            )
            incoming = sum(
                float(i.get("amount_brl", 0.0))
                for i in receivables_resp.get("items", [])
                if i.get("status") in ("pending", "overdue")
            )
        except (NotImplementedError, Exception):
            incoming = 0.0

        try:
            payables_resp = erp_client.list_payables(
                from_date=today_str, to_date=in_7_days, limit=200
            )
            outgoing = sum(
                float(i.get("amount_brl", 0.0))
                for i in payables_resp.get("items", [])
                if i.get("status") in ("pending", "overdue")
            )
            upcoming_bills = sorted(
                [
                    i for i in payables_resp.get("items", [])
                    if i.get("status") in ("pending", "overdue")
                ],
                key=lambda x: x.get("due_date", ""),
            )[:3]
        except (NotImplementedError, Exception):
            outgoing = 0.0
            upcoming_bills = []

        projected = balance + incoming - outgoing
        threshold = _cash_threshold("7d", erp_client=erp_client)

        if projected < threshold:
            severity = "critical" if projected < threshold * 0.5 else "warn"

            bills_str = ""
            if upcoming_bills:
                parts = [
                    f"{b.get('counterparty','?')} R$ {float(b.get('amount_brl',0)):,.0f} ({b.get('due_date','')})"
                    for b in upcoming_bills[:2]
                ]
                bills_str = f" Principais vencimentos: {'; '.join(parts)}."

            summary = (
                f"Caixa projetado em 7 dias: R$ {projected:,.2f} "
                f"(threshold R$ {threshold:,.2f}).{bills_str} "
                f"Saldo atual: R$ {balance:,.2f} | "
                f"+recebimentos: R$ {incoming:,.2f} | "
                f"-pagamentos: R$ {outgoing:,.2f}."
            )

            alerts.append(Alert(
                rule_name=self.name,
                severity=severity,
                summary=summary,
                raw_data={
                    "horizon": "7d",
                    "balance_brl": balance,
                    "incoming_7d_brl": round(incoming, 2),
                    "outgoing_7d_brl": round(outgoing, 2),
                    "projected_brl": round(projected, 2),
                    "threshold_brl": round(threshold, 2),
                    "upcoming_bills": upcoming_bills[:5],
                },
                dedup_key="cash_low:global",
            ))

        return alerts
