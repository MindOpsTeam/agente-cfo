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
            curl → PANEL_WEBHOOK_URL (painel central)
```

## Variáveis de Ambiente Requeridas

| Variável | Descrição | Exemplo |
|---|---|---|
| `OMIE_APP_KEY` | App Key da integração Omie | `12345678901` |
| `OMIE_APP_SECRET` | App Secret da integração Omie | `abc123def456...` |
| `CFO_WHATSAPP_TO` | Número destino dos alertas (E.164) | `+5511999999999` |
| `LICENSE_KEY` | Chave de licença do produto | `lk_prod_xxx` |
| `TENANT_ID` | Identificador do cliente no painel | `empresa-abc` |
| `LLM_BUDGET_BRL` | Teto mensal de custo LLM em BRL | `50` |

## Variáveis Opcionais

| Variável | Descrição | Padrão |
|---|---|---|
| `PANEL_WEBHOOK_URL` | URL do painel central para telemetria | _(vazio — tolerado)_ |
| `OMIE_SKILL_PATH` | Path absoluto da skill omie | `~/.openclaw/workspace/skills/omie` |
| `CFO_LOG_DIR` | Diretório de logs | `~/.agente-cfo/logs` |
| `CFO_STATE_DIR` | Diretório de estado (budget, cron-ids) | `~/.agente-cfo` |
| `LLM_INPUT_PRICE_BRL` | Preço por 1M tokens input em BRL | `9.50` |
| `LLM_OUTPUT_PRICE_BRL` | Preço por 1M tokens output em BRL | `47.50` |

## Ferramentas Expostas pela Skill

### 1. `doctor.sh` — Diagnóstico do sistema
```bash
bash skills/agente-cfo/scripts/doctor.sh
```
Testa: WhatsApp pareado, Omie acessível, LICENSE_KEY presente, webhook receiver rodando.
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

## Cron Jobs (registrados pelo setup.sh)

Os IDs dos crons são salvos em `~/.agente-cfo/cron-ids.env` pelo instalador:

```bash
# ~/.agente-cfo/cron-ids.env (gerado pelo setup.sh)
CRON_ID_MANHA=abc123
CRON_ID_TARDE=def456
CRON_ID_BUDGET=ghi789
CRON_ID_WATCHER=jkl012
```

O `check-budget.sh` lê esse arquivo para pausar/retomar os crons via `openclaw cron disable/enable`.

## Prompts

| Arquivo | Trigger | Finalidade |
|---|---|---|
| `prompts/alerta_manha.md` | Cron 07:00 | Saldo atual + contas vencendo hoje |
| `prompts/alerta_tarde.md` | Cron 18:00 | Resumo do dia + projeção 7 dias |
| `prompts/categorizacao.md` | Ad-hoc | Categorizar lançamentos novos |
| `prompts/doctor.md` | Ad-hoc | Narrativa do health check |

## Estrutura de Logs

```
~/.agente-cfo/
├── logs/
│   ├── cfo-reporter.log
│   ├── omie-pull-wrapper.log
│   ├── check-budget.log
│   ├── whatsapp-watch.log
│   ├── doctor.log
│   └── repare.log
├── cron-ids.env          # IDs dos cron jobs (escrito pelo setup.sh)
└── budget-state.json     # Acumulador de custo mensal
```

## Setup Inicial (feito pelo setup.sh do instalador)

O setup.sh do instalador registra os crons e salva os IDs. A skill não registra crons
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
