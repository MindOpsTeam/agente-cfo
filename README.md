# 🤖 Agente CFO — Marcos

**CFO virtual 24/7 brasileiro — rode na sua infra em 15 minutos**

[![Template gratuito](https://img.shields.io/badge/template-gratuito-brightgreen?logo=lovable)](https://lovable.dev)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-nativo-25D366?logo=whatsapp)](https://wa.me)
[![Open Source](https://img.shields.io/badge/open--source-MIT-blue)](LICENSE)
[![Brasil](https://img.shields.io/badge/feito_no-Brasil-009c3b)](https://github.com/MindOpsTeam/agente-cfo)

---

## Remixar no Lovable

> **→ [Clique aqui para remixar o template e ter seu próprio Marcos](https://lovable.dev)**

---

## O que é

**Marcos** é seu CFO virtual. Ele vive na sua VPS, responde via WhatsApp, Telegram e chat web com dados reais do seu ERP, CRM, cobrança e e-commerce — 24/7, sem você abrir planilha.

```
Você (WA): "Quanto tenho a receber essa semana?"
Marcos:    "R$ 12.400 em 3 clientes. Maior vencimento: Acme em 23/05 (R$ 8.200).
            Risco: Acme tem histórico de atraso 🟡."

Você:      "Gastei R$150 com Uber"
Marcos:    "Entendi — R$150 pago pra Uber, categoria Transporte, hoje.
            Confirma? (SIM/NÃO)"
Você:      "SIM"
Marcos:    "✅ Lançado no Omie (id=4823)."
```

---

## Como funciona (4 passos, ~15 min)

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Remix        │  2. Onboarding   │  3. VPS Setup   │ 4. Use │
│  No Lovable      │  No painel       │  1 comando      │        │
│  cria seu painel │  ERP + WA + key  │  aguarda 5 min  │ pronto │
└─────────────────────────────────────────────────────────────────┘
```

1. **Remix** — clique no botão acima, crie seu painel Lovable em 1 minuto
2. **Onboarding** — configure ERP, WhatsApp e chave Anthropic no wizard visual
3. **Instale na VPS** — cole o comando gerado (1 linha) e aguarde ~5 min
4. **Converse com Marcos** — no WhatsApp, Telegram ou chat web

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Agente LLM | Claude Sonnet 4.6 via Anthropic API |
| Orquestrador | [OpenClaw](https://openclaw.ai) |
| Protocolo ferramentas | MCP (Model Context Protocol) |
| Backend | Supabase (PostgreSQL + Edge Functions + Realtime) |
| Frontend | React + Vite + TanStack Router (Lovable) |
| Canais | WhatsApp (Evolution API + wacli) · Telegram Bot API |
| Infra cliente | VPS Ubuntu 22.04+ (qualquer provedor) |

---

## Skills disponíveis (25 skills CFO)

### Dados em tempo real (17 MCPs, 1.372 tools)
| Categoria | Skills |
|-----------|--------|
| **ERP** | Omie · Bling · Tiny · Granatum · VHSYS · Nibo · ContaAzul |
| **CRM** | HubSpot · Pipedrive · PipeRun · Kommo · RD Station |
| **Cobrança** | Asaas · Iugu |
| **E-commerce** | Mercado Livre · Nuvemshop |
| **Banco de dados** | Supabase (multi-projeto) |

### Análise & Planejamento (14 skills PhD)
| Skill | Capacidade |
|-------|-----------|
| `cfo-analise-estrategica` | DRE, margens, KPIs (DSO/DPO/CCC), vertical/horizontal |
| `cfo-projecao` | Runway, burn rate, cenários otimista/realista/pessimista |
| `cfo-inadimplencia` | Aging, top devedores, plano de cobrança priorizado |
| `cfo-anomalias` | Z-score de despesas, concentração de clientes |
| `cfo-tributacao-br` | Calendário fiscal BR (DAS/FGTS/IRPJ/13º) |
| `cfo-cobranca-orquestrada` | Workflow de cobrança em lote com confirmação |
| `cfo-relatorios-executivos` | Relatório semanal/mensal com recomendações |
| `cfo-planejamento` | Planos de ação com milestones semanais |
| `cfo-cenarios-nomeados` | Cenários salvos e comparados lado-a-lado |
| `cfo-what-if` | Simulador "e se?" mês-a-mês + varredura de ponto ótimo |
| `cfo-calendario-acoes` | Calendário acionável: fiscal + cobrança + pagamentos |
| `cfo-sensitivity` | Análise de sensibilidade — qual variável tem mais alavanca |
| `cfo-decisao-estrategica` | 2-3 alternativas + tradeoffs + recomendação explícita |
| `cfo-conciliacao-*` | Conciliação cross-sistema (cobrança/ecommerce/CRM/banco) |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                   Painel Web (Lovable)                   │
│              chat · relatórios · configurações           │
└────────────────────────┬────────────────────────────────┘
                         │ Supabase (PostgreSQL + Realtime)
┌────────────────────────▼────────────────────────────────┐
│              VPS do Cliente (Ubuntu 22.04+)              │
│                                                         │
│  OpenClaw Gateway ← webhooks Evolution API / Telegram   │
│       │                                                  │
│       ▼                                                  │
│  Marcos (Claude Sonnet 4.6)                             │
│       │                                                  │
│       ├─→ MCP: Omie (96 tools)                          │
│       ├─→ MCP: HubSpot (463 tools)                      │
│       ├─→ MCP: Asaas (33 tools)                         │
│       ├─→ ... 14 outros MCPs                            │
│       │                                                  │
│  9 daemons systemd (heartbeat, sync, alerts, ...)       │
└─────────────────────────────────────────────────────────┘
```

---

## Custos mensais estimados

| Item | Custo estimado |
|------|---------------|
| VPS (Hetzner CX22) | €5/mês (~R$30) |
| Anthropic API (uso moderado) | ~R$30–80 |
| Lovable (free tier) | Grátis |
| **Total** | **~R$60–110/mês** |

---

## Pré-requisitos

- Conta Anthropic com API key (`sk-ant-...`)
- VPS Ubuntu 22.04+ com 1 vCPU e 1 GB RAM
- ERP com API ativa (Omie recomendado para começar)
- Número WhatsApp (chip dedicado recomendado)

### VPS recomendadas

| Provedor | Plano | Preço |
|----------|-------|-------|
| [Hetzner](https://hetzner.com/cloud) | CX22 (2 vCPU / 4 GB) | €4,35/mês |
| [DigitalOcean](https://digitalocean.com) | Droplet Basic 2 GB | $12/mês |
| [Hostinger](https://hostinger.com.br/vps) | VPS 1 | R$24/mês |

---

## Licença

MIT — você é dono do código, dos dados e da infra.

---

## Contribuir

PRs bem-vindos. Veja [SPRINTS.md](docs/SPRINTS.md) para o roadmap.

Comunidade: [Viver de IA](https://viverdeia.ai)
