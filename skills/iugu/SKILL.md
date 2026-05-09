---
name: iugu
description: "Cobrança via Iugu — faturas, inadimplência, links de pagamento (Pix/Boleto/Cartão)."
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

# Iugu Skill

Integração com Iugu via API REST v1. Auth por Basic Authentication (token como usuário, senha vazia).

## Setup

```bash
bash skills/iugu/scripts/connect.sh
```

Onde achar o token: `app.iugu.com → Configurações → API → Chaves de API`

## Uso

```bash
python3 skills/iugu/scripts/iugu_client.py list_invoices --status overdue --limit 20
python3 skills/iugu/scripts/iugu_client.py get_overdue_customers
python3 skills/iugu/scripts/iugu_client.py get_invoice --id xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
python3 skills/iugu/scripts/iugu_client.py get_customer --id xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
python3 skills/iugu/scripts/iugu_client.py company_info
```

## Comandos write (requerem confirmação do dono)

```bash
python3 skills/iugu/scripts/iugu_client.py send_payment_link --invoice_id <id> --channel whatsapp
python3 skills/iugu/scripts/iugu_client.py mark_invoice_paid_manually --id <id>
python3 skills/iugu/scripts/iugu_client.py create_invoice --customer_id <id> --amount 1500 --due_date 2025-06-30 --description "Mensalidade"
python3 skills/iugu/scripts/iugu_client.py cancel_invoice --id <id>
```

## Credenciais

Salvas em `~/.openclaw/secrets/iugu.env` (chmod 600).

## Notas

- Status mapeados: `open` (pending/in_analysis), `overdue` (expired), `paid` (paid/partially_paid), `cancelled` (canceled/refunded)
- `mark_invoice_paid_manually`: endpoint pode variar por tipo de conta Iugu — verifique no painel após execução
- `send_reminder`: não suportado — use `send_payment_link` por invoice
- Auth: `Basic base64(token + ":")` — token como username, senha em branco
- Docs: https://dev.iugu.com/
