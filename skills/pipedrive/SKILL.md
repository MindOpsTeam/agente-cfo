---
name: pipedrive
description: "Integracao com Pipedrive CRM via API REST v1. Pipeline de vendas e deals."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🟢",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# Pipedrive CRM Skill

Integracao com Pipedrive CRM via API REST v1 usando API Token estático.

## Setup

```bash
bash skills/pipedrive/scripts/connect.sh
```

Você precisará de:
1. O **subdomínio** da sua empresa (ex: `minhaempresa` de `minhaempresa.pipedrive.com`)
2. Um **API Token** em Perfil → Configurações → API

## Uso

```bash
python3 skills/pipedrive/scripts/pipedrive_client.py list_deals --status open
python3 skills/pipedrive/scripts/pipedrive_client.py pipeline_summary
python3 skills/pipedrive/scripts/pipedrive_client.py get_pipeline_projection --days 30
python3 skills/pipedrive/scripts/pipedrive_client.py company_info
```

## Comandos write

```bash
python3 skills/pipedrive/scripts/pipedrive_client.py move_deal --id 123 --to_stage "Proposta"
python3 skills/pipedrive/scripts/pipedrive_client.py update_deal --id 123 --amount 5000 --close_date 2025-06-30
python3 skills/pipedrive/scripts/pipedrive_client.py create_deal --title "Novo cliente" --amount 10000
python3 skills/pipedrive/scripts/pipedrive_client.py mark_deal_won --id 123
python3 skills/pipedrive/scripts/pipedrive_client.py mark_deal_lost --id 123 --reason "Sem budget"
python3 skills/pipedrive/scripts/pipedrive_client.py add_deal_note --id 123 --note "Follow-up feito"
```

## Credenciais

Salvas em `~/.openclaw/secrets/pipedrive.env` (chmod 600).  
Stage mappings em `~/.openclaw/secrets/pipedrive_stages.json`.

## Notas

- `move_deal --to_stage` aceita ID numérico ou nome do stage (case-insensitive)
- `get_pipeline_projection` usa a implementação padrão de `BaseCRMClient`
- Paginação: Pipedrive usa `start` (offset), não `page` — a skill converte automaticamente
