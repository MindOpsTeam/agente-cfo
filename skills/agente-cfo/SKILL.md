---
name: agente-cfo
description: "CFO virtual para PME brasileira. Orquestra omie (dados financeiros do ERP) e wacli (envio de alertas via WhatsApp). Gera insights de fluxo de caixa, categoriza lançamentos, dispara alertas matinais e vespertinos, e monitora saúde do sistema. Use quando o usuário pedir resumo financeiro, alertas de caixa, categorização de lançamentos, ou diagnóstico do agente CFO."
homepage: https://agente-cfo.com.br
metadata:
  {
    "openclaw":
      {
        "emoji": "💼",
        "requires": { "bins": ["wacli", "python3", "curl", "jq"] },
      },
  }
---

# Agente CFO

CFO virtual para PME brasileira. Conecta o ERP Omie ao WhatsApp do dono da empresa,
gerando insights financeiros diários sem intervenção manual.

Modelo: **single-tenant** — cada cliente roda sua própria instância (VPS + OpenClaw + skill).
Sem multi-tenancy, sem license key. Auth VPS↔painel via `X-Panel-Token`.

## Arquitetura

```
[Cron 07:00] ──▶ agente lê prompts/alerta_manha.md
[Cron 18:00] ──▶ agente lê prompts/alerta_tarde.md
                     │
                     ▼
            omie_client.py (dados ERP)
                     │
                     ▼
            LLM gera insight em PT-BR
                     │
                     ▼
            wacli send text (WhatsApp)
                     │
                     ▼
            curl → PANEL_BASE_URL/event (painel central)
```

## Variáveis de Ambiente Requeridas

| Variável | Descrição | Exemplo |
|---|---|---|
| `OMIE_APP_KEY` | App Key da integração Omie | `12345678901` |
| `OMIE_APP_SECRET` | App Secret da integração Omie | `abc123def456...` |
| `CFO_WHATSAPP_TO` | Número destino dos alertas (E.164) | `+5511999999999` |
| `ANTHROPIC_API_KEY` | Chave de API Anthropic | `sk-ant-...` |
| `PANEL_BASE_URL` | URL do Supabase Edge Functions do cliente | `https://xxxx.supabase.co/functions/v1` |
| `PANEL_TOKEN` | Token de autenticação VPS↔painel | `(gerado pelo setup.sh)` |
| `INSTANCE_ID` | UUID da instância no painel | `(gerado pelo setup.sh)` |
| `HOOKS_TOKEN` | Token de auth do endpoint /hooks/agent | `(gerado pelo setup.sh)` |
| `LLM_BUDGET_BRL` | Teto mensal de custo LLM em BRL | `50` |

## Variáveis Opcionais

| Variável | Descrição | Padrão |
|---|---|---|
| `INGRESS_URL` | URL pública do Cloudflare Tunnel | _(detectada automaticamente)_ |
| `OMIE_SKILL_PATH` | Path absoluto da skill omie | `~/.openclaw/workspace/skills/omie` |
| `CFO_LOG_DIR` | Diretório de logs | `~/.agente-cfo/logs` |
| `CFO_STATE_DIR` | Diretório de estado (budget, cron-ids) | `~/.agente-cfo` |
| `LLM_INPUT_PRICE_BRL` | Preço por 1M tokens input em BRL | `9.50` |
| `LLM_OUTPUT_PRICE_BRL` | Preço por 1M tokens output em BRL | `47.50` |

## Endpoint /hooks/agent

O OpenClaw Gateway expõe nativamente o endpoint `/hooks/agent` **na porta 18789** (porta padrão do gateway).

- **Método:** `POST`
- **Auth:** `Authorization: Bearer <HOOKS_TOKEN>` (ou `X-OpenClaw-Token: <HOOKS_TOKEN>`)
- **Body JSON:**

```json
{
  "message":        "Execute: bash ~/.openclaw/workspace/skills/agente-cfo/scripts/cfo-reporter.sh ...",
  "name":           "PainelCFO",
  "wakeMode":       "now",
  "deliver":        false,
  "timeoutSeconds": 60
}
```

- **Configuração:** o token vem de `hooks.token` no config do OpenClaw (setado automaticamente pelo `setup.sh` via variável de ambiente `HOOKS_TOKEN`).
- **HTTPS externo:** o Cloudflare Tunnel (`INGRESS_URL`) faz proxy para `http://localhost:18789`, portanto o painel acessa via `${INGRESS_URL}/hooks/agent`.

O `push-command` da edge function Supabase usa exatamente esse endpoint para enviar comandos do painel para a VPS.

## Ferramentas Expostas pela Skill

### 1. `doctor.sh` — Diagnóstico do sistema
```bash
bash skills/agente-cfo/scripts/doctor.sh
```
Testa: WhatsApp pareado, Omie acessível, PANEL_TOKEN presente, conectividade com painel, endpoint /hooks/agent.
Exit 0 = tudo ok. Exit 1 = falha em algum componente.

### 2. `repare.sh` — Re-pareamento WhatsApp
```bash
bash skills/agente-cfo/scripts/repare.sh
```
Guia o usuário pelo re-pareamento do WhatsApp quando o QR expira.

### 3. `cfo-reporter.sh` — Relatório sob demanda
```bash
bash skills/agente-cfo/scripts/cfo-reporter.sh <prompt_file>
# Exemplos:
bash skills/agente-cfo/scripts/cfo-reporter.sh prompts/alerta_manha.md
bash skills/agente-cfo/scripts/cfo-reporter.sh prompts/alerta_tarde.md
```
Wrapper principal: coleta dados Omie → chama LLM com prompt → envia WhatsApp → reporta ao painel.

### 4. `omie-pull-wrapper.sh` — Coleta de dados Omie com retry
```bash
bash skills/agente-cfo/scripts/omie-pull-wrapper.sh <comando_omie> [args...]
# Exemplo:
bash skills/agente-cfo/scripts/omie-pull-wrapper.sh resumo_financeiro
bash skills/agente-cfo/scripts/omie-pull-wrapper.sh contas_receber 1 50
```

### 5. `check-budget.sh` — Controle de custo LLM
```bash
bash skills/agente-cfo/scripts/check-budget.sh
```
Parseia sessões do OpenClaw, estima custo mensal em BRL. Se ultrapassar `LLM_BUDGET_BRL`,
desabilita os cron jobs de alerta e notifica via WhatsApp.

### 6. `whatsapp-watch.sh` — Monitor de conexão WhatsApp
```bash
bash skills/agente-cfo/scripts/whatsapp-watch.sh
```
Poll a cada 30 minutos via `wacli doctor`. Se QR expirado, alerta via mensagem no terminal
e reporta ao painel. Rode como processo background ou cron separado.

### 7. `heartbeat.sh` — Heartbeat ao painel
```bash
bash skills/agente-cfo/scripts/heartbeat.sh
```
Chamado pelo cron `*/5 * * * *`. Envia heartbeat ao painel incluindo `INGRESS_URL` atual
(re-detectada do cloudflared se mudou).

## Cron Jobs (registrados pelo setup.sh)

5 cron jobs são registrados. Os IDs são salvos em `~/.agente-cfo/cron-ids.env`:

```bash
# ~/.agente-cfo/cron-ids.env (gerado pelo setup.sh)
CRON_ID_MANHA=<uuid>
CRON_ID_TARDE=<uuid>
CRON_ID_HEARTBEAT=<uuid>
CRON_ID_BUDGET=<uuid>
CRON_ID_WA_WATCH=<uuid>
```

| Job | Schedule | Descrição |
|---|---|---|
| `alerta_manha` | 07:00 BRT | Alerta matinal — saldo + contas do dia |
| `alerta_tarde` | 18:00 BRT | Resumo do dia + projeção 7 dias |
| `heartbeat` | `*/5 * * * *` | Keepalive + ingress_url para o painel |
| `check-budget` | 03:00 BRT | Controle de custo LLM mensal |
| `whatsapp-watch` | `*/30 * * * *` | Monitor de conexão WhatsApp |

O `check-budget.sh` lê esse arquivo para pausar/retomar os crons via `openclaw cron disable/enable`.

## Notificações Proativas (Sprint 5)

Marcos detecta anomalias financeiras e comerciais **autonomamente**, sem esperar cron ou mensagem do dono.

### Daemon: `cfo_proactive_watcher.py`

Roda como `cfo-proactive.service` (systemd). Loop a cada 30 minutos (configurável via `CFO_PROACTIVE_INTERVAL_MINUTES`).

**Fluxo por ciclo:**
1. Carrega ERP client (`CFO_ERP_NAME`) e CRM client (`CFO_CRM_NAME`) dinamicamente
2. Executa todas as regras em `proactive_rules/`
3. Aplica cooldown por `dedup_key` (estado em `~/.agente-cfo/state/proactive_alerts.json`)
4. Dispara `/hooks/agent` com `name=proactive_alert` para cada nova anomalia
5. Marcos formata mensagem curta (≤600 chars) usando `prompts/proactive.md` e envia via WhatsApp
6. Emite `_panel_event "proactive_alert"` → aparece em `/audit` e `/events` do painel

**Governance:** daemon é 100% read-only. Nenhum write no ERP/CRM.

### Regras de detecção

| Regra | Trigger | Severity | Cooldown | Dependência |
|---|---|---|---|---|
| `rule_overdue_critical` | Conta vencida há >7 dias | warn/critical (>30d) | 168h por conta | ERP |
| `rule_cash_low` | Caixa projetado 7d < `LLM_BUDGET_BRL × 5` | warn/critical (<50% threshold) | 24h global | ERP |
| `rule_concentration` | 1 cliente >40% do total a receber | warn | 168h por cliente | ERP |
| `rule_inadimplencia_high` | Total vencido / total a receber >15% | warn (>15%), critical (>30%) | 24h global | ERP |
| `rule_deal_stale` | Deal aberto sem update há >30 dias | info | 168h por deal | CRM |
| `rule_pipeline_drop` | Won mês corrente < 50% do mês anterior (proporcional) | warn | 168h global | CRM |
| `rule_erp_api_health` | API ERP com falha em ≥2 ciclos consecutivos | warn/critical | 24h | ERP |

**Thresholds configuráveis via env vars:**

| Variável | Padrão | Significado |
|---|---|---|
| `CFO_OVERDUE_DAYS_THRESHOLD` | `7` | Dias de atraso para disparar overdue_critical |
| `CFO_CASH_LOW_THRESHOLD_BRL` | `LLM_BUDGET_BRL × 5` | Override manual do threshold de caixa |
| `CFO_CASH_THRESHOLD_MULTIPLIER` | `5` | Multiplicador sobre LLM_BUDGET_BRL |
| `CFO_CONCENTRATION_THRESHOLD_PCT` | `40` | % de concentração por cliente |
| `CFO_INADIMPLENCIA_WARN_PCT` | `15` | % de inadimplência para warn |
| `CFO_INADIMPLENCIA_CRITICAL_PCT` | `30` | % de inadimplência para critical |
| `CFO_DEAL_STALE_DAYS` | `30` | Dias sem update para deal_stale |
| `CFO_PIPELINE_DROP_THRESHOLD_PCT` | `50` | Queda % de won para pipeline_drop |
| `CFO_ERP_ERRORS_THRESHOLD` | `2` | Erros consecutivos para erp_api_health |
| `CFO_PROACTIVE_INTERVAL_MINUTES` | `30` | Intervalo do loop do daemon |

**Ressalvas por skill ERP:**
- Regras que dependem de `get_balance()` silenciosamente pulam se o ERP retorna `not_supported`
- `rule_pipeline_drop` e `rule_deal_stale` são puladas se `CFO_CRM_NAME=nenhum`
- ERPs sem `list_overdue()` nativo usam o fallback da `BaseERPClient` (filtra por `due_date < hoje`)

### Logs e estado

```
~/.agente-cfo/
├── logs/
│   └── proactive.log              # logs do daemon proativo
└── state/
    └── proactive_alerts.json      # cooldown state: dedup_key + sent_at por regra
```

## Prompts

| Arquivo | Trigger | Finalidade |
|---|---|---|
| `prompts/alerta_manha.md` | Cron 07:00 | Saldo atual + contas vencendo hoje |
| `prompts/alerta_tarde.md` | Cron 18:00 | Resumo do dia + projeção 7 dias |
| `prompts/proactive.md` | Anomalia detectada (daemon) | Formatar notificação proativa curta |
| `prompts/categorizacao.md` | Ad-hoc | Categorizar lançamentos novos |
| `prompts/doctor.md` | Ad-hoc | Narrativa do health check |

## Estrutura de Logs e Memória

```
~/.agente-cfo/
├── logs/
│   ├── cfo-reporter.log
│   ├── omie-pull-wrapper.log
│   ├── check-budget.log
│   ├── whatsapp-watch.log
│   ├── heartbeat.log
│   ├── doctor.log
│   ├── repare.log
│   └── proactive.log
├── memory/               # chmod 700 — memória local do agente (nunca vai ao painel)
│   ├── empresa.md        # fatos sobre a empresa (nome, segmento, sazonalidade)
│   ├── preferencias_dono.md
│   ├── eventos.md        # linha do tempo append-only
│   ├── decisoes.md       # decisões registradas
│   └── metricas_baseline.md
├── state/
│   └── proactive_alerts.json  # cooldown state do daemon proativo
├── cron-ids.env          # IDs dos cron jobs (escrito pelo setup.sh)
└── budget-state.json     # Acumulador de custo mensal
```

## Identidade do Agente

Os arquivos em `skills/agente-cfo/identity/` definem quem é o agente, como ele fala e
como gerencia memória. São lidos no início de cada prompt:

| Arquivo | Conteúdo |
|---|---|
| `identity/identity.md` | Nome, papel, background, especialidades, crenças operacionais |
| `identity/soul.md` | Voz, tom, linguagem permitida/proibida, guardrails, postura de suporte |
| `identity/memory.md` | Manual do sistema de memória local (`~/.agente-cfo/memory/`) |

## Setup Inicial (feito pelo setup.sh do instalador)

O setup.sh registra os crons e salva os IDs. A skill não registra crons
por conta própria — apenas documenta os comandos esperados:

```bash
# Alerta manhã
CRON_ID_MANHA=$(openclaw cron add \
  --name "CFO Alerta Manhã" \
  --cron "0 7 * * *" --tz "America/Sao_Paulo" \
  --session isolated \
  --message "Execute: bash ~/.openclaw/workspace/skills/agente-cfo/scripts/cfo-reporter.sh ~/.openclaw/workspace/skills/agente-cfo/prompts/alerta_manha.md" \
  --no-deliver --json | jq -r '.id')

# Alerta tarde
CRON_ID_TARDE=$(openclaw cron add \
  --name "CFO Alerta Tarde" \
  --cron "0 18 * * *" --tz "America/Sao_Paulo" \
  --session isolated \
  --message "Execute: bash ~/.openclaw/workspace/skills/agente-cfo/scripts/cfo-reporter.sh ~/.openclaw/workspace/skills/agente-cfo/prompts/alerta_tarde.md" \
  --no-deliver --json | jq -r '.id')

# Salvar IDs
echo "CRON_ID_MANHA=${CRON_ID_MANHA}" > ~/.agente-cfo/cron-ids.env
echo "CRON_ID_TARDE=${CRON_ID_TARDE}" >> ~/.agente-cfo/cron-ids.env
```
