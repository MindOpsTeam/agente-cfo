---
name: contaazul
description: "Integracao com ContaAzul ERP via API REST v1 (OAuth 2.0). Financeiro completo."
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

# ContaAzul ERP Skill

Integração com ContaAzul ERP via API REST v1 (nova API financeira) usando OAuth 2.0
com refresh token automático.

## Setup

```bash
bash skills/contaazul/scripts/connect.sh
```

Você precisará de:
1. Um app OAuth criado em [developers.contaazul.com](https://developers.contaazul.com)
   - Tipo: Authorization Code
   - Redirect URI: `urn:ietf:wg:oauth:2.0:oob`
   - Escopos: `financeiro`
2. **Client ID** e **Client Secret** do app

O script abre a URL de autorização, você cola o código recebido e os tokens são salvos automaticamente.

## Uso

```bash
python3 skills/contaazul/scripts/contaazul_client.py get_balance
python3 skills/contaazul/scripts/contaazul_client.py list_receivables --from 2025-05-01 --to 2025-05-31
python3 skills/contaazul/scripts/contaazul_client.py list_payables --from 2025-05-01 --to 2025-05-31
python3 skills/contaazul/scripts/contaazul_client.py list_overdue
python3 skills/contaazul/scripts/contaazul_client.py get_cash_projection --days 30
```

## Comandos write

```bash
python3 skills/contaazul/scripts/contaazul_client.py pay_payable --id <id>
python3 skills/contaazul/scripts/contaazul_client.py mark_received --id <id>
python3 skills/contaazul/scripts/contaazul_client.py create_payable --amount 500 --due_date 2025-06-10 --supplier "Fornecedor ABC"
python3 skills/contaazul/scripts/contaazul_client.py create_receivable --amount 1200 --due_date 2025-06-15 --customer "Cliente XYZ"
python3 skills/contaazul/scripts/contaazul_client.py cancel_payable --id <id>
```

## Credenciais

Salvas em `~/.openclaw/secrets/contaazul.env` (chmod 600).  
O refresh token é renovado automaticamente a cada uso.

## Notas técnicas

- `get_balance`: soma `saldo-atual` de todas as contas financeiras ativas
- Paginação: parâmetros `pagina` + `tamanhoPagina` (máx. 100 por página)
- `cancel_payable`: usa PATCH com status `CANCELADO` (a API v1 pública não expõe DELETE de parcelas)
- Docs: https://developers.contaazul.com/docs/financial-apis-openapi/v1
