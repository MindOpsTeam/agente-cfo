# Guia do Cliente — Agente CFO (Marcos)

> **Versão:** Sprint LAUNCH-1 · 2026-05-21  
> **Tempo de leitura:** ~5 minutos  
> **Tempo de instalação:** ~15 minutos

---

## 1. O que é Marcos

**Marcos** é um CFO virtual 24/7 que responde no seu WhatsApp, Telegram e painel web com dados reais do seu negócio. Ele consulta seu ERP, CRM e plataforma de cobrança, lança despesas, analisa inadimplência, projeta fluxo de caixa e sugere ações concretas — tudo sem você abrir planilha ou dashboard.

É como ter um CFO sênior disponível a qualquer hora, que conhece seu negócio de cor e diz o que você precisa ouvir, não o que você quer.

---

## 2. Por que é diferente

| Característica | Marcos | Ferramentas tradicionais |
|----------------|--------|--------------------------|
| **Onde roda** | Na sua VPS (você é dono) | Na nuvem deles |
| **Seus dados** | Ficam na sua infra | Ficam nos servidores deles |
| **Custo** | ~R$60–110/mês (infraestrutura) | R$200–800/mês (SaaS) |
| **Código** | Open-source (MIT) | Caixa-preta |
| **Canal** | WhatsApp / Telegram / Web | Só dashboard |
| **Inteligência** | Proativo — alerta sem você pedir | Só mostra dados quando você abre |

---

## 3. Pré-requisitos

Você precisa de **4 coisas** antes de começar:

### 3a. Conta Anthropic (obrigatório)

Marcos usa o modelo Claude Sonnet da Anthropic para pensar.

1. Acesse [console.anthropic.com](https://console.anthropic.com)
2. Crie conta e adicione créditos (~R$50 pra começar, dura semanas em uso normal)
3. Crie uma API key (`sk-ant-api03-...`)
4. Guarde essa chave — você vai colar no onboarding

**Custo estimado:** R$30–80/mês dependendo de quantas mensagens o Marcos recebe.

### 3b. VPS Linux (obrigatório)

Uma máquina virtual onde o Marcos vai rodar. Não precisa de servidor caro — o básico funciona.

**Requisitos mínimos:** Ubuntu 22.04+, 1 vCPU, 1 GB RAM, 20 GB disco

**Provedores recomendados:**

| Provedor | Plano recomendado | Preço | Link |
|----------|------------------|-------|------|
| **Hetzner** (melhor custo-benefício) | CX22 (2 vCPU / 4 GB) | €4,35/mês | [hetzner.com/cloud](https://hetzner.com/cloud) |
| **DigitalOcean** (mais conhecido) | Droplet Basic 2 GB | $12/mês | [digitalocean.com](https://digitalocean.com) |
| **Hostinger** (opção BR) | VPS 1 (1 vCPU / 1 GB) | R$24/mês | [hostinger.com.br/vps](https://hostinger.com.br/vps) |

> Pode usar AWS, GCP, OVH, Linode — qualquer VPS Ubuntu funciona. Hetzner é a mais barata e confiável para PMEs.

### 3c. WhatsApp (opcional para começar)

Um número WhatsApp que o Marcos vai usar para se comunicar com você. **Recomendado: chip dedicado** (não use seu número pessoal para evitar risco de banimento).

Você pode começar usando só o chat web e adicionar WhatsApp depois.

### 3d. ERP com API ativa (opcional para começar)

Marcos funciona sem ERP no início — você pode testar pelo chat. Para dados reais, configure depois:

**Suportados:** Omie · Bling · Tiny · Granatum · VHSYS · Nibo · ContaAzul  
**Recomendado para começar:** Omie (gratuito, API mais completa)

---

## 4. Instalação passo a passo (~15 minutos)

### Etapa 1 — Remixar o template no Lovable (2 min)

1. Acesse o template público do Agente CFO no Lovable
2. Clique em **"Remix"**
3. Crie sua conta Lovable (email + OTP, grátis)
4. O Lovable cria automaticamente:
   - Seu painel web próprio (URL: `seu-projeto.lovable.app`)
   - Banco de dados Supabase próprio
   - Todas as edge functions necessárias

### Etapa 2 — Criar conta no painel (1 min)

1. Acesse `seu-projeto.lovable.app`
2. Clique em **"Criar conta"**
3. Email + OTP — sem senha para lembrar

### Etapa 3 — Wizard de onboarding (5 min)

O wizard te guia por 4 passos:

1. **Anthropic** — cole sua API key (`sk-ant-...`). O wizard valida em tempo real.
2. **ERP** — escolha seu ERP e cole as credenciais (ou pule por agora)
3. **WhatsApp** — informe o número que vai usar (ou pule)
4. **Revisão** — confirme e clique em **"Gerar comando de instalação"**

O wizard gera **um comando único** com tudo configurado. Copie ele.

### Etapa 4 — Instalar na VPS (5 min)

1. Acesse sua VPS via SSH:
   ```bash
   ssh root@IP_DA_SUA_VPS
   ```

2. Cole o comando gerado pelo wizard (ele começa com `curl -fsSL ...`):
   ```bash
   # Exemplo — o seu vai ter suas credenciais embutidas:
   curl -fsSL "https://seu-projeto.supabase.co/functions/v1/setup-installer?token=XXXXX" | bash
   ```

3. Aguarde ~5 minutos. O script instala tudo automaticamente:
   - OpenClaw (orquestrador de agentes)
   - Marcos (agente CFO com todas as skills)
   - 9 daemons de background
   - Tunnel Cloudflare (acesso externo)
   - MCPs das suas integrações

4. No final aparece:
   ```
   ╔══════════════════════════════════════════════════╗
   ║              Instalação Concluída!               ║
   ╚══════════════════════════════════════════════════╝
   Marcos está online.
   ```

5. **Se configurou WhatsApp:** abra `http://[URL-DO-PAINEL]/settings/whatsapp` e escaneie o QR code

### Pronto!

Abra o chat no painel ou mande mensagem no WhatsApp:
> "Marcos, tudo bem?"

Ele responde.

---

## 5. Custos mensais estimados

| Item | Faixa de custo |
|------|---------------|
| VPS (Hetzner CX22) | €4,35/mês (~R$26) |
| Anthropic API — uso leve (30–50 msgs/dia) | ~R$30–50 |
| Anthropic API — uso moderado (100–200 msgs/dia) | ~R$50–120 |
| Lovable (free tier — até 5 projetos) | Grátis |
| **Total estimado** | **~R$60–150/mês** |

> **Dica:** Configure `LLM_BUDGET_BRL` no onboarding para limitar o gasto mensal com Anthropic automaticamente.

---

## 6. Como pedir ajuda

- **Documentação:** [docs/ neste repositório](https://github.com/MindOpsTeam/agente-cfo/tree/main/docs)
- **FAQ:** [docs/FAQ.md](FAQ.md)
- **Problemas:** [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Comunidade:** [Viver de IA](https://viverdeia.ai)
- **GitHub Issues:** [github.com/MindOpsTeam/agente-cfo/issues](https://github.com/MindOpsTeam/agente-cfo/issues)

> ⚠️ **Sem suporte 1:1.** Este é um projeto open-source comunitário.

---

## 7. Privacidade e segurança

- **Seus dados ficam na sua VPS e no seu banco Supabase** — ninguém mais tem acesso
- A API key da Anthropic fica no arquivo `~/.agente-cfo/.env` da sua VPS (chmod 600)
- Credenciais de ERP ficam no seu Supabase Vault (criptografadas)
- O painel Lovable tem autenticação por email + OTP
- Não existe servidor central nosso que recebe seus dados financeiros

---

## 8. Como atualizar Marcos

```bash
# Na sua VPS:
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/self_update.sh
```

Ou via painel → Configurações → Sistema → "Atualizar Marcos".
