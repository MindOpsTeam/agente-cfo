#!/usr/bin/env python3
"""
ERP Gateway — ponto de entrada generico para qualquer skill ERP.
Uso: python3 erp_gateway.py <command> [args...]
Le CFO_ERP_NAME do .env, instancia o client correto, executa o comando.
"""
import os
import sys
import subprocess
import json


def main():
    env_file = os.path.expanduser("~/.agente-cfo/.env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    erp_name = os.environ.get("CFO_ERP_NAME", "omie")
    skill_base = os.path.expanduser(f"~/.openclaw/workspace/skills/{erp_name}")
    client_script = os.path.join(skill_base, "scripts", f"{erp_name}_client.py")

    if not os.path.exists(client_script):
        print(json.dumps({"error": f"Skill '{erp_name}' nao encontrada em {client_script}"}))
        sys.exit(1)

    result = subprocess.run(
        ["python3", client_script] + sys.argv[1:],
        capture_output=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
