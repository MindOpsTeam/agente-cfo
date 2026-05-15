# Guia do Dono — Agente CFO

**Marcos** é seu CFO virtual. Ele vive na sua VPS e responde no WhatsApp, Telegram e no chat web com dados reais do seu negócio — 24/7, sem você abrir planilha.

---

## 1. Onboarding (primeira vez)

### Pré-requisitos

| O que precisa | Onde conseguir |
|---------------|----------------|
| VPS Linux (Ubuntu 22.04+, 1 vCPU / 1 GB RAM) | DigitalOcean, Hetzner, Hostinger — ~R$30–80/mês |
| Conta Anthropic + API Key | [console.anthropic.com](https://console.anthropic.com) — ~R$30–80/mês de uso |
| ERP com API ativa | Omie, Bling, Tiny, Granatum, VHSYS, Nibo ou ContaAzul |
| Número WhatsApp dedicado (opcional) | Chip novo recomendado — não o seu número pessoal |

### Passos

1. **Crie conta no painel** em [carteira-do-agente.lovable.app](https://carteira-do-agente.lovable.app)
2. Siga o onboarding guiado (8 etapas no browser)
3. Cole o comando gerado na sua VPS — instala tudo em ~5 minutos
4. Escaneie o QR code para conectar o WhatsApp (ou configure Telegram)
5. Pronto — Marcos já está trabalhando

---

## 2. Conectar integrações via painel

**Painel → Configurações → Integrações**

Nenhuma chave precisa ir pra VPS manualmente. Você cola no painel, o daemon `cfo-credentials-sync` materializa na VPS em até 3 minutos.

### ERPs suportados

| ERP | O que Marcos consulta |
|-----|----------------------|
| Omie | Saldo, contas a pagar/receber, clientes, pedidos, NF-e, fluxo de caixa |
| Bling | Saldo, contas, pedidos, produtos, estoque |
| Tiny | Pedidos, NF-e, produtos, clientes |
| Granatum | Lançamentos, categorias, saldo |
| VHSYS | Clientes, produtos, pedidos, financeiro |
| Nibo | Contas a pagar/receber, categorias, saldo |
| ContaAzul | Clientes, produtos, pedidos, contas |

### CRMs suportados

| CRM | O que Marcos consulta |
|-----|----------------------|
| HubSpot | Deals, contatos, empresas, tickets, atividades |
| RD Station | Contatos, leads, oportunidades, funil |
| PipeRun | Deals, pipeline, atividades |
| Pipedrive | Deals, leads, pessoas, organizações |
| Kommo (amoCRM) | Leads, contatos, tarefas, pipelines |

### Cobrança

| Sistema | O que Marcos faz |
|---------|-----------------|
| Asaas | Cria cobranças (boleto/Pix/cartão), lista inadimplentes, envia lembretes |
| Iugu | Faturas, assinaturas, extrato |

---

## 3. Configurar canais de mensagem

### WhatsApp (via Evolution API)

**Painel → Configurações → WhatsApp**

1. Informe URL e API key da sua instância Evolution
2. Clique "Adicionar instância"
3. QR code aparece no painel — escaneie com o celular
4. Status vira `connected` em segundos

Você pode ter múltiplas instâncias (ex: `vendas`, `suporte`, `dono`).

### Telegram

**Painel → Configurações → Telegram**

1. Fale com [@BotFather](https://t.me/BotFather) no Telegram → `/newbot`
2. Cole o token no painel
3. Em 30s o daemon registra o webhook automaticamente
4. Envie `/start` para o bot — Marcos responde

### Chat web

Disponível em qualquer dispositivo via painel. Mesmo Marcos, mesmo histórico.

---

## 4. Criar automações

**Painel → Automações → Nova Automação**

Ou via chat:

```
"Marcos, cria uma automação pra me mandar o faturamento toda segunda às 9h"
"Marcos, me avisa sempre que o caixa ficar abaixo de R$ 20.000"
```

Tipos de gatilho disponíveis:
- **Cron**: horário específico ("toda segunda às 09:00")
- **Métrica**: quando KPI cruza threshold ("caixa < R$50k")
- **Manual**: botão no painel ou mensagem para Marcos

Ações que precisam de confirmação (Marcos pede "SIM" antes de executar):
- Enviar cobrança para cliente
- Criar fatura no ERP
- Atualizar deal no CRM

---

## 5. Definir alertas

**Painel → Configurações → Alertas**

| Tipo | Exemplo |
|------|---------|
| Taxa de erro | "Me avisa se o daemon de automações falhar mais de 50% dos ciclos" |
| Daemon caiu | "Me avisa se o gateway do OpenClaw cair" |
| Budget Anthropic | "Me avisa se o custo passar de R$ 100/dia" |
| Latência alta | "Me avisa se Marcos demorar mais de 60s consistentemente" |

Canais de notificação: WhatsApp, Telegram, painel. Cooldown configurável (evita spam).

---

## 6. Controlar via painel (sem SSH)

**Painel → Configurações → Sistema**

Através do Marcos ou da UI, você pode:

```
"Marcos, reinicia o serviço cfo-automation-engine"
"Marcos, mostra os últimos 30 logs do cfo-evolution-sync"
"Marcos, qual o status do OpenClaw?"
"Marcos, instala o plugin X"
"Marcos, atualiza todas as skills"
```

Ações disponíveis: restart/start/stop de serviços, logs, config get/set, plugins, MCP servers, self-update. Ver [docs/admin-actions.md](admin-actions.md) para lista completa.

---

## 7. Backup e restore

### Backup automático

Roda todo dia às 03:00 e salva em `~/.agente-cfo/backups/`. Mantém 7 versões.

### Backup manual

```bash
# Via painel: Configurações → Sistema → "Baixar Backup"
# Ou pede pro Marcos: "Marcos, faz um backup das minhas configurações"
```

### Restore

```bash
# Com o arquivo tar.gz do backup:
bash restore_config.sh ~/cfo-backup-YYYYMMDD.tar.gz --dry-run  # pré-visualiza
bash restore_config.sh ~/cfo-backup-YYYYMMDD.tar.gz             # aplica
```

Ver [docs/backup-restore.md](backup-restore.md) para detalhes.

---

## 8. Migrar para nova VPS

```bash
# 1. Na VPS atual — gera backup com tudo
bash memory_export.sh --include-sessions --output ~/marcos-completo.tar.gz
bash backup_config.sh --include-secrets --output ~/config-completo.tar.gz

# 2. Transfere para nova VPS
scp ~/marcos-completo.tar.gz ~/config-completo.tar.gz nova-vps:~/

# 3. Na nova VPS — instala e restaura
curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh | bash
bash restore_config.sh ~/config-completo.tar.gz
bash memory_import.sh ~/marcos-completo.tar.gz --replace
```

---

## 9. Problemas comuns

| Sintoma | Causa provável | Solução |
|---------|---------------|---------|
| Marcos não responde | Gateway offline | `systemctl restart openclaw-gateway` ou via painel |
| QR code WhatsApp não aparece | Evolution sync falhou | Painel → Configurações → WhatsApp → "Forçar Sync" |
| Integração ERP não funciona | Credentials sync atrasado | Aguarda 3min ou "Marcos, forçar sync de credenciais" |
| Chat web deu erro 503 | VPS offline / tunnel caiu | Verifica `systemctl status cloudflared-cfo` |
| Alerta não disparou | Cooldown ativo (30min padrão) | Aguarda cooldown ou ajusta no painel |

Ver [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) para diagnóstico completo.

---

## Para desenvolvedores

| Recurso | Link |
|---------|------|
| Arquitetura técnica | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| Histórico de sprints | [docs/SPRINTS.md](SPRINTS.md) |
| Protocolo WebSocket | [docs/openclaw-ws.md](openclaw-ws.md) |
| Pipeline cross-channel | [docs/channels.md](channels.md) |
| Observabilidade | [docs/metrics.md](metrics.md) |
