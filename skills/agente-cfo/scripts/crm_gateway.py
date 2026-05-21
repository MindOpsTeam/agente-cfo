#!/usr/bin/env python3
"""
CRM Gateway — ponto de entrada generico para qualquer skill CRM.
Uso: python3 crm_gateway.py <command> [args...]
Le CFO_CRM_NAME do .env, instancia o client correto, executa o comando.

Comandos suportados (via BaseCRMClient):
  list_deals [--status open|won|lost] [--limit N] [--page N]
  pipeline_summary
  get_pipeline_projection [--days N]   # Sprint 6: projeção de fechamentos N dias
  company_info
  move_deal --id ID --to_stage STAGE
  update_deal --id ID [--amount N] [--close_date DATE]
  create_deal --title TITLE [--amount N] [--pipeline P]
  add_deal_note --id ID --note TEXT
  mark_deal_won --id ID
  mark_deal_lost --id ID [--reason TEXT]
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

    crm_name = os.environ.get("CFO_CRM_NAME", "")
    if not crm_name or crm_name == "nenhum":
        print(json.dumps({"error": "Nenhum CRM configurado. Defina CFO_CRM_NAME no .env."}))
        sys.exit(1)

    # rd-station -> rd_station for file naming
    client_filename = crm_name.replace("-", "_") + "_client.py"
    skill_base = os.path.expanduser(f"~/.openclaw/workspace/skills/{crm_name}")
    client_script = os.path.join(skill_base, "scripts", client_filename)

    if not os.path.exists(client_script):
        print(json.dumps({"error": f"Skill CRM '{crm_name}' nao encontrada em {client_script}"}))
        sys.exit(1)

    result = subprocess.run(
        ["python3", client_script] + sys.argv[1:],
        capture_output=True,
        text=True,
    )
    # HubSpot pode retornar MISSING_SCOPES — detectar antes de repassar
    required_scopes = None
    if crm_name == "hubspot":
        # Scopes comuns que podem faltar
        required_scopes = ["crm.objects.deals.read", "crm.objects.deals.write"]
    cred_err = wrap_subprocess_result(crm_name, result, required_scopes=required_scopes)
    if cred_err and cred_err.get("error_kind") in ("credential_invalid", "scopes_missing"):
        print(json.dumps(cred_err, ensure_ascii=False))
        sys.exit(0)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
