"""
rule_erp_api_health — Detecta falha persistente na API do ERP (credenciais expiradas,
quota excedida, serviço fora do ar).

Severity: warn (erro isolado), critical (N erros consecutivos)
Cooldown: 24h (global)
Dependência: ERP

Lógica:
  - Usa state["erp_errors"] para rastrear falhas consecutivas por ciclo
  - Se o erp_client foi passado como None (falhou na inicialização) → dispara
  - Se get_balance() lança RuntimeError com "HTTP 4" → credenciais inválidas
  - Se lança RuntimeError com "HTTP 5" → serviço fora do ar
  - ERP_ERRORS_CONSECUTIVE_THRESHOLD (default 2) erros em sequência → alerta
"""
from __future__ import annotations
import os
from . import ProactiveRule, Alert

ERRORS_THRESHOLD = int(os.environ.get("CFO_ERP_ERRORS_THRESHOLD", "2"))
ERP_ERRORS_STATE_KEY = "_erp_consecutive_errors"


class RuleERPApiHealth(ProactiveRule):
    name = "rule_erp_api_health"
    cooldown_hours = 24

    def evaluate(self, erp_client, crm_client, state) -> list[Alert]:
        erp_name = os.environ.get("CFO_ERP_NAME", "ERP")

        # Caso 1: erp_client não pôde ser instanciado (credenciais ausentes, etc.)
        if erp_client is None:
            return [Alert(
                rule_name=self.name,
                severity="critical",
                summary=(
                    f"Cliente {erp_name} não pôde ser inicializado — "
                    f"credenciais ausentes ou skill não instalada. "
                    f"Verifique as variáveis de ambiente no .env."
                ),
                raw_data={"erp_name": erp_name, "reason": "client_init_failed"},
                dedup_key="erp_health:init_failed",
            )]

        # Caso 2: testar get_balance() como ping
        error_msg = None
        try:
            erp_client.get_balance()
            # Sucesso — resetar contador de erros consecutivos no state
            state.pop(ERP_ERRORS_STATE_KEY, None)
            return []
        except NotImplementedError:
            # ERP não suporta get_balance — não é erro de API
            return []
        except RuntimeError as e:
            error_msg = str(e)
        except Exception as e:
            error_msg = str(e)

        # Incrementar erros consecutivos
        consecutive = state.get(ERP_ERRORS_STATE_KEY, 0) + 1
        state[ERP_ERRORS_STATE_KEY] = consecutive

        if consecutive < ERRORS_THRESHOLD:
            # Ainda abaixo do threshold — não alertar ainda
            return []

        # Determinar tipo de erro
        if "HTTP 4" in error_msg or "401" in error_msg or "403" in error_msg:
            severity = "critical"
            reason = "credenciais inválidas ou expiradas (HTTP 4xx)"
            hint = "Verifique OMIE_APP_KEY/OMIE_APP_SECRET (ou equivalente) no .env."
        elif "HTTP 5" in error_msg or "502" in error_msg or "503" in error_msg:
            severity = "warn"
            reason = f"serviço {erp_name} fora do ar (HTTP 5xx)"
            hint = "O ERP pode estar em manutenção. Tente novamente em alguns minutos."
        elif "attempt" in error_msg.lower() or "timeout" in error_msg.lower():
            severity = "warn"
            reason = "timeout na API — sem resposta"
            hint = "Verifique conectividade da VPS com a API do ERP."
        else:
            severity = "warn"
            reason = f"erro desconhecido: {error_msg[:80]}"
            hint = "Verifique os logs: ~/.agente-cfo/logs/proactive.log"

        summary = (
            f"API {erp_name} com falha ({consecutive} erros consecutivos): {reason}. "
            f"{hint}"
        )

        return [Alert(
            rule_name=self.name,
            severity=severity,
            summary=summary,
            raw_data={
                "erp_name": erp_name,
                "error": error_msg[:200],
                "consecutive_errors": consecutive,
                "reason": reason,
            },
            dedup_key=f"erp_health:{erp_name.lower()}",
        )]
