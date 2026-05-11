"""Automation Actions — interface e registry para o Automation Engine."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

# Mapeamento type -> classe (preenchido pelos módulos ao importar)
ACTION_REGISTRY: dict[str, type["Action"]] = {}


class Action(ABC):
    type: str = ""
    require_confirmation_default: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.type:
            ACTION_REGISTRY[cls.type] = cls

    @abstractmethod
    def execute(self, spec: dict, run_context: dict) -> dict:
        """
        Executa a ação.
        run_context: {user_id, automation_id, run_id, env: dict, scripts_dir: str}
        Retorna: {"success": bool, "output": dict, "error": str|None}
        """
        ...


def load_all():
    """Importa todos os módulos de ação para popular o registry."""
    from . import (send_report, send_whatsapp, crm_update_deal,
                   crm_create_task, erp_create_invoice, cobranca_send,
                   ai_decide)
