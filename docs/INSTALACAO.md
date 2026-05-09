# Instalação — Agente CFO

Este guia cobre dois caminhos: o **fluxo recomendado** (via painel Lovable com onboarding guiado) e o **fluxo alternativo** (setup.sh manual na VPS, sem interface).

---

## Pré-requisitos

Antes de começar, tenha em mãos:

| Item | Detalhe |
|---|---|
| **VPS Linux** | Ubuntu 22.04+ mínimo. 1 vCPU / 1 GB RAM é suficiente. |
| **Acesso root/sudo** | O setup.sh instala dependências do sistema. |
| **Conta Lovable** | Gratuita em [lovable.dev](https://lovable.dev). Para hospedar o painel e o banco Supabase. |
| **Conta Anthropic** | Para gerar a API Key em [console.anthropic.com](https://console.anthropic.com). |
| **ERP com API ativa** | Omie, Bling, Tiny, Granatum, VHSYS, Nibo ou ContaAzul. Veja [INTEGRACOES.md](INTEGRACOES.md) para como gerar as credenciais. |
| **CRM (opcional)** | HubSpot, RD Station CRM, PipeRun ou Pipedrive. |
| **Número WhatsApp dedicado** | Recomendado um chip exclusivo para os alertas do Marcos. O número não pode estar logado em outro dispositivo durante o setup. |

---

## Fluxo 1 — Recomendado: Painel Lovable + Onboarding Guiado

O painel guia você pelas 8 etapas com validações em cada passo.

### Etapa 1 — Duplicar o template no Lovable

1. Acesse o template e clique em **"Use this Template"**:  
   [![Open in Lovable](https://lovable.dev/button.svg)](https://lovable.dev/projects/ddcd382f-f68a-478d-a2a5-811a860ba83c)
2. O Lovable cria um projeto na sua conta com um banco Supabase vinculado automaticamente.
3. Anote a URL do projeto Supabase: aparece em **Supabase → Settings → API** no formato  
   `https://<ref>.supabase.co`

**Como verificar:** O painel carrega e exibe a tela de onboarding em `/onboarding`.

---

### Etapa 2 — Aplicar as migrations do banco

As migrations criam as tabelas de eventos, instâncias e configurações.

**Opção A — Via SQL Editor do Supabase (mais simples):**

1. Abra **Supabase → SQL Editor**
2. Execute os arquivos de `painel/supabase/migrations/` em ordem numérica:
   - `001_initial_schema.sql`
   - `002_events.sql`
   - etc.

**Opção B — Via CLI do Supabase:**

```bash
cd painel/
supabase link --project-ref <project_ref>
supabase db push
```

**Como verificar:** As tabelas `instances`, `events` e `configs` aparecem em Supabase → Table Editor.

---

### Etapa 3 — Configurar credenciais no painel

No painel, acesse `/onboarding` e preencha:

- **Anthropic API Key** — formato `sk-ant-...`
- **Número WhatsApp** — formato `+55119XXXXXXXX` (E.164)
- **ERP e credenciais** — veja [INTEGRACOES.md](INTEGRACOES.md) para cada sistema
- **CRM e credenciais** — opcional
- **Orçamento LLM** — em R$, quanto pode gastar por mês com a Anthropic

---

### Etapa 4 — Preparar a VPS

Acesse sua VPS via SSH e certifique-se de que o sistema está atualizado:

```bash
sudo apt update && sudo apt upgrade -y
```

---

### Etapa 5 — Rodar o instalador

O painel exibe o comando de instalação personalizado com suas variáveis já preenchidas. Algo como:

```bash
ANTHROPIC_API_KEY=sk-ant-... \
CFO_WHATSAPP_TO=+55119... \
CFO_ERP_NAME=omie \
OMIE_APP_KEY=... \
OMIE_APP_SECRET=... \
PANEL_BASE_URL=https://<ref>.supabase.co/functions/v1 \
NONINTERACTIVE=1 \
bash <(curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh)
```

O setup.sh:
1. Instala OpenClaw, `wacli`, `cloudflared`
2. Gera o `PANEL_TOKEN` e pausa pedindo que você o configure no Supabase
3. Instala as skills do monorepo
4. Cria os services systemd (`wacli-inbound`, `cfo-proactive`)
5. Registra os cron jobs de alerta (07:00 e 18:00)
6. Roda o diagnóstico final (`doctor.sh`)

**Duração média:** 5–10 minutos numa VPS limpa.

---

### Etapa 6 — Configurar o PANEL_TOKEN no Supabase

O setup.sh gera um `PANEL_TOKEN` aleatório e pausa. Você precisa:

1. Ir em **Supabase → Settings → Edge Functions → Secrets**
2. Clicar em **"Add new secret"**
3. Nome: `PANEL_TOKEN` / Valor: o token exibido no terminal
4. Salvar e pressionar **Enter** no terminal para continuar

**Como verificar:** O terminal exibe `[OK] PANEL_TOKEN configurado no Supabase.`

---

### Etapa 7 — Parear o WhatsApp

O setup.sh exibe um QR code no terminal. Use o WhatsApp **do número dedicado**:

1. Abra o WhatsApp → três pontos → **Aparelhos conectados**
2. Escaneie o QR code

> **Atenção:** O QR expira em ~20 segundos. Se expirar, o setup exibe um novo automaticamente.

**Como verificar:** O terminal exibe `[OK] WhatsApp pareado.`

---

### Etapa 8 — Verificar o setup completo

Ao fim do setup, o `doctor.sh` roda automaticamente. Você deve ver:

```
✅ OpenClaw: rodando
✅ wacli: pareado
✅ ERP: API acessível
✅ Cron jobs: 2 registrados
✅ Tunnel: ativo (https://xxx.trycloudflare.com)
✅ Painel: registrado
```

Qualquer `❌` indica um problema. Veja [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Para rodar o diagnóstico manualmente a qualquer momento:

```bash
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/doctor.sh
```

---

## Fluxo 2 — Alternativo: Setup Manual (sem painel)

Use este fluxo se preferir não usar o Lovable ou quiser automatizar via CI.

```bash
# 1. SSH na VPS
ssh root@<seu-ip>

# 2. Exportar variáveis manualmente
export ANTHROPIC_API_KEY="sk-ant-..."
export CFO_WHATSAPP_TO="+55119XXXXXXXX"
export CFO_ERP_NAME="omie"
export OMIE_APP_KEY="..."
export OMIE_APP_SECRET="..."
export PANEL_BASE_URL="https://<ref>.supabase.co/functions/v1"
export LLM_BUDGET_BRL="50"

# 3. Rodar o instalador interativo
bash <(curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh)
```

Neste modo o setup pergunta interativamente o que não estiver nos env vars.

**Limitações sem painel:**
- Sem histórico de eventos visuais
- Sem dashboard de uso de tokens
- O PANEL_TOKEN ainda é necessário para que as edge functions aceitem as requisições — se não tiver Supabase, as chamadas ao painel simplesmente falham silenciosamente (não travam o agente)

---

## Atualização

Para atualizar as skills para a versão mais recente do monorepo:

```bash
# Reinstalar skill agente-cfo e dependências
bash <(curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh)
```

O setup.sh é idempotente — pula o que já está instalado e atualiza apenas o necessário.

---

## Próximos passos

- [INTEGRACOES.md](INTEGRACOES.md) — como gerar credenciais em cada ERP/CRM
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — o setup abortou? Consulte aqui
- [FAQ.md](FAQ.md) — dúvidas frequentes
