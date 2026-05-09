---
name: mercado-livre
description: "E-commerce via Mercado Livre — pedidos, produtos, estoque e métricas de vendas."
homepage: https://github.com/MindOpsTeam/agente-cfo
metadata:
  {
    "openclaw":
      {
        "emoji": "🟡",
        "requires": { "bins": ["python3", "curl"] },
      },
  }
---

# Mercado Livre Skill

Integração com Mercado Livre via API REST usando OAuth 2.0 com refresh token automático.

## Setup

```bash
bash skills/mercado-livre/scripts/connect.sh
```

Você precisará de:
1. Um app criado em [developers.mercadolivre.com.br](https://developers.mercadolivre.com.br)
   - Redirect URI: `https://localhost` (ou qualquer URL válida)
2. **App ID** e **Secret Key** do app

O `connect.sh` abre a URL de autorização. Após autorizar, copie o `code=TG-XXXXX` da URL de redirect.

## Uso

```bash
python3 skills/mercado-livre/scripts/mercado_livre_client.py list_orders --status paid --limit 20
python3 skills/mercado-livre/scripts/mercado_livre_client.py list_orders --status paid --since 2025-05-01
python3 skills/mercado-livre/scripts/mercado_livre_client.py get_order --id 12345678
python3 skills/mercado-livre/scripts/mercado_livre_client.py list_products --limit 50
python3 skills/mercado-livre/scripts/mercado_livre_client.py get_low_stock --threshold 3
python3 skills/mercado-livre/scripts/mercado_livre_client.py get_sales_metrics --days 30
python3 skills/mercado-livre/scripts/mercado_livre_client.py company_info
```

## Comandos write (requerem confirmação do dono)

```bash
python3 skills/mercado-livre/scripts/mercado_livre_client.py update_stock --product_id MLB123 --new_qty 50
python3 skills/mercado-livre/scripts/mercado_livre_client.py update_price --product_id MLB123 --new_price 149.90
python3 skills/mercado-livre/scripts/mercado_livre_client.py mark_order_shipped --id 12345678 --tracking_code AA123456789BR
python3 skills/mercado-livre/scripts/mercado_livre_client.py cancel_order --id 12345678 --reason "Produto indisponivel"
```

## Credenciais

Salvas em `~/.openclaw/secrets/mercado-livre.env` (chmod 600).  
Refresh token renovado automaticamente a cada uso com token próximo ao vencimento.

## Notas

- Status de pedido: `paid` (paid/ready_to_ship), `shipped`, `delivered`, `cancelled`, `pending`
- `list_products` usa batch de detalhes (20 por requisição) — pode ser lento para catálogos grandes
- `mark_order_shipped`: requer `shipment_id` — extraído automaticamente do pedido
- `get_sales_metrics` usa `list_orders --status all` com filtro `since` — inclui apenas paid/shipped/delivered
- Docs: https://developers.mercadolivre.com.br/
