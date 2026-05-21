# Alertas Templates — Marcos CFO

> Templates de alertas prontos para o cliente ativar com 1 clique no painel.
> Cada template mapeia diretamente para um tipo em `alerts_config`.
> Painel usa esta lista para mostrar "Alertas sugeridos".

---

## Categoria: Caixa & Runway

### 1. Runway crítico
- **Nome:** Runway baixo — menos de 60 dias
- **Tipo:** `cfo_runway_low`
- **Condição:** `{"threshold_days": 60}`
- **Canais:** whatsapp, painel
- **Cooldown:** 1440 min (1x/dia)
- **Mensagem:** "⚠️ Runway em {runway_dias} dias. Menos de 2 meses de operação coberta. Revisar burn ou antecipar recebíveis."

### 2. Caixa abaixo do burn mensal
- **Nome:** Caixa menor que 1 mês de burn
- **Tipo:** `cfo_cash_low`
- **Condição:** `{"multiplier": 1}` (caixa < 1x burn)
- **Canais:** whatsapp, painel
- **Cooldown:** 1440 min
- **Mensagem:** "🔴 Caixa ({valor}) menor que burn mensal ({burn}). Situação crítica."

### 3. Saldo negativo
- **Nome:** Saldo negativo
- **Tipo:** `cfo_balance_negative`
- **Condição:** `{}`
- **Canais:** whatsapp, painel
- **Cooldown:** 60 min
- **Mensagem:** "🚨 Saldo negativo: {valor}. Ação imediata necessária."

---

## Categoria: Inadimplência

### 4. Inadimplência alta (valor absoluto)
- **Nome:** Inadimplência acima de R$10.000
- **Tipo:** `cfo_overdue_high_value`
- **Condição:** `{"threshold_brl": 10000}`
- **Canais:** whatsapp, painel
- **Cooldown:** 480 min (2x/dia)
- **Mensagem:** "⚠️ Inadimplência total: {valor} ({count} clientes). Executar cobrança?"

### 5. Inadimplência alta (percentual)
- **Nome:** Inadimplência > 15% do faturamento
- **Tipo:** `cfo_overdue_high_pct`
- **Condição:** `{"threshold_pct": 15}`
- **Canais:** whatsapp, painel
- **Cooldown:** 1440 min
- **Mensagem:** "🔴 Inadimplência em {pct}% do faturamento — acima do limite de 15%."

### 6. Recebimento parou
- **Nome:** Zero recebimentos por 7 dias
- **Tipo:** `cfo_no_receivables`
- **Condição:** `{"window_days": 7}`
- **Canais:** whatsapp, painel
- **Cooldown:** 1440 min
- **Mensagem:** "⚠️ Nenhum recebimento registrado nos últimos 7 dias. Verificar ERP e carteira de clientes."

---

## Categoria: Despesas & Anomalias

### 7. Categoria de despesa cresceu > 20% MoM
- **Nome:** Anomalia de despesa por categoria
- **Tipo:** `cfo_expense_anomaly`
- **Condição:** `{"threshold_pct": 20}`
- **Canais:** painel
- **Cooldown:** 1440 min
- **Mensagem:** "🔍 Categoria '{categoria}' cresceu {pct}% vs mês anterior. Investigar."

### 8. Despesa total anômala (z-score)
- **Nome:** Despesas fora do padrão histórico
- **Tipo:** `cfo_expense_zscore`
- **Condição:** `{"zscore_threshold": 2.0}`
- **Canais:** painel
- **Cooldown:** 1440 min
- **Mensagem:** "⚠️ Despesas do mês com z-score {zscore:.1f}σ acima do normal. Revisar."

---

## Categoria: Conciliação Cross-Sistema

### 9. Deal Won sem receita ERP (30d)
- **Nome:** Deal HubSpot fechado sem NF no ERP
- **Tipo:** `cfo_deal_no_revenue`
- **Condição:** `{"window_days": 30}`
- **Canais:** painel
- **Cooldown:** 1440 min
- **Mensagem:** "⚠️ Deal '{titulo}' fechado em {data} por {valor} sem receita registrada no ERP nos 30 dias seguintes."

### 10. Lançamentos manuais pendentes
- **Nome:** Writes dashboard_only não migrados
- **Tipo:** `cfo_manual_pending`
- **Condição:** `{"threshold_count": 3}`
- **Canais:** painel
- **Cooldown:** 1440 min
- **Mensagem:** "📋 {count} lançamentos no painel aguardando migração pro ERP ({valor} total)."

---

## Categoria: Fiscal & Compliance

### 11. Vencimento fiscal próximo (7 dias)
- **Nome:** Obrigação fiscal vencendo em 7 dias
- **Tipo:** `cfo_fiscal_upcoming`
- **Condição:** `{"window_days": 7}`
- **Canais:** whatsapp, painel
- **Cooldown:** 1440 min
- **Mensagem:** "🧾 Obrigação fiscal vencendo: {obrigacao} em {data}. Verificar se está preparado."

### 12. Vencimento fiscal urgente (2 dias)
- **Nome:** Obrigação fiscal vencendo amanhã
- **Tipo:** `cfo_fiscal_urgent`
- **Condição:** `{"window_days": 2}`
- **Canais:** whatsapp, painel
- **Cooldown:** 360 min
- **Mensagem:** "🔴 URGENTE: {obrigacao} vence em {data}. Pagar hoje."

---

## Categoria: Cobrança

### 13. Boleto Asaas a vencer (sem confirmação)
- **Nome:** Boleto vence em 3 dias sem confirmação
- **Tipo:** `cfo_invoice_expiring`
- **Condição:** `{"window_days": 3, "platform": "asaas"}`
- **Canais:** painel
- **Cooldown:** 480 min
- **Mensagem:** "💰 {count} boleto(s) Asaas vencendo nos próximos 3 dias ({valor} total). Enviar lembrete?"

---

## Formato para cadastro via API (alerts-save)

```json
{
  "name": "Runway baixo — menos de 60 dias",
  "type": "cfo_runway_low",
  "condition": {"threshold_days": 60},
  "channels": ["whatsapp", "panel"],
  "cooldown_min": 1440,
  "active": true
}
```

> **Nota:** os tipos `cfo_*` são processados pelo `cfo-alerts-checker` daemon.
> Os tipos infraestrutura (`daemon_down`, `error_rate`, `cost_anthropic`, `latency_high`)
> são processados pelo `alerts_checker.py` daemon.
> Ambos leem da mesma tabela `alerts_config`.
