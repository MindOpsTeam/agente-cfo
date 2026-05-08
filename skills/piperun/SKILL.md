---
name: piperun
description: "Integracao com PipeRun CRM via API REST. Pipeline de vendas e deals."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🚀",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# PipeRun CRM Skill

Integracao com PipeRun CRM via API REST.

## Setup

```bash
bash skills/piperun/scripts/connect.sh
```

## Uso

```bash
python3 skills/piperun/scripts/piperun_client.py list_deals --status open
python3 skills/piperun/scripts/piperun_client.py pipeline_summary
python3 skills/piperun/scripts/piperun_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/piperun.env` (chmod 600).
