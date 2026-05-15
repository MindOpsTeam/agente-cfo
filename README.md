# Agente CFO

**Marcos**, seu CFO virtual brasileiro — responde via WhatsApp, Telegram e painel web com dados reais do seu ERP, CRM e cobrança. Sem planilha, sem dashboard, sem contratar pessoa.

---

## O que é

- Conecta ERPs, CRMs, cobrança e e-commerce via **1.279 ferramentas MCP**
- Marcos responde via **chat web, WhatsApp e Telegram** — mesmo contexto em todos os canais
- **Plug-and-play**: configura tudo pelo painel, zero SSH após onboarding inicial
- **Auto-recovery**: daemons se recuperam sozinhos quando algo falha
- **Alertas configuráveis**: avisa quando daemon cai, custo ultrapassa budget, taxa de erro sobe
- **Open-source** — você é dono da infra, dados ficam na sua VPS + Supabase

## Para quem

PMEs brasileiras que querem um CFO 24/7 que entende contabilidade, cobrança, vendas e e-commerce — sem contratar pessoa física.

---

## Quickstart (5 min)

```bash
# 1. Crie conta no painel
# https://carteira-do-agente.lovable.app

# 2. Cole na sua VPS (Ubuntu 22.04+)
curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh | bash

# 3. Painel → /integrations → conecta ERP/CRM → pronto
```

---

## Como funciona

```
┌─────────────────────────────────────────────────────────────────┐
│                          PAINEL WEB                             │
│  (Supabase + React, Lovable Cloud)                              │
│  /chat  /integrations  /automations  /settings  /alerts        │
└────────────────────────────────┬────────────────────────────────┘
                                 │ HTTPS / WebSocket
         ┌───────────────────────▼────────────────────────┐
         │                   VPS LINUX                    │
         │                                                │
         │  ┌─────────────────────────────────────────┐   │
         │  │         OpenClaw Gateway                │   │
         │  │   (agente Marcos · Claude Sonnet 4.6)   │   │
         │  └──────────────────┬──────────────────────┘   │
         │                     │ MCP stdio                 │
         │  ┌──────────────────▼──────────────────────┐   │
         │  │    17 MCP servers (1.279 tools)         │   │
         │  │  Omie · Bling · HubSpot · Asaas · ...  │   │
         │  └──────────────────┬──────────────────────┘   │
         │                     │                           │
         │  ┌──────────────────▼──────────────────────┐   │
         │  │           Daemons CFO (14)               │   │
         │  │  credentials-sync  ·  automation-engine  │   │
         │  │  evolution-sync    ·  telegram-sync      │   │
         │  │  metrics-publisher ·  alerts-checker     │   │
         │  │  health-doctor     ·  mcp-warmer         │   │
         │  └──────────────────┬──────────────────────┘   │
         │                     │ Cloudflare Tunnel          │
         └─────────────────────┼──────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
           WhatsApp        Telegram         APIs ERP
        (Evolution API)  (Bot API)        CRM · Cobrança
```

---

## Integrações (17 skills · 1.279 tools)

| Categoria | Skills |
|-----------|--------|
| ERP | Omie, Bling, Tiny, Granatum, VHSYS, Nibo, ContaAzul |
| CRM | HubSpot, RD Station, PipeRun, Pipedrive, Kommo |
| Cobrança | Asaas, Iugu |
| E-commerce | Mercado Livre, Nuvemshop |
| Database | Supabase (multi-projeto via painel) |

---

## Automações

Configure via painel ou chat com Marcos:

| Trigger | Exemplo |
|---------|---------|
| Cron | Relatório semanal às 9h toda segunda |
| Métrica | Caixa < R$ 50k → alerta imediato |
| Manual | "Marcos, cobra todos os inadimplentes" |

---

## Daemons (infra da VPS)

| Serviço | Função | Intervalo |
|---------|--------|-----------|
| `openclaw-gateway` | Agente Marcos (LLM + MCP) | always |
| `cloudflared-cfo` | Tunnel Cloudflare | always |
| `cfo-automation-engine` | Executa automações | 5min |
| `cfo-credentials-sync` | Materializa secrets do painel | 3min |
| `cfo-evolution-sync` | Sync instâncias WhatsApp | 30s |
| `cfo-telegram-sync` | Registro de webhooks Telegram | 30s |
| `cfo-supabase-sync` | MCP servers de projetos Supabase | 5min |
| `cfo-mcp-warmer` | Pre-warm MCPs (reduz latência) | 10min |
| `cfo-metrics-publisher` | Publica métricas pro painel | 60s |
| `cfo-alerts-checker` | Avalia alertas configuráveis | 60s |
| `cfo-health-doctor` | Auto-recovery de daemons | 60s |

---

## Documentação

| Doc | Descrição |
|-----|-----------|
| [docs/CLIENTE.md](docs/CLIENTE.md) | Guia do dono (sem jargão) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitetura detalhada |
| [docs/SPRINTS.md](docs/SPRINTS.md) | Histórico de entregas |
| [docs/mcps.md](docs/mcps.md) | 17 integrações com tool count |
| [docs/channels.md](docs/channels.md) | Pipeline WhatsApp/Telegram/Painel |
| [docs/admin-actions.md](docs/admin-actions.md) | Controle via painel (21 ações) |
| [docs/metrics.md](docs/metrics.md) | Observabilidade |
| [docs/backup-restore.md](docs/backup-restore.md) | Backup e restore de config |
| [docs/memory-portability.md](docs/memory-portability.md) | Export/import de memória |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Problemas comuns |
| [docs/openclaw-ws.md](docs/openclaw-ws.md) | Protocolo WebSocket do gateway |

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | TanStack Start + React + Tailwind (Lovable Cloud) |
| Backend | Supabase (PostgreSQL + Edge Functions + Realtime + Storage) |
| Agente | OpenClaw + Claude Sonnet 4.6 (Anthropic) |
| MCPs | Python 3.12 / stdio (17 servers, 1.279 tools) |
| Mensageria WA | Evolution API (multi-instância) |
| Mensageria TG | Telegram Bot API |
| Infra VPS | Ubuntu 22.04+ + systemd (14 units) |
| Tunnel | Cloudflare quick tunnel |

---

## Self-update (zero SSH)

```bash
# Via painel: Configurações → Sistema → "Atualizar VPS"
# Ou Marcos faz por você quando pedido

# Manual (se necessário):
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/self_update.sh
```

---

## Licença

Código MIT. Cada instância é independente — você é dono da sua infra, dados e credenciais.
