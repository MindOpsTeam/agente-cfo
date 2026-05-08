---
name: bling
description: "Integracao com Bling ERP v3 via API REST (OAuth 2.0). Contas a pagar/receber, saldo e info da empresa."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🟡",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# Bling ERP Skill

Integracao com Bling ERP v3 via OAuth 2.0.

## Setup

```bash
bash skills/bling/scripts/connect.sh
```

## Uso

```bash
python3 skills/bling/scripts/bling_client.py get_balance
python3 skills/bling/scripts/bling_client.py list_payables --from 2026-05-01 --to 2026-05-31
python3 skills/bling/scripts/bling_client.py list_receivables --limit 50
python3 skills/bling/scripts/bling_client.py list_overdue
python3 skills/bling/scripts/bling_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/bling.env` (chmod 600).
Tokens sao renovados automaticamente via refresh_token.
