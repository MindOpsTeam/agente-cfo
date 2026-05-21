#!/usr/bin/env python3
"""
ERP Gateway — ponto de entrada genérico para qualquer skill ERP.
Uso: python3 erp_gateway.py <command> [args...]
Lê CFO_ERP_NAME do .env, instancia o client correto, executa o comando.

Comandos suportados (via BaseERPClient):
  get_balance
  list_receivables [--from DATE] [--to DATE] [--limit N] [--page N]
  list_payables    [--from DATE] [--to DATE] [--limit N] [--page N]
  list_overdue
  get_cash_projection [--days N]
  company_info
  pay_payable      --id ID
  mark_received    --id ID
  create_payable   --amount N --due_date DATE --supplier NAME [--category C]
                   [--thread_id T] [--run_id R] [--channel C]
  create_receivable --amount N --due_date DATE --customer NAME [--category C]
                   [--thread_id T] [--run_id R] [--channel C]
  cancel_payable   --id ID
  update_category  --id ID --category C [--record_type payable|receivable]

  snapshot_kpis    — agrega KPIs do ERP num único JSON (para dashboard-snapshot)
    Output: {"balance": N, "payables_30d": N, "receivables_30d": N,
             "overdue_total": N, "erp": "omie", "as_of": "<ISO>"}
    Em caso de erro parcial: valores afetados ficam 0.0, campo "erp_error" presente.

AUTO-FALLBACK (create_payable / create_receivable):
  Se o ERP retornar erro (qualquer {error:...} ou returncode != 0), o gateway:
    1. Chama panel_write_event.sh com erp="dashboard_only", status="success"
    2. Retorna JSON: {"success": true, "fallback": "dashboard_only",
                     "panel_id": "<uuid>", "erp_error": "<msg>"}
  Isso garante atomicidade: Marcos não precisa de um 2º turn para tratar falha.
  Exit 0 em ambos os casos (ERP success ou fallback).
  Os args --thread_id / --run_id / --channel são opcionais mas recomendados:
  sem eles, panel_write_event.sh usa valores vazios (painel pode não atualizar).
"""
import os
import sys
import subprocess
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
from credential_error import wrap_subprocess_result  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────

WRITE_COMMANDS = {"create_payable", "create_receivable"}
AGGREGATE_COMMANDS = {"snapshot_kpis"}
WRITE_EVENT_SCRIPT = Path(__file__).parent / "panel_write_event.sh"

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_env():
    env_file = os.path.expanduser("~/.agente-cfo/.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())


def parse_write_args(argv: list[str]) -> dict:
    """Extrai --amount, --supplier/--customer, --due_date, --category,
    --thread_id, --run_id, --channel dos args da linha de comando."""
    result: dict[str, str] = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--") and i + 1 < len(argv):
            key = arg[2:]
            result[key] = argv[i + 1]
            i += 2
        else:
            i += 1
    return result


def call_panel_write_event(
    action: str,
    erp: str,
    erp_record_id: str,
    parsed: dict,
    status: str = "success",
    erp_error: str = "",
) -> str:
    """Chama panel_write_event.sh e retorna o stdout (OK:<id> ou DUPLICATE:<id>)."""
    if not WRITE_EVENT_SCRIPT.exists():
        return ""

    supplier = parsed.get("supplier") or parsed.get("customer") or ""
    cmd = [
        "bash", str(WRITE_EVENT_SCRIPT),
        "--action",     action,
        "--erp",        erp,
        "--channel",    parsed.get("channel", ""),
        "--thread_id",  parsed.get("thread_id", ""),
        "--status",     status,
    ]
    if erp_record_id:
        cmd += ["--erp_record_id", erp_record_id]
    if parsed.get("amount"):
        cmd += ["--amount", parsed["amount"]]
    if supplier:
        cmd += ["--supplier_or_customer", supplier]
    if parsed.get("due_date"):
        cmd += ["--due_date", parsed["due_date"]]
    if parsed.get("category"):
        cmd += ["--category", parsed["category"]]
    if parsed.get("run_id"):
        cmd += ["--run_id", parsed["run_id"]]
    if erp_error:
        cmd += ["--error", erp_error[:300]]  # trunca pra não explodir o payload

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return r.stdout.strip()
    except Exception as e:
        return f"WARN: panel_write_event falhou: {e}"


def extract_panel_id(pwe_output: str) -> str:
    """Extrai o UUID de 'OK: <uuid>' ou 'DUPLICATE: <uuid>'."""
    if not pwe_output:
        return ""
    parts = pwe_output.split(":", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return ""


def extract_erp_error(raw_stdout: str, returncode: int) -> str:
    """Tenta extrair mensagem de erro do JSON retornado pelo ERP client."""
    if raw_stdout.strip():
        try:
            d = json.loads(raw_stdout)
            if isinstance(d, dict):
                return str(d.get("error") or d.get("message") or d.get("faultstring") or "")
        except json.JSONDecodeError:
            pass
    if returncode != 0:
        return f"ERP returncode={returncode}"
    return ""


# ── snapshot_kpis ─────────────────────────────────────────────────────────────

def _run_client(client_script: str, subcommand: str, extra_args: list) -> dict:
    """Executa um subcommand do ERP client e retorna dict JSON ou {"error": ...}."""
    result = subprocess.run(
        ["python3", client_script, subcommand] + extra_args,
        capture_output=True, text=True, timeout=30,
    )
    raw = result.stdout.strip()
    if not raw:
        return {"error": f"{subcommand}: saída vazia (rc={result.returncode})"}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": f"{subcommand}: JSON inválido: {raw[:120]}"}


def _sum_amounts(data) -> float:  # dict | list — Python 3.9 compat
    """Soma o campo de valor de uma lista de registros retornada pelo ERP client."""
    items: list = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("items", "payables", "receivables", "lancamentos", "titulos", "data", "records"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        # Resposta já é o total direto (get_balance-style)
        if not items:
            for key in ("balance", "total", "amount", "value", "saldo"):
                if key in data:
                    try:
                        return float(data[key])
                    except (TypeError, ValueError):
                        pass

    total = 0.0
    for item in items:
        for key in ("nValorTitulo", "nValorLancamento", "valor", "amount",
                    "value", "nValor", "nSaldo", "total"):
            if key in item:
                try:
                    total += float(item[key])
                    break
                except (TypeError, ValueError):
                    pass
    return total


def cmd_snapshot_kpis(erp_name: str, client_script: str) -> dict:
    """
    Agrega balance + payables_30d + receivables_30d + overdue_total num único JSON.
    Falhas parciais resultam em 0.0 para o campo afetado + erp_error no output.
    Exit 0 sempre (dashboard-snapshot não deve falhar por ERP indisponível).
    """
    today = datetime.now(timezone.utc).date()
    in_30d = (today + timedelta(days=30)).isoformat()
    today_iso = today.isoformat()

    result: dict = {
        "balance": 0.0,
        "payables_30d": 0.0,
        "receivables_30d": 0.0,
        "overdue_total": 0.0,
        "erp": erp_name,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    errors: list[str] = []

    # 1. Balance
    bal_data = _run_client(client_script, "get_balance", [])
    if "error" in bal_data:
        errors.append(f"get_balance: {bal_data['error']}")
    else:
        result["balance"] = _sum_amounts(bal_data)

    # 2. Payables (próximos 30 dias)
    pay_data = _run_client(client_script, "list_payables",
                           ["--from", today_iso, "--to", in_30d, "--limit", "200"])
    if "error" in pay_data:
        errors.append(f"list_payables: {pay_data['error']}")
    else:
        result["payables_30d"] = _sum_amounts(pay_data)

    # 3. Receivables (próximos 30 dias)
    rec_data = _run_client(client_script, "list_receivables",
                           ["--from", today_iso, "--to", in_30d, "--limit", "200"])
    if "error" in rec_data:
        errors.append(f"list_receivables: {rec_data['error']}")
    else:
        result["receivables_30d"] = _sum_amounts(rec_data)

    # 4. Overdue total
    ovd_data = _run_client(client_script, "list_overdue", [])
    if "error" in ovd_data:
        errors.append(f"list_overdue: {ovd_data['error']}")
    else:
        result["overdue_total"] = _sum_amounts(ovd_data)

    if errors:
        result["erp_error"] = "; ".join(errors)

    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    load_env()

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Nenhum comando fornecido"}))
        sys.exit(1)

    command = sys.argv[1]

    erp_name = os.environ.get("CFO_ERP_NAME", "omie")
    erp_slug  = erp_name.replace("-", "_")
    skill_base   = os.path.expanduser(f"~/.openclaw/workspace/skills/{erp_name}")
    client_script = os.path.join(skill_base, "scripts", f"{erp_slug}_client.py")

    if not os.path.exists(client_script):
        print(json.dumps({"error": f"Skill '{erp_name}' nao encontrada em {client_script}"}))
        sys.exit(1)

    # ── Comandos de WRITE com fallback atômico ────────────────────────────────
    if command in WRITE_COMMANDS:
        parsed = parse_write_args(sys.argv[2:])

        # Filtra args do gateway antes de passar pro client
        # (client não conhece --thread_id / --run_id / --channel)
        gateway_only = {"thread_id", "run_id", "channel"}
        client_args = []
        argv_tail = sys.argv[2:]
        i = 0
        while i < len(argv_tail):
            arg = argv_tail[i]
            if arg.startswith("--") and arg[2:] in gateway_only:
                i += 2  # pula flag + valor
            else:
                client_args.append(arg)
                i += 1

        result = subprocess.run(
            ["python3", client_script, command] + client_args,
            capture_output=True,
            text=True,
        )

        # ── Credencial inválida (detecção imediata, antes de fallback) ────────
        cred_err = wrap_subprocess_result(erp_name, result)
        if cred_err and cred_err.get("error_kind") in ("credential_invalid", "scopes_missing"):
            print(json.dumps(cred_err, ensure_ascii=False))
            sys.exit(0)  # Marcos lê message_pt e responde ao user

        # Avalia se o ERP teve sucesso
        erp_ok = False
        erp_record_id = ""
        erp_error_msg = ""

        if result.returncode == 0 and result.stdout.strip():
            try:
                resp = json.loads(result.stdout)
                if isinstance(resp, dict) and not resp.get("error") and not resp.get("faultstring"):
                    erp_ok = True
                    erp_record_id = str(resp.get("id") or resp.get("record_id") or resp.get("codigo") or "")
                else:
                    erp_error_msg = str(resp.get("error") or resp.get("faultstring") or resp.get("message") or "ERP retornou erro")
            except json.JSONDecodeError:
                # stdout não-JSON = erro inesperado
                erp_error_msg = result.stdout.strip()[:300]
        else:
            erp_error_msg = extract_erp_error(result.stdout + result.stderr, result.returncode)

        if erp_ok:
            # ── Sucesso no ERP → registra normalmente ────────────────────────
            pwe_out = call_panel_write_event(
                action=command,
                erp=erp_name,
                erp_record_id=erp_record_id,
                parsed=parsed,
                status="success",
            )
            panel_id = extract_panel_id(pwe_out)
            output = {"success": True, "fallback": None,
                      "erp_record_id": erp_record_id, "panel_id": panel_id}
            print(json.dumps(output))
            sys.exit(0)
        else:
            # ── Falha no ERP → fallback dashboard_only atômico ──────────────
            pwe_out = call_panel_write_event(
                action=command,
                erp="dashboard_only",
                erp_record_id="",
                parsed=parsed,
                status="success",    # o REGISTRO no painel é sucesso
                erp_error=erp_error_msg,
            )
            panel_id = extract_panel_id(pwe_out)
            output = {
                "success":     True,
                "fallback":    "dashboard_only",
                "panel_id":    panel_id,
                "erp_error":   erp_error_msg,
            }
            print(json.dumps(output))
            sys.exit(0)   # ← sempre 0: Marcos não precisa de recovery turn

    # ── snapshot_kpis: agregação de KPIs para dashboard-snapshot ─────────────
    if command in AGGREGATE_COMMANDS:
        kpis = cmd_snapshot_kpis(erp_name, client_script)
        # credential check: se o ERP retornou credential_invalid, propaga
        if kpis.get("erp_error"):
            # Tenta detectar erro de credencial no erp_error para propagar via wrap
            # (erp_error pode conter "credential_invalid" se o client usou wrap_subprocess_result)
            err_lower = kpis["erp_error"].lower()
            if any(k in err_lower for k in ("credential", "unauthorized", "401", "403", "invalid_key")):
                kpis["error_kind"] = "credential_invalid"
                kpis["message_pt"] = (
                    f"Credenciais do {erp_name} inválidas ou expiradas. "
                    "Configure as credenciais no painel e tente novamente."
                )
        print(json.dumps(kpis, ensure_ascii=False))
        sys.exit(0)  # sempre 0: dashboard não deve quebrar por ERP indisponível

    # ── Todos os outros comandos: proxy simples (com credential check) ────────
    result = subprocess.run(
        ["python3", client_script] + sys.argv[1:],
        capture_output=True,
        text=True,
    )
    # Verifica credencial antes de repassar stdout bruto
    cred_err = wrap_subprocess_result(erp_name, result)
    if cred_err and cred_err.get("error_kind") in ("credential_invalid", "scopes_missing"):
        print(json.dumps(cred_err, ensure_ascii=False))
        sys.exit(0)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
