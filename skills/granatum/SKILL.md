---
name: granatum
description: "Integracao com Granatum financeiro via API REST. Contas a pagar/receber e saldo."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "💚",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# Granatum Skill

Integracao com Granatum via API REST.

## Setup

```bash
bash skills/granatum/scripts/connect.sh
```

## Uso

```bash
python3 skills/granatum/scripts/granatum_client.py get_balance
python3 skills/granatum/scripts/granatum_client.py list_payables --from 2026-05-01 --to 2026-05-31
python3 skills/granatum/scripts/granatum_client.py list_receivables --limit 50
python3 skills/granatum/scripts/granatum_client.py list_overdue
python3 skills/granatum/scripts/granatum_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/granatum.env` (chmod 600).
