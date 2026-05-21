# FAQ — Agente CFO (Marcos)

> Dúvidas mais comuns. Se não encontrar aqui, veja [TROUBLESHOOTING.md](TROUBLESHOOTING.md) ou abra uma issue no GitHub.

---

## Instalação e infraestrutura

### Por que preciso de VPS? Não dá pra rodar em cloud normal?

O Marcos é um processo persistente — ele precisa ficar rodando 24/7, ouvindo mensagens, executando crons às 07h e 18h, mantendo MCPs quentes. Serviços de cloud "serverless" (Vercel, Railway free tier, Render) hibernam após inatividade.

Uma VPS barata (~R$25/mês) resolve isso de forma simples e confiável.

### Posso usar AWS, GCP, Azure em vez de Hetzner?

Sim. O setup.sh funciona em qualquer Ubuntu 22.04+. Use o que preferir.

AWS recomendado: EC2 t3.small (2 vCPU / 2 GB) em us-east-1 ou sa-east-1 — ~$18/mês.

### Precisa de IP fixo na VPS?

Não. O Marcos usa Cloudflare Tunnel para expor os webhooks — o IP pode mudar sem problema.

### Posso usar meu próprio domínio?

Sim. Configure no painel → Configurações → Sistema → "Usar domínio próprio" e adicione o CNAME apontando para o tunnel. Mas não é necessário para funcionar.

---

## Dados e privacidade

### Meus dados financeiros ficam onde?

Na sua VPS e no seu banco Supabase (criado quando você fez o Remix no Lovable). **Nenhum dado passa por servidores da MindOps** — o Marcos acessa seus ERPs diretamente da sua VPS.

Exceção: as mensagens vão para a Anthropic API (para o Claude processar). Revise a política de privacidade em [anthropic.com/privacy](https://anthropic.com/privacy).

### Posso trocar de provedor de VPS depois?

Sim. Rode `bash ~/.openclaw/workspace/skills/agente-cfo/scripts/backup_config.sh` antes, migre para nova VPS, e rode `bash restore_config.sh`. O painel Supabase continua igual — só a VPS muda.

### Posso deletar tudo e recomeçar?

Sim: delete a VPS e rode `openclaw uninstall` no painel. Para recomeçar, rode o wizard de onboarding novamente e um novo comando de instalação será gerado.

---

## Integrações

### Posso conectar mais de um ERP?

O Marcos usa **1 ERP principal** (definido em `CFO_ERP_NAME`). Mas você pode conectar quantas *skills* quiser como fontes de dados secundárias — por exemplo, Omie como ERP principal e também consultar Bling para comparação.

Para trocar de ERP principal: painel → Configurações → Sistema → "ERP principal".

### Posso conectar mais de um CRM?

Mesma lógica — 1 CRM ativo. Você pode trocar a qualquer momento pelo painel.

### Todas as integrações são gratuitas?

As skills são gratuitas e open-source. Você paga apenas a API do ERP/CRM (que provavelmente já paga como SaaS). O Marcos só acessa APIs que você já tem acesso.

### Posso testar sem ter ERP?

Sim! Sem ERP conectado, o Marcos responde com dados "indisponíveis" mas funciona para planejamento, análise de cenários e aprendizado. Configure o ERP depois.

---

## WhatsApp

### Risco de banimento?

O Marcos usa a Evolution API, que simula um dispositivo WhatsApp conectado. O WhatsApp não gosta disso oficialmente. Para minimizar risco:
- Use um número/chip dedicado (não seu número pessoal)
- Não envie mensagens em massa (o Marcos não foi feito para isso)
- Volume de mensagens típico: 5–30 mensagens/dia — muito abaixo dos limites de ban

### Posso usar meu número pessoal?

Tecnicamente sim, mas **não recomendado**. Se o número for banido, você perde o WhatsApp pessoal. Use um chip dedicado.

### E se o WhatsApp desconectar?

O Marcos tem auto-recovery: o daemon `wacli-sync` detecta a desconexão e tenta reconectar automaticamente. Se falhar: abra o painel → Configurações → WhatsApp → "Reconectar" e escaneie o QR novamente.

---

## Uso e custos

### Quanto gasto com Anthropic?

Depende do volume de mensagens. Estimativas:
- **Uso leve** (30–50 msgs/dia): ~R$30–50/mês
- **Uso moderado** (100–200 msgs/dia): ~R$80–120/mês
- **Uso intenso** (300+ msgs/dia): ~R$150–250/mês

Configure um limite em `LLM_BUDGET_BRL` no onboarding — o Marcos para de responder quando atingir o limite e avisa você.

### Como sei quanto estou gastando?

Painel → Custo LLM → gráfico por modelo e período. Também configurável via alertas automáticos.

### Como atualizo o Marcos com novas skills?

```bash
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/self_update.sh
```

Ou via painel → Configurações → Sistema → "Verificar atualizações".

---

## Canais

### Marcos funciona no Telegram?

Sim. Configure em painel → Configurações → Telegram → "Adicionar bot" com o token do BotFather. O Marcos passa a responder tanto no WhatsApp quanto no Telegram com o mesmo histórico.

### Posso usar o painel web sem WhatsApp?

Sim. O chat web funciona independentemente. Você pode usar o Marcos exclusivamente pelo browser se preferir.

### Posso ter mais de um WhatsApp conectado?

Sim — via Evolution API você pode configurar múltiplas instâncias. Útil se você quer que o Marcos responda em números diferentes para contexts diferentes.

---

## Problemas comuns

Veja [TROUBLESHOOTING.md](TROUBLESHOOTING.md) para soluções detalhadas de:
- WhatsApp não pareou
- Tunnel Cloudflare caiu
- ERP retornando 401
- Daemons reiniciando em loop
- Marcos não responde
