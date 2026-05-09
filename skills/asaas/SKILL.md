---
name: asaas
description: "Cobrança via Asaas — faturas, inadimplência, links de pagamento (Pix/Boleto)."
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

# Asaas Skill

Integração com Asaas via API REST v3. Auth por `access_token` no header (sem OAuth).
Suporta ambientes sandbox e produção.

## Setup

```bash
bash skills/asaas/scripts/connect.sh
```

Você precisará do **API Token** em: Minha Conta → Configurações → Integrações → API  
(`https://www.asaas.com/config/index`)

## Uso

```bash
python3 skills/asaas/scripts/asaas_client.py list_invoices --status overdue --limit 20
python3 skills/asaas/scripts/asaas_client.py get_overdue_customers
python3 skills/asaas/scripts/asaas_client.py get_invoice --id pay_xxxx
python3 skills/asaas/scripts/asaas_client.py get_customer --id cus_xxxx
python3 skills/asaas/scripts/asaas_client.py company_info
```

## Comandos write (requerem confirmação do dono)

```bash
python3 skills/asaas/scripts/asaas_client.py send_payment_link --invoice_id pay_xxxx --channel whatsapp
python3 skills/asaas/scripts/asaas_client.py mark_invoice_paid_manually --id pay_xxxx
python3 skills/asaas/scripts/asaas_client.py create_invoice --customer_id cus_xxxx --amount 1500 --due_date 2025-06-30 --description "Mensalidade"
python3 skills/asaas/scripts/asaas_client.py cancel_invoice --id pay_xxxx
```

## Credenciais

Salvas em `~/.openclaw/secrets/asaas.env` (chmod 600).

## Notas

- Status mapeados: `open` (PENDING), `overdue` (OVERDUE), `paid` (RECEIVED/RECEIVED_IN_CASH), `cancelled` (CANCELLED)
- `send_payment_link`: tenta notificação via API Asaas; retorna `payment_url` para envio manual via wacli
- `send_reminder`: não suportado diretamente — use `send_payment_link` por invoice
- Docs: https://docs.asaas.com/
