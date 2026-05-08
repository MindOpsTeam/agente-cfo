---
name: rd-station
description: "Integracao com RD Station CRM via API REST. Pipeline de vendas e deals."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🔴",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# RD Station CRM Skill

Integracao com RD Station CRM via API REST.

## Setup

```bash
bash skills/rd-station/scripts/connect.sh
```

## Uso

```bash
python3 skills/rd-station/scripts/rd_station_client.py list_deals --status open
python3 skills/rd-station/scripts/rd_station_client.py pipeline_summary
python3 skills/rd-station/scripts/rd_station_client.py company_info
```

## Credenciais

Salvas em `~/.openclaw/secrets/rd-station.env` (chmod 600).
