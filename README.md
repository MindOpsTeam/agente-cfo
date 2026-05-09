# Agente CFO

> CFO virtual para PME brasileira — alertas financeiros no WhatsApp, sem planilha, sem dashboard para abrir.

[![10 integrações](https://img.shields.io/badge/integrações-10%20ERPs%2FCRMs-blue)](#integrações-suportadas)
[![Template gratuito](https://img.shields.io/badge/template-gratuito-green)](https://lovable.dev/projects/ddcd382f-f68a-478d-a2a5-811a860ba83c)

Conecta o **ERP/CRM** da empresa ao **WhatsApp** do dono via **OpenClaw**, gerando insights de fluxo de caixa e alertas proativos sem intervenção manual.

**Template gratuito de cópia** — distribuído para alunos da plataforma [Viver de IA](https://viverdeia.ai). Cada cliente roda na infra dele: VPS própria, Supabase próprio (via Lovable Cloud), Anthropic key própria.

---

## O que o Agente CFO faz

- **07:00** — Resumo matinal: saldo atual, contas a receber hoje, contas a pagar hoje, inadimplência, projeção de caixa 30 dias
- **18:00** — Fechamento do dia + projeção 7 dias + pipeline CRM (se configurado)
- **Alertas proativos** automáticos: caixa baixo, inadimplência alta, pipeline em queda, deals parados
- **Conversa via WhatsApp** — responde perguntas financeiras em linguagem natural ("qual meu saldo?", "quem vence hoje?")
- **Painel web** (Lovable Cloud) com histórico de eventos, uso de tokens e push de comandos para a VPS

## Documentação

| Doc | Conteúdo |
|---|---|
| [docs/INSTALACAO.md](docs/INSTALACAO.md) | Onboarding passo a passo — painel Lovable ou setup manual |
| [docs/INTEGRACOES.md](docs/INTEGRACOES.md) | Como conectar cada ERP e CRM (credenciais, capacidades, limitações) |
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

Todas as skills ERP expõem a mesma interface (`get_balance`, `list_payables`, `list_receivables`, `list_overdue`, `get_cash_projection`, `company_info`).
Skills CRM expõem `list_deals`, `pipeline_summary`, `get_pipeline_projection`, `company_info`.

O `setup.sh` pergunta qual ERP e CRM usar e configura automaticamente.

---

## Pré-requisitos

| Item | Detalhe |
|---|---|
| VPS Linux | Ubuntu 22.04+, mínimo 1 vCPU / 1 GB RAM |
| ERP | Conta em um dos ERPs suportados (Omie, Bling, Tiny, Granatum, VHSYS, Nibo ou ContaAzul) |
| CRM (opcional) | Conta em HubSpot, RD Station CRM, PipeRun ou Pipedrive |
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
│   ├── nibo/                # Nibo (Premium)
│   ├── contaazul/           # ContaAzul ERP (OAuth 2.0)
│   ├── hubspot/             # HubSpot CRM
│   ├── rd-station/          # RD Station CRM
│   ├── piperun/             # PipeRun CRM
│   └── pipedrive/           # Pipedrive CRM
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

## Licença

MIT — faça o que quiser, sem garantias.
