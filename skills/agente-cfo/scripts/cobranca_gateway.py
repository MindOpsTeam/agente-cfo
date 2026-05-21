#!/usr/bin/env python3
"""
Cobrança Gateway — ponto de entrada genérico para qualquer skill de cobrança.
Uso: python3 cobranca_gateway.py <command> [args...]
Lê CFO_COBRANCA_NAME do .env, instancia o client correto, executa o comando.

Comandos suportados (via BaseCobrancaClient):
  list_invoices [--status open|paid|overdue|cancelled|all] [--customer_id X] [--limit N] [--page N]
  get_invoice --id X
  get_customer --id X
  get_overdue_customers
  get_payment_methods
  company_info
  send_payment_link --invoice_id X [--channel whatsapp|email] [--custom_message "..."]
  mark_invoice_paid_manually --id X
  create_invoice --customer_id X --amount N --due_date DATE [--description "..."]
  cancel_invoice --id X
  send_reminder --customer_id X --message "..."
"""
import os
import sys
import subprocess
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from credential_error import wrap_subprocess_result


def main():
    env_file = os.path.expanduser("~/.agente-cfo/.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    cobranca_name = os.environ.get("CFO_COBRANCA_NAME", "nenhum")
    if not cobranca_name or cobranca_name == "nenhum":
        print(json.dumps({"error": "Nenhuma plataforma de cobrança configurada. "
                          "Defina CFO_COBRANCA_NAME no .env (asaas ou iugu)."}))
        sys.exit(1)

    client_filename = cobranca_name.replace("-", "_") + "_client.py"
    skill_base = os.path.expanduser(f"~/.openclaw/workspace/skills/{cobranca_name}")
    client_script = os.path.join(skill_base, "scripts", client_filename)

    if not os.path.exists(client_script):
        print(json.dumps({"error": f"Skill de cobrança '{cobranca_name}' nao encontrada em {client_script}"}))
        sys.exit(1)

    result = subprocess.run(
        ["python3", client_script] + sys.argv[1:],
        capture_output=True,
        text=True,
    )
    cred_err = wrap_subprocess_result(cobranca_name, result)
    if cred_err and cred_err.get("error_kind") in ("credential_invalid", "scopes_missing"):
        print(json.dumps(cred_err, ensure_ascii=False))
        sys.exit(0)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
