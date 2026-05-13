---
name: kommo
description: "Integracao com Kommo CRM (formerly amoCRM) via API v4. Leads, contatos, empresas, tarefas, pipelines."
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

# Kommo CRM Skill

Integracao com Kommo CRM (formerly amoCRM) via API REST v4 usando Access Token.

## Setup

```bash
bash skills/kommo/scripts/connect.sh
```

Voce precisara de:
1. O **subdominio** da sua conta (ex: `minhaempresa` de `minhaempresa.kommo.com`)
2. Um **Access Token** em Configuracoes → Integracoes → API

## Credenciais

Salvas em `~/.openclaw/secrets/kommo.env` (chmod 600).
