---
name: cfo-conciliacao-bancaria
description: >
  PLACEHOLDER — Conciliação de extrato bancário vs lançamentos ERP.
  Interface pronta para integração futura com Open Finance / Pluggy / OFX.
  Quando o usuário conectar um banco via Pluggy ou importar OFX, esta skill
  fará o cruzamento automático com o ERP.
category: CFO/Conciliação
metadata:
  { "openclaw": { "emoji": "🏦", "requires": { "bins": ["python3"] } } }
---

# CFO — Conciliação Bancária ↔ ERP (Placeholder)

> ⚠️ **Status:** Placeholder. Scripts de cruzamento prontos, integração bancária pendente.

## Interface esperada

```bash
# Quando banco for conectado via Pluggy/Open Finance:
python3 $SKILL_DIR/scripts/cruzar.py --conta corrente --periodo 30

# Para importar extrato OFX/CSV manualmente:
python3 $SKILL_DIR/scripts/importar_extrato.py --formato ofx --arquivo /tmp/extrato.ofx
python3 $SKILL_DIR/scripts/cruzar.py --periodo 30
```

## Como conectar banco (futuro)

1. Criar conta no Pluggy (pluggy.ai) ou usar Open Finance BR
2. Configurar no painel `/integrations` (nova entrada: "Banco via Open Finance")
3. Esta skill passa a receber via `PLUGGY_ITEM_ID` + `PLUGGY_CLIENT_ID` + `PLUGGY_CLIENT_SECRET`
4. Cron diário pode então rodar conciliação automática

## Match logic (quando ativo)

- Valor exato ou ±0.01 (centavos de diferença bancária)
- Data: ±1 dia (D+1 de compensação)
- Tipo: crédito bancário = recebível ERP; débito bancário = pagável ERP

## Provedor sugerido

[Pluggy](https://pluggy.ai) — agregador Open Finance BR com SDK Python.
Cobre ~200 instituições financeiras brasileiras.
