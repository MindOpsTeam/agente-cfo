# LAUNCH-CHECKLIST.md — Sprint LAUNCH-1

> Checklist do PM para colocar o Agente CFO disponível para clientes.
> Itens marcados com **[LOVABLE]** exigem ação no dashboard Lovable.
> Itens marcados com **[PM]** são feitos pelo PM direto.

---

## Pré-lançamento (fazer antes de divulgar)

### Lovable Dashboard — Configurar template público

- [ ] **[LOVABLE]** Acessar [lovable.dev](https://lovable.dev) → Dashboard → projeto `carteira-do-agente`
- [ ] **[LOVABLE]** Marcar `is_published = true`
- [ ] **[LOVABLE]** Marcar `visibility = public`
- [ ] **[LOVABLE]** Ativar `public_remixing_enabled = true`
- [ ] **[LOVABLE]** Copiar URL de remix público (formato: `lovable.dev/projects/XXX/remix`)
- [ ] **[LOVABLE]** Configurar thumbnail/preview card do projeto
- [ ] **[LOVABLE]** Adicionar descrição: "CFO virtual 24/7 para PMEs brasileiras — rode na sua infra"

### Atualizar landing page com URL de remix

- [ ] **[LOVABLE AI PROMPT]** Disparar prompt abaixo para atualizar `/install` com URL real:

```
No arquivo src/routes/install.tsx, atualize o botão "Remixar no Lovable" para apontar para a URL:
[URL_DE_REMIX_COPIADA_ACIMA]

Também atualize qualquer referência a "carteira-do-agente.lovable.app" para usar a URL pública correta do template.
```

### Repositório GitHub

- [ ] **[PM]** Confirmar repo `agente-cfo` como public: `gh repo view MindOpsTeam/agente-cfo --json visibility`
- [ ] **[PM]** Confirmar repo `carteira-do-agente` como public: `gh repo view MindOpsTeam/carteira-do-agente --json visibility`
- [ ] **[PM]** README.md atualizado com CTA e botão remix ✅ (feito neste sprint)
- [ ] **[PM]** Adicionar topics ao repo GitHub: `cfo`, `ai-agent`, `openai`, `anthropic`, `mcp`, `whatsapp`, `brasil`, `pme`, `lovable`

```bash
gh repo edit MindOpsTeam/agente-cfo \
  --add-topic cfo --add-topic ai-agent --add-topic mcp \
  --add-topic whatsapp --add-topic brasil --add-topic pme \
  --add-topic anthropic --add-topic lovable
```

### Documentação

- [ ] **[PM]** Verificar docs/CLIENTE.md atualizado ✅ (feito neste sprint)
- [ ] **[PM]** Verificar docs/FAQ.md atualizado ✅ (feito neste sprint)
- [ ] **[PM]** Verificar docs/TROUBLESHOOTING.md atualizado ✅ (feito neste sprint)

---

## Lançamento

### Health indicator no dashboard

- [ ] **[LOVABLE AI PROMPT]** Disparar `docs/SPRINT-LAUNCH-1-LOVABLE-PROMPT.md` para adicionar card de status do Marcos no dashboard

### Comunicação

- [ ] **[PM]** Post no Viver de IA com link do template + tutorial em vídeo
- [ ] **[PM]** README GitHub com badge "template gratuito" ✅
- [ ] **[PM]** Thread no X/Twitter com GIF de demo

---

## Pós-lançamento

### Monitoramento

- [ ] **[PM]** Verificar edge fn `instance-register` recebendo registros de clientes novos
- [ ] **[PM]** Monitorar issues no GitHub
- [ ] **[PM]** Verificar se setup.sh está funcionando para clientes (testar com VPS limpa)

### Manutenção contínua

- [ ] **[PM]** Setup alert no GitHub pra notificação de issues com label `bug`
- [ ] **[PM]** Review quinzenal de SPRINTS.md para priorizar próximos itens

---

## Notas de Arquitetura

### Single-tenant (por design)

Cada cliente tem:
- **1 painel Lovable** (Remix → banco Supabase próprio)
- **1 VPS** com Marcos
- **Zero compartilhamento** de dados entre clientes

Não há painel central — o cliente é 100% dono da infraestrutura.

### Fluxo de instalação

```
Cliente faz Remix
       ↓
Cria conta no painel (email + OTP)
       ↓
Wizard de onboarding (4 etapas)
  - Anthropic API key (validada na hora)
  - ERP + credenciais (opcional)
  - WhatsApp número (opcional)
  - Revisão
       ↓
Painel gera one-time token (24h)
       ↓
edge fn setup-installer?token=XXX
  → retorna shell script com env vars preenchidas
       ↓
Cliente cola 1 comando na VPS
       ↓
setup.sh roda (~5 min)
  → instala tudo
  → registra instância no painel
  → heartbeat começa
       ↓
Marcos online ✅
```
