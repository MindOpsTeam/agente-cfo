---
name: vhsys
description: "Integracao com VHSYS ERP via API REST. Contas a pagar/receber e saldo."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🔵",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# VHSYS ERP Skill

Integracao com VHSYS via API REST v2.

## Setup

```bash
bash skills/vhsys/scripts/connect.sh
```

## Uso

```bash
python3 skills/vhsys/scripts/vhsys_client.py get_balance
python3 skills/vhsys/scripts/vhsys_client.py list_payables --from 2026-05-01 --to 2026-05-31
python3 skills/vhsys/scripts/vhsys_client.py list_receivables --limit 50
python3 skills/vhsys/scripts/vhsys_client.py list_overdue
python3 skills/vhsys/scripts/vhsys_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/vhsys.env` (chmod 600):
```
VHSYS_ACCESS_TOKEN=xxx
VHSYS_SECRET_TOKEN=yyy
```
