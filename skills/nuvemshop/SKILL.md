---
name: nuvemshop
description: "E-commerce via Nuvemshop — pedidos, produtos, estoque e métricas de vendas."
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

# Nuvemshop Skill

Integração com Nuvemshop via API REST v1 usando OAuth 2.0.  
O access token da Nuvemshop é **long-lived** (não expira) — sem refresh necessário.

## Setup

```bash
bash skills/nuvemshop/scripts/connect.sh
```

Você precisará de:
1. Um app criado em [partners.nuvemshop.com.br](https://partners.nuvemshop.com.br) ou diretamente na loja
   - Redirect URI: `https://localhost`
2. **Client ID** e **Client Secret** do app

## Uso

```bash
python3 skills/nuvemshop/scripts/nuvemshop_client.py list_orders --status paid --limit 20
python3 skills/nuvemshop/scripts/nuvemshop_client.py list_orders --status paid --since 2025-05-01
python3 skills/nuvemshop/scripts/nuvemshop_client.py get_order --id 123456
python3 skills/nuvemshop/scripts/nuvemshop_client.py list_products --limit 50
python3 skills/nuvemshop/scripts/nuvemshop_client.py get_low_stock --threshold 3
python3 skills/nuvemshop/scripts/nuvemshop_client.py get_sales_metrics --days 30
python3 skills/nuvemshop/scripts/nuvemshop_client.py company_info
```

## Comandos write (requerem confirmação do dono)

```bash
python3 skills/nuvemshop/scripts/nuvemshop_client.py update_stock --product_id 123 --new_qty 50
python3 skills/nuvemshop/scripts/nuvemshop_client.py update_price --product_id 123 --new_price 149.90
python3 skills/nuvemshop/scripts/nuvemshop_client.py mark_order_shipped --id 456 --tracking_code AA123456789BR
python3 skills/nuvemshop/scripts/nuvemshop_client.py cancel_order --id 456 --reason "Produto indisponivel"
```

## Credenciais

Salvas em `~/.openclaw/secrets/nuvemshop.env` (chmod 600).  
Token long-lived — sem refresh automático. Se revogar o app na Nuvemshop, execute `connect.sh --force`.

## Notas

- `list_products`: estoque agregado das variantes; `price_brl` = preço da primeira variante
- `update_stock` / `update_price`: atualiza apenas a primeira variante — para produtos com múltiplas variantes, use o painel
- `get_sales_metrics`: status `paid` inclui paid + shipped + delivered
- `cancel_order`: endpoint pode retornar 422 se o pedido já foi enviado
- Docs: https://tiendanube.github.io/api-documentation/
