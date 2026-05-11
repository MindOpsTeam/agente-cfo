# Agente CFO

> CFO virtual para PME brasileira — alertas financeiros no WhatsApp, sem planilha, sem dashboard para abrir.

[![v1.0.0](https://img.shields.io/badge/versão-v1.0.0-brightgreen)](https://github.com/MindOpsTeam/agente-cfo/releases/tag/v1.0.0)
[![14 integrações](https://img.shields.io/badge/integrações-14%20ERPs%2FCRMs%2FCobrança%2FEcommerce-blue)](#integrações-suportadas)
[![Template gratuito](https://img.shields.io/badge/template-gratuito-green)](https://lovable.dev/projects/ddcd382f-f68a-478d-a2a5-811a860ba83c)

> 🚀 **Quer instalar?** → Acesse o painel e siga o onboarding guiado: [lovable.dev/projects/ddcd382f-f68a-478d-a2a5-811a860ba83c](https://lovable.dev/projects/ddcd382f-f68a-478d-a2a5-811a860ba83c)
>
> 📖 **Cliente Viver de IA?** → Leia o [docs/CLIENTE.md](docs/CLIENTE.md) — guia plug-n-play sem jargão técnico.

---

> **v1.0 — template sem suporte dedicado e sem atualizações automáticas.** Distribuído como parte do catálogo gratuito da [Viver de IA](https://viverdeia.ai). Cada instalação é independente — você é dono da sua infra.

Conecta o **ERP/CRM** da empresa ao **WhatsApp** do dono via **OpenClaw**, gerando insights de fluxo de caixa e alertas proativos sem intervenção manual.

**Template gratuito de cópia** — distribuído para alunos da plataforma [Viver de IA](https://viverdeia.ai). Cada cliente roda na infra dele: VPS própria, Supabase próprio (via Lovable Cloud), Anthropic key própria.

---

---

## O que o Agente CFO faz

- **07:00** — Resumo matinal: saldo atual, contas a receber hoje, contas a pagar hoje, inadimplência, projeção de caixa 30 dias
- **18:00** — Fechamento do dia + projeção 7 dias + pipeline CRM (se configurado)
- **Alertas proativos** automáticos: caixa baixo, inadimplência alta, pipeline em queda, deals parados, estoque baixo, queda nas vendas, pedidos não enviados
- **Cobrança ativa** de clientes inadimplentes via WhatsApp — com confirmação obrigatória do dono
- **Conversa via WhatsApp** — responde perguntas financeiras em linguagem natural ("qual meu saldo?", "quem vence hoje?")
- **Painel web** (Lovable Cloud) com histórico de eventos, uso de tokens e push de comandos para a VPS

## Documentação

| Doc | Conteúdo |
|---|---|
| [docs/CLIENTE.md](docs/CLIENTE.md) | **Guia do cliente** — plug-n-play, sem jargão técnico |
| [docs/INSTALACAO.md](docs/INSTALACAO.md) | Onboarding passo a passo — painel Lovable ou setup manual |
| [docs/INTEGRACOES.md](docs/INTEGRACOES.md) | Como conectar cada ERP, CRM, cobrança e e-commerce |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | WhatsApp não pareia? Gateway não sobe? Resolva aqui |
| [docs/FAQ.md](docs/FAQ.md) | Perguntas frequentes — custos, segurança, dados, backups |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Visão técnica: stack, diagramas de fluxo, BaseERPClient |

---

## Integrações suportadas

| Tipo | Sistema | Auth | Skill |
|------|---------|------|-------|
| ERP | **Omie** | App Key + Secret | [`skills/omie`](skills/omie/SKILL.md) |
| ERP | **Bling** | OAuth 2.0 (refresh automático) | [`skills/bling`](skills/bling/SKILL.md) |
| ERP | **Tiny** | Token API v2 | [`skills/tiny`](skills/tiny/SKILL.md) |
| ERP | **Granatum** | Access Token | [`skills/granatum`](skills/granatum/SKILL.md) |
| ERP | **VHSYS** | Access Token + Secret Token | [`skills/vhsys`](skills/vhsys/SKILL.md) |
| ERP | **Nibo** | API Token (plano Premium) | [`skills/nibo`](skills/nibo/SKILL.md) |
| ERP | **ContaAzul** | OAuth 2.0 (refresh automático) | [`skills/contaazul`](skills/contaazul/SKILL.md) |
| CRM | **HubSpot** | Private App Token | [`skills/hubspot`](skills/hubspot/SKILL.md) |
| CRM | **RD Station CRM** | Token de integração | [`skills/rd-station`](skills/rd-station/SKILL.md) |
| CRM | **PipeRun** | Token | [`skills/piperun`](skills/piperun/SKILL.md) |
| CRM | **Pipedrive** | API Token + subdomínio | [`skills/pipedrive`](skills/pipedrive/SKILL.md) |
| Cobrança | **Asaas** | API Token (header) | [`skills/asaas`](skills/asaas/SKILL.md) |
| Cobrança | **Iugu** | API Token (Basic Auth) | [`skills/iugu`](skills/iugu/SKILL.md) |
| E-commerce | **Mercado Livre** | OAuth 2.0 (refresh automático) | [`skills/mercado-livre`](skills/mercado-livre/SKILL.md) |
| E-commerce | **Nuvemshop** | OAuth 2.0 (token long-lived) | [`skills/nuvemshop`](skills/nuvemshop/SKILL.md) |

Interfaces uniformes por categoria:
- **ERP:** `get_balance`, `list_payables`, `list_receivables`, `list_overdue`, `get_cash_projection`, `company_info`
- **CRM:** `list_deals`, `pipeline_summary`, `get_pipeline_projection`, `company_info`
- **Cobrança:** `list_invoices`, `get_invoice`, `get_customer`, `get_overdue_customers`, `send_payment_link`, `create_invoice`, `cancel_invoice`
- **E-commerce:** `list_orders`, `get_order`, `list_products`, `get_low_stock`, `get_sales_metrics`, `update_stock`, `mark_order_shipped`

O `setup.sh` pergunta qual ERP e CRM usar e configura automaticamente.

---

## Pré-requisitos

| Item | Detalhe |
|---|---|
| VPS Linux | Ubuntu 22.04+, mínimo 1 vCPU / 1 GB RAM |
| ERP | Conta em um dos ERPs suportados (Omie, Bling, Tiny, Granatum, VHSYS, Nibo ou ContaAzul) |
| CRM (opcional) | Conta em HubSpot, RD Station CRM, PipeRun ou Pipedrive |
| Cobrança (opcional) | Conta em Asaas ou Iugu |
| E-commerce (opcional) | Conta no Mercado Livre ou Nuvemshop |
| WhatsApp | Número dedicado para os alertas |
| Anthropic | API Key (`sk-ant-...`) |
| Lovable Cloud | Conta gratuita em [lovable.dev](https://lovable.dev) |

---

## Instalação

### 1. Abrir o painel no Lovable Cloud

Clique em **"Use this Template"** para duplicar o painel para a sua conta Lovable:

[![Open in Lovable](https://lovable.dev/button.svg)](https://lovable.dev/projects/ddcd382f-f68a-478d-a2a5-811a860ba83c)

O Lovable vai criar um projeto com o painel já configurado e um projeto Supabase vinculado.

### 2. Aplicar as migrations no Supabase

No painel do Lovable, vá em **Supabase → SQL Editor** e aplique os arquivos em `painel/supabase/migrations/` em ordem numérica.

Ou use a CLI:
```bash
cd painel/
supabase link --project-ref <project_ref>
supabase db push
```

### 3. Rodar o instalador na VPS

```bash
curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh | bash
```

O instalador vai:
1. Instalar OpenClaw, wacli e cloudflared
2. Coletar suas credenciais (ERP, WhatsApp, Anthropic)
3. **Gerar um `PANEL_TOKEN`** e pausar para você configurá-lo como secret no Supabase
4. Parear o WhatsApp (QR code no terminal)
5. Subir um Cloudflare Tunnel para o painel enviar comandos para a VPS
6. Registrar os cron jobs de alerta (07:00 e 18:00)
7. Rodar o diagnóstico final (`doctor.sh`)

> Guia completo com pré-requisitos, etapas e verificações: **[docs/INSTALACAO.md](docs/INSTALACAO.md)**

---

## Estrutura do repositório

```
agente-cfo/
├── skills/
│   ├── _lib/               # Lib comum (BaseERPClient, BaseCRMClient, HTTP, schemas)
│   ├── _template/           # Template para novas skills
│   ├── agente-cfo/          # Skill principal (roda na VPS do cliente)
│   │   ├── SKILL.md
│   │   ├── prompts/         # Templates dos alertas WhatsApp
│   │   └── scripts/         # erp_gateway.py, crm_gateway.py, cfo-reporter.sh
│   ├── omie/                # Omie ERP
│   ├── bling/               # Bling ERP (OAuth 2.0)
│   ├── tiny/                # Tiny ERP
│   ├── granatum/            # Granatum
│   ├── vhsys/               # VHSYS ERP
│   ├── nibo/                # Nibo ERP (Premium)
│   ├── contaazul/           # ContaAzul ERP (OAuth 2.0)
│   ├── hubspot/             # HubSpot CRM
│   ├── rd-station/          # RD Station CRM
│   ├── piperun/             # PipeRun CRM
│   ├── pipedrive/           # Pipedrive CRM
│   ├── asaas/               # Asaas — cobrança (Pix/Boleto)
│   ├── iugu/                # Iugu — cobrança
│   ├── mercado-livre/       # Mercado Livre e-commerce (OAuth 2.0)
│   └── nuvemshop/           # Nuvemshop e-commerce (OAuth 2.0)
├── painel/
│   └── supabase/
│       ├── migrations/     # Schema do banco (single-tenant)
│       └── functions/      # Edge functions (Deno/TypeScript)
│           ├── instance-register/
│           ├── heartbeat/
│           ├── event/
│           ├── llm-usage/
│           └── push-command/
└── install/
    ├── setup.sh            # Instalador ponta-a-ponta
    └── env.example         # Referência de variáveis de ambiente
```

---

## Variáveis de ambiente (VPS)

Geradas em `~/.agente-cfo/.env` pelo `setup.sh`. Veja [`install/env.example`](install/env.example) para referência completa.

---

## Comando Central

Painel de estado da arte com KPIs unificados, projeções e insights IA.

### Como funciona

1. **dashboard-snapshot** — agrega métricas de todas as integrações ativas em paralelo, com cache de 5 min
2. **marcos_insight_generator** — roda a cada 15 min, analisa os números e gera até 8 insights via Marcos
3. **simulate-scenario** — simulação what-if: e se eu cobrar X% do inadimplente? e se fechar esses deals?

### Edge functions

| Função | Auth | Descrição |
|--------|------|-----------|
| `dashboard-snapshot` | JWT dono | Coleta e agrega KPIs de todas as skills ativas |
| `dashboard-publish-insights` | X-Panel-Token | Persiste insights gerados por Marcos |
| `simulate-scenario` | JWT dono | Simula cenários financeiros (read-only) |

### Configuração

No arquivo `~/.openclaw/secrets/agente-cfo.env`:
```
ACTIVE_SKILLS=omie,pipedrive
PANEL_BASE_URL=https://xxxxx.supabase.co
PANEL_TOKEN=seu_panel_token
HOOKS_URL=https://sua-instancia.example.com
HOOKS_TOKEN=seu_hooks_token
```

O cron `marcos_insight_generator` roda automaticamente a cada 15 minutos após o setup.

---

## Automações

O **Automation Engine** substitui as regras proativas hardcoded por automações configuráveis via painel ou chat.

### Daemon

- Path: `skills/agente-cfo/scripts/cfo_automation_engine.py`
- Intervalo: `AUTOMATION_ENGINE_INTERVAL_MIN` (default 5 min)
- Logs: `~/.agente-cfo/logs/automation-engine.log`
- State: `~/.agente-cfo/state/automation_engine.json`
- Systemd: `cfo-automation-engine.service`

### Tipos de trigger

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `cron` | Expressão cron (5 campos) | `0 9 * * 1` (segunda 9h) |
| `metric` | Dispara quando KPI ultrapassa threshold | `balance_brl < 50000` |
| `manual` | Só via botão "Run Now" no painel | — |

### Actions disponíveis

| Action | Confirmação | Descrição |
|--------|-------------|-----------|
| `send_report` | Não | Gera relatório (cash/pipeline/cobranca/dashboard) e envia via WhatsApp |
| `send_whatsapp` | Sim* | Envia mensagem WhatsApp (*não se `to=owner`) |
| `crm_update_deal` | Sim | Atualiza campos de um deal no CRM |
| `crm_create_task` | Não | Cria tarefa no CRM |
| `erp_create_invoice` | Sim | Cria conta a receber no ERP |
| `cobranca_send` | Sim | Envia cobrança (payment link ou reminder) |
| `ai_decide` | Sim | Delega decisão para Marcos via IA |

### Flow de confirmação WhatsApp

1. Engine detecta que a automação precisa de confirmação
2. Cria `automation_run` com status `pending_confirm` + `confirmation_token`
3. Envia WhatsApp: "Vou executar X. Confirma? SIM ou NÃO. [confirm:UUID]"
4. Salva token em `~/.agente-cfo/state/pending_confirm_token.txt`
5. `wacli_inbound.py` detecta resposta SIM/NÃO do dono
6. Chama edge function `automation-confirm` com token + decisão
7. Edge function atualiza status para `running` (confirma) ou `cancelled`
8. Engine detecta run com `status=running` e executa as ações
9. Runs `pending_confirm` > 24h são expirados automaticamente

### Templates disponíveis

| Template Key | Nome | Trigger |
|-------------|------|---------|
| `weekly_cash_report` | Relatório semanal de caixa | Cron: seg 9h |
| `auto_collect_overdue` | Cobrança automática inadimplentes 15d+ | Cron: diário 10h |
| `crm_update_won_deals` | Atualiza CRM quando fatura paga | Cron: */30 min |
| `stale_deals_reminder` | Lembrete deals parados +7 dias | Cron: ter 9h |
| `cash_flow_alert` | Alerta de caixa baixo | Metric: balance_brl < 50k |
| `weekly_overdue_report` | Top devedores semanal | Cron: sex 9h |

### Edge functions

| Função | Auth | Descrição |
|--------|------|-----------|
| `automations-list` | JWT dono | Lista automações + último run |
| `automations-save` | JWT dono | Cria/atualiza automação |
| `automations-delete` | JWT dono | Deleta automação e runs |
| `automations-run-now` | JWT dono | Execução manual imediata |
| `automation-confirm` | X-Panel-Token | Callback de confirmação WhatsApp |
| `automations-test` | JWT dono | Teste de automação via push-command |
| `automations-templates-list` | JWT dono | Lista templates disponíveis |

### Migração das regras antigas

O script `migrate_rules_to_automations.py` converte as 12 regras proativas em automações equivalentes:

```bash
python3 ~/.openclaw/workspace/skills/agente-cfo/scripts/migrate_rules_to_automations.py
```

Idempotente: só roda uma vez (flag `proactive_rules_migrated` no state).

Para rollback: `systemctl stop cfo-automation-engine && systemctl start cfo-proactive`

### Schema Supabase

```sql
automations(id, user_id, name, description, trigger, conditions, actions, active, require_confirmation, template_key, last_run_at, next_run_at, created_at, updated_at)
automation_runs(id, automation_id, user_id, status, trigger_payload, steps, result, error, confirmation_token, confirmation_message_id, started_at, finished_at)
```

Status de runs: `pending_confirm` | `running` | `succeeded` | `failed` | `cancelled` | `expired`

---

## Licença

MIT — faça o que quiser, sem garantias.
