---
name: tiny
description: "Integracao com Tiny ERP via API v2. Contas a pagar/receber e info da empresa."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🟣",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# Tiny ERP Skill

Integracao com Tiny ERP via API v2.

## Setup

```bash
bash skills/tiny/scripts/connect.sh
```

## Uso

```bash
python3 skills/tiny/scripts/tiny_client.py get_balance
python3 skills/tiny/scripts/tiny_client.py list_payables --from 2026-05-01 --to 2026-05-31
python3 skills/tiny/scripts/tiny_client.py list_receivables --limit 50
python3 skills/tiny/scripts/tiny_client.py list_overdue
python3 skills/tiny/scripts/tiny_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/tiny.env` (chmod 600).
