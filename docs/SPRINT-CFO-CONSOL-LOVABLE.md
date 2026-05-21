# SPRINT-CFO-CONSOL-LOVABLE.md

> Textos prontos para PM disparar via lovable_send_prompt.
> Ref: Sprint CFO-CONSOL — Templates de alerta + CRUD aprimorado.

---

## Prompt 1: Templates de alertas sugeridos na página de alertas

```
Na página de alertas (src/routes/_authenticated/alerts.tsx), adicionar uma seção
"Alertas sugeridos" que mostra templates pré-configurados que o usuário pode ativar
com 1 clique.

### Templates a mostrar (baseados em docs/skills/agente-cfo/identity/alertas_templates.md)

Mostrar cards em grid 2-3 colunas para:

const ALERT_TEMPLATES = [
  { name: "Runway < 60 dias", type: "cfo_runway_low", condition: {threshold_days: 60}, channels: ["whatsapp", "panel"], icon: "⏱️", desc: "Avisa quando o caixa cobre menos de 2 meses de operação" },
  { name: "Inadimplência > R$10k", type: "cfo_overdue_high_value", condition: {threshold_brl: 10000}, channels: ["whatsapp", "panel"], icon: "⚠️", desc: "Monitora total de vencidos" },
  { name: "Caixa < 1 burn mensal", type: "cfo_cash_low", condition: {multiplier: 1}, channels: ["whatsapp", "panel"], icon: "🔴", desc: "Alerta crítico de liquidez" },
  { name: "Anomalia de despesa", type: "cfo_expense_anomaly", condition: {threshold_pct: 20}, channels: ["panel"], icon: "🔍", desc: "Categoria cresceu >20% vs mês anterior" },
  { name: "Vencimento fiscal (7 dias)", type: "cfo_fiscal_upcoming", condition: {window_days: 7}, channels: ["whatsapp", "panel"], icon: "🧾", desc: "Obrigações DAS/FGTS/IRPJ próximas" },
  { name: "Deal sem NF (30 dias)", type: "cfo_deal_no_revenue", condition: {window_days: 30}, channels: ["panel"], icon: "🤝", desc: "Deal Won sem receita no ERP" },
  { name: "Lançamentos pendentes", type: "cfo_manual_pending", condition: {threshold_count: 3}, channels: ["panel"], icon: "📋", desc: "Writes dashboard_only aguardando migração" },
  { name: "Zero recebimentos (7d)", type: "cfo_no_receivables", condition: {window_days: 7}, channels: ["whatsapp", "panel"], icon: "💰", desc: "Sem nenhum recebimento por 7 dias" },
];

Cada card tem:
- Ícone + Nome + Descrição curta
- Badge com canais (whatsapp, painel)
- Botão "Ativar" que chama alerts-save com os parâmetros do template
- Após ativar: botão vira "✅ Ativo" e o alerta aparece na lista principal

Posicionar acima da lista de alertas existentes, com cabeçalho "Alertas sugeridos"
colapsável (aberto por padrão se não há alertas configurados, fechado se já tem).

Usar o mesmo pattern visual dos cards de integração (com Badge, Card, Button do shadcn/ui).
```

---

## Prompt 2: Página de alertas — melhorias de UX

```
Melhorias na página de alertas (src/routes/_authenticated/alerts.tsx):

1. Adicionar campo "type" visível em cada alerta da lista:
   - Badge colorido por tipo: cfo_* = azul, infra = cinza
   - Tooltip com descrição do que o alerta monitora

2. Adicionar filtro por categoria no topo:
   - Tabs: "Todos" | "Financeiro" | "Infraestrutura"
   - Filtra a lista principal

3. Adicionar coluna "Última vez disparado" na lista:
   - Lê alerts_history via alerts-history-list edge fn
   - Mostra "Nunca" ou timestamp relativo (ex: "há 2 dias")

4. Botão "Testar agora" em cada alerta:
   - Chama alerts-test edge fn
   - Mostra resultado inline (disparou / não disparou / erro)
```

---

## Prompt 3: Dashboard — widget "Últimas ações via chat" melhorado

```
No widget cfo-write-events-widget.tsx (src/components/cfo-write-events-widget.tsx),
adicionar:

1. Filtro por status:
   - Tabs: "Todos" | "ERP real" | "Painel (fallback)"
   - erp != 'dashboard_only' → "ERP real" (verde)
   - erp == 'dashboard_only' → "Painel (fallback)" (amarelo)

2. Botão "Migrar" em registros dashboard_only:
   - Aparece quando erp == 'dashboard_only' e erp_record_id é null
   - Chama uma edge fn que aciona Marcos via /hooks/agent para migrar
   - (edge fn a criar: POST /migrate-pending-write com body {write_event_id})

3. Badge de canal (whatsapp/telegram/panel) em cada item
```

---

## Prompt 4: /settings/telegram — botão "Registrar webhook"

```
Na página src/routes/_authenticated/settings_.telegram.tsx, adicionar
um botão "Registrar webhook manualmente" em cada card de bot configurado.

Ao clicar:
1. Busca o bot_token armazenado (via edge fn segura ou campo oculto)
2. Chama supabase.functions.invoke("push-command") com:
   {
     command: "telegram_webhook_set",
     payload: {
       bot_username: bot.bot_username,
       bot_token: "[precisa de campo token_hash ou requerir reinserção]",
       webhook_secret: bot.webhook_secret
     }
   }
3. Mostra toast: "✅ Webhook registrado" ou "❌ Falhou"

Nota para implementação: o token do bot não é armazenado em texto claro
após o cadastro (apenas o webhook_secret derivado). Para re-registrar o webhook,
o usuário precisará colar o token novamente. Mostrar um dialog solicitando
re-inserção do token quando o botão for clicado.
```

---

## Como disparar

```javascript
// Um por vez, na ordem (esperar cada um completar antes do próximo):
lovable_send_prompt(prompt1)  // Templates de alertas sugeridos
lovable_send_prompt(prompt2)  // Melhorias UX alertas
lovable_send_prompt(prompt3)  // Widget últimas ações
lovable_send_prompt(prompt4)  // Telegram webhook manual
```

## Contexto para PM

- `alerts_config` tem: `id`, `name`, `type`, `condition`, `channels`, `cooldown_min`, `active`
- `alerts_history` tem: `id`, `alert_id`, `triggered_at`, `message`, `channel`
- Edge fns existentes: `alerts-list`, `alerts-save`, `alerts-delete`, `alerts-test`, `alerts-history-list`
- Tipos suportados pelo `alerts_checker.py` atual: `cost_anthropic`, `daemon_down`, `tool_errors`, `latency_high`
- Tipos CFO (`cfo_runway_low`, etc.) precisam ser adicionados ao `alerts_checker.py` — isso é trabalho de código, não Lovable
- `cfo-write-events` tabela tem: `id`, `erp`, `erp_record_id`, `amount`, `supplier`, `channel`, `status`
