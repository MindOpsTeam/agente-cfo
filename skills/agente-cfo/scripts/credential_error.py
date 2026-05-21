"""
credential_error.py — Detecção e formatação de erros de credencial nos gateways.

Detecta erros de autenticação a partir de:
  - stdout JSON com "error" contendo "401", "unauthorized", "invalid token", etc.
  - returncode != 0 com mensagem de 401 no stderr/stdout
  - MISSING_SCOPES específico do HubSpot

Retorna dicts estruturados com:
  error_kind: "credential_invalid" | "scopes_missing" | None
  skill, http_status, fix_url, message_pt, required_scopes (se aplicável)
"""
import re

# Painel base URL do painel (fallback hardcoded — lê do env se disponível)
import os
_PANEL_BASE = os.environ.get("PANEL_BASE_URL", "").rstrip("/")
_PANEL_ORIGIN = re.sub(r"/functions/v1.*", "", _PANEL_BASE) if _PANEL_BASE else "[painel]"

# Padrões que indicam credencial inválida
_CRED_PATTERNS = [
    r"\b401\b",
    r"unauthorized",
    r"invalid.{0,20}(token|key|secret|credential|api.?key)",
    r"(token|key|credential).{0,20}inv[aá]lid",
    r"auth.{0,10}fail",
    r"access.{0,10}denied",
    r"permission.{0,10}denied",
    r"403.*forbidden",
    r"not authorized",
    r"authentication.{0,10}(fail|error|required)",
    r"invalid_api_key",
    r"apikey.*invalid",
    r"app_key.*inv",          # Omie specific
    r"app_secret.*inv",       # Omie specific
    r"HTTP 401",
    r"HTTP 403",
    r"http_status.*401",
    r"\"status\".*401",
]

# Padrões de escopos faltando
_SCOPE_PATTERNS = [
    r"missing.{0,20}scope",
    r"scope.{0,20}missing",
    r"MISSING_SCOPES",
    r"insufficient.{0,20}(scope|permission)",
    r"required.{0,20}scope",
]

# Mensagens localizadas por skill
_MSG_PT: dict[str, str] = {
    "asaas":       "Credencial Asaas inválida (HTTP 401). Atualize a API Key em {fix_url} e me chame de novo.",
    "iugu":        "Token Iugu inválido (HTTP 401). Atualize em {fix_url} e tente novamente.",
    "omie":        "Credenciais Omie inválidas (HTTP 401). Verifique App Key e App Secret em {fix_url}.",
    "bling":       "Token Bling expirado ou inválido. Reautorize em {fix_url}.",
    "contaazul":   "Token ContaAzul expirado. Reautorize em {fix_url}.",
    "granatum":    "API Key Granatum inválida. Atualize em {fix_url}.",
    "vhsys":       "Tokens VHSYS inválidos. Atualize em {fix_url}.",
    "nibo":        "API Token Nibo inválido. Atualize em {fix_url}.",
    "tiny":        "Token Tiny inválido. Atualize em {fix_url}.",
    "hubspot":     "Token HubSpot inválido (HTTP 401). Reautorize em {fix_url}.",
    "rd-station":  "API Key RD Station inválida. Atualize em {fix_url}.",
    "piperun":     "Token PipeRun inválido. Atualize em {fix_url}.",
    "pipedrive":   "API Token Pipedrive inválido. Atualize em {fix_url}.",
    "kommo":       "Access Token Kommo inválido ou expirado. Atualize em {fix_url}.",
    "mercado-livre": "Token Mercado Livre expirado. Reautorize em {fix_url}.",
    "nuvemshop":   "Token Nuvemshop expirado. Reautorize em {fix_url}.",
}

_SCOPE_MSG_PT: dict[str, str] = {
    "hubspot": (
        "Token HubSpot não tem os escopos necessários para esta operação. "
        "Adicione os escopos em: {fix_url} "
        "(Settings → Integrations → Private Apps → edite o app → Scopes)."
    ),
}


def _matches(text: str, patterns: list[str]) -> bool:
    t = text.lower()
    return any(re.search(p, t, re.IGNORECASE) for p in patterns)


def detect_credential_error(
    skill_name: str,
    stdout: str,
    stderr: str,
    returncode: int,
    required_scopes: list[str] | None = None,
) -> dict | None:
    """
    Analisa stdout/stderr de um subprocess de client ERP/CRM/cobrança.
    Retorna None se não houver erro de credencial.
    Retorna dict com error_kind estruturado se houver.
    """
    combined = f"{stdout} {stderr}"
    fix_url = f"{_PANEL_ORIGIN}/integrations/{skill_name}"

    # MISSING_SCOPES (HubSpot específico, mas detecta pra qualquer skill)
    if _matches(combined, _SCOPE_PATTERNS):
        msg_tpl = _SCOPE_MSG_PT.get(skill_name,
            f"Token {skill_name} não tem os escopos necessários. Adicione em {{fix_url}}.")
        return {
            "success": False,
            "error_kind": "scopes_missing",
            "skill": skill_name,
            "required_scopes": required_scopes or [],
            "fix_url": fix_url,
            "message_pt": msg_tpl.format(fix_url=fix_url),
        }

    # Credencial inválida (401 / auth errors)
    if _matches(combined, _CRED_PATTERNS):
        # Extrai http_status se possível
        http_status = 401
        m = re.search(r"HTTP (\d{3})", combined, re.IGNORECASE)
        if m:
            http_status = int(m.group(1))

        msg_tpl = _MSG_PT.get(skill_name,
            f"Credencial {skill_name} inválida (HTTP {http_status}). "
            f"Atualize em {{fix_url}} e tente novamente.")
        return {
            "success": False,
            "error_kind": "credential_invalid",
            "skill": skill_name,
            "http_status": http_status,
            "fix_url": fix_url,
            "message_pt": msg_tpl.format(fix_url=fix_url),
        }

    return None


def wrap_subprocess_result(
    skill_name: str,
    result,  # subprocess.CompletedProcess
    required_scopes: list[str] | None = None,
) -> dict | None:
    """
    Wrapper conveniente: recebe CompletedProcess e retorna erro estruturado ou None.
    """
    return detect_credential_error(
        skill_name=skill_name,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
        returncode=result.returncode,
        required_scopes=required_scopes,
    )
