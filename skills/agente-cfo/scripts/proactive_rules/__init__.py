"""
proactive_rules — Interface e dataclass compartilhados pelas regras de detecção.

Cada regra:
  - Herda ProactiveRule
  - Implementa evaluate(erp_client, crm_client, state) -> list[Alert]
  - Declara name (str) e cooldown_hours (int)

Alert.dedup_key é a chave de cooldown por item. Exemplo:
  "overdue:omie_pay_4882"  — uma conta específica
  "cash_low:global"        — alerta global de caixa
  "concentration:acme"     — um cliente específico
"""
from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Any


@dataclass
class Alert:
    rule_name: str
    severity: str        # "info" | "warn" | "critical"
    summary: str         # 1-2 frases — o agente formata em português no prompt
    raw_data: dict = field(default_factory=dict)   # contas/deals/valores envolvidos
    dedup_key: str = ""  # ex: "overdue:pay_4882" — chave de cooldown por item


class ProactiveRule(ABC):
    name: str = ""
    cooldown_hours: int = 24

    @abstractmethod
    def evaluate(
        self,
        erp_client: Any | None,
        crm_client: Any | None,
        state: dict,
    ) -> list[Alert]:
        """
        Avalia a regra e retorna lista de alertas detectados.

        - erp_client: instância de BaseERPClient (ou None se ERP indisponível)
        - crm_client: instância de BaseCRMClient (ou None se CRM não configurado)
        - state: dict com histórico de alertas já enviados (para contexto extra)

        Regras que dependem do CRM devem checar `if crm_client is None: return []`.
        Regras que dependem de comandos não suportados pelo ERP devem tratar
        NotImplementedError/RuntimeError e retornar [] silenciosamente (skip+log).
        """
        ...
