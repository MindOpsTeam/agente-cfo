---
name: <nome>
description: "<descricao curta>"
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🔌",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# <Nome> ERP/CRM Skill

Integração com <Nome> via API REST.

## Setup

```bash
bash skills/<nome>/scripts/connect.sh
```

## Uso

```bash
python3 skills/<nome>/scripts/<nome>_client.py get_balance
python3 skills/<nome>/scripts/<nome>_client.py list_payables --from 2026-05-01 --to 2026-05-31
python3 skills/<nome>/scripts/<nome>_client.py list_receivables --limit 50
python3 skills/<nome>/scripts/<nome>_client.py list_overdue
python3 skills/<nome>/scripts/<nome>_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/<nome>.env` (chmod 600).
