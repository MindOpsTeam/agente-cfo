---
name: hubspot
description: "Integracao com HubSpot CRM via API REST. Pipeline de vendas e deals."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🟧",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# HubSpot CRM Skill

Integracao com HubSpot CRM via API REST (Private App token).

## Setup

```bash
bash skills/hubspot/scripts/connect.sh
```

## Uso

```bash
python3 skills/hubspot/scripts/hubspot_client.py list_deals --status open
python3 skills/hubspot/scripts/hubspot_client.py pipeline_summary
python3 skills/hubspot/scripts/hubspot_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/hubspot.env` (chmod 600).
Stage mappings em `~/.openclaw/secrets/hubspot_stages.json`.
