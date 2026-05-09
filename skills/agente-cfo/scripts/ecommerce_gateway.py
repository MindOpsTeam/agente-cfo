#!/usr/bin/env python3
"""
E-commerce Gateway — ponto de entrada genérico para qualquer skill de e-commerce.
Uso: python3 ecommerce_gateway.py <command> [args...]
Lê CFO_ECOMMERCE_NAME do .env, instancia o client correto, executa o comando.

Comandos suportados (via BaseEcommerceClient):
  list_orders [--status pending|paid|shipped|delivered|cancelled|all] [--limit N] [--since YYYY-MM-DD]
  get_order --id X
  list_products [--limit N] [--in_stock_only true]
  get_product --id X
  get_low_stock [--threshold N]
  get_sales_metrics [--days N]
  company_info
  update_stock --product_id X --new_qty N
  mark_order_shipped --id X [--tracking_code CODE]
  update_price --product_id X --new_price N
  cancel_order --id X [--reason "..."]
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

    ecom_name = os.environ.get("CFO_ECOMMERCE_NAME", "nenhum")
    if not ecom_name or ecom_name == "nenhum":
        print(json.dumps({"error": "Nenhuma plataforma de e-commerce configurada. "
                          "Defina CFO_ECOMMERCE_NAME no .env (mercado-livre ou nuvemshop)."}))
        sys.exit(1)

    client_filename = ecom_name.replace("-", "_") + "_client.py"
    skill_base = os.path.expanduser(f"~/.openclaw/workspace/skills/{ecom_name}")
    client_script = os.path.join(skill_base, "scripts", client_filename)

    if not os.path.exists(client_script):
        print(json.dumps({"error": f"Skill de e-commerce '{ecom_name}' nao encontrada em {client_script}"}))
        sys.exit(1)

    result = subprocess.run(
        ["python3", client_script] + sys.argv[1:],
        capture_output=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
