---
name: omie
description: "Integracao com Omie ERP via API REST. Contas a pagar/receber, resumo financeiro, clientes, produtos, pedidos, NF-e e estoque."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "📊",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# Omie ERP Skill

Integracao com Omie ERP via API REST (JSON-RPC).

## Setup

```bash
bash skills/omie/scripts/connect.sh
```

## Uso

### Comandos unificados (schema CFO)

```bash
python3 skills/omie/scripts/omie_client.py get_balance
python3 skills/omie/scripts/omie_client.py list_payables --from 2026-05-01 --to 2026-05-31
python3 skills/omie/scripts/omie_client.py list_receivables --limit 50
python3 skills/omie/scripts/omie_client.py list_overdue
python3 skills/omie/scripts/omie_client.py company_info
```

### Comandos legados (Omie nativo)

```bash
python3 skills/omie/scripts/omie_client.py resumo_financeiro
python3 skills/omie/scripts/omie_client.py contas_receber [pagina] [por_pagina]
python3 skills/omie/scripts/omie_client.py contas_pagar [pagina] [por_pagina]
python3 skills/omie/scripts/omie_client.py clientes_listar [pagina] [por_pagina]
python3 skills/omie/scripts/omie_client.py produtos_listar [pagina] [por_pagina]
python3 skills/omie/scripts/omie_client.py pedidos_listar [pagina] [por_pagina]
python3 skills/omie/scripts/omie_client.py nfe_listar [pagina] [por_pagina]
python3 skills/omie/scripts/omie_client.py estoque_posicao [pagina] [por_pagina]
```

## Credenciais

Salvas em `~/.openclaw/secrets/omie.env` (chmod 600):

```
OMIE_APP_KEY=12345678901
OMIE_APP_SECRET=abc123def456...
```
