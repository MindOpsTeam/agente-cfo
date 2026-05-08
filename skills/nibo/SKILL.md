---
name: nibo
description: "Integracao com Nibo financeiro via API REST (plano Premium). Contas a pagar/receber e saldo."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🟠",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# Nibo Skill

Integracao com Nibo via API REST (requer plano Premium).

## Setup

```bash
bash skills/nibo/scripts/connect.sh
```

## Uso

```bash
python3 skills/nibo/scripts/nibo_client.py get_balance
python3 skills/nibo/scripts/nibo_client.py list_payables --from 2026-05-01 --to 2026-05-31
python3 skills/nibo/scripts/nibo_client.py list_receivables --limit 50
python3 skills/nibo/scripts/nibo_client.py list_overdue
python3 skills/nibo/scripts/nibo_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/nibo.env` (chmod 600).
