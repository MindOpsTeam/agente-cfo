# FAQ — Perguntas Frequentes

---

## Sobre o Marcos

### O que é o Marcos?

Marcos é o CFO virtual do Agente CFO. É um agente de IA com personalidade e identidade própria — não é um chatbot genérico. Ele conhece o contexto financeiro da sua empresa, fala diretamente via WhatsApp e age como um CFO real: monitora caixa, alerta sobre vencimentos, analisa pipeline de vendas e responde perguntas financeiras em linguagem natural.

A identidade e o tom do Marcos são definidos nos arquivos `identity/soul.md` e `identity/identity.md` — você pode personalizá-los depois da instalação.

---

### Quanto custa usar o Agente CFO?

O template em si é **gratuito**. Os custos são seus e dependem do uso:

| Item | Quem paga | Estimativa |
|---|---|---|
| VPS Linux | Você | R$ 25–80/mês (DigitalOcean, Vultr, Hetzner) |
| Anthropic API | Você | Varia com uso. R$ 50/mês é confortável para PME. |
| Supabase (banco + edge functions) | Você | Gratuito no free tier para volume baixo |
| Cloudflare Tunnel | Gratuito | Zero |
| Lovable Cloud (painel) | Gratuito | Plano free tem limites de edição |

A variável `LLM_BUDGET_BRL` no setup configura um limite mensal de gasto com a Anthropic. Quando o limite é atingido, o agente para de processar e você recebe um aviso.

---

### Posso usar sem o Lovable?

Sim. O painel Lovable é conveniente mas não obrigatório para o funcionamento do Marcos.

Sem o Lovable, você perde:
- Dashboard visual de eventos e alertas
- Interface de onboarding guiado
- Histórico de mensagens no browser

O agente continua funcionando normalmente: recebe mensagens via WhatsApp, envia alertas nos horários configurados e detecta anomalias.

Se quiser usar sem Lovable, use o [Fluxo 2 — Setup Manual](INSTALACAO.md#fluxo-2--alternativo-setup-manual-sem-painel) da documentação de instalação.

---

## ERPs e CRMs

### Quais ERPs são suportados?

| ERP | Auth | Observações |
|---|---|---|
| **Omie** | App Key + Secret | Mais testado. Recomendado para novos usuários. |
| **Bling** | OAuth 2.0 | Refresh automático. |
| **Tiny** | Token API v2 | |
| **Granatum** | Access Token | |
| **VHSYS** | Access Token + Secret | |
| **Nibo** | API Token | Requer plano Premium. |
| **ContaAzul** | OAuth 2.0 | Refresh automático. API v1 financeira. |

### Quais CRMs são suportados?

| CRM | Auth | Observações |
|---|---|---|
| **HubSpot** | Private App Token | Stage mapping cacheado localmente. |
| **RD Station CRM** | Token de integração | |
| **PipeRun** | Token | |
| **Pipedrive** | API Token + subdomínio | Stage mapping cacheado localmente. |

CRM é opcional. Sem CRM, as funcionalidades de pipeline não estarão disponíveis.

---

### Posso trocar de ERP depois da instalação?

Sim. Execute o `connect.sh` do novo ERP e atualize `CFO_ERP_NAME` no `.env`:

```bash
# Instalar nova skill
bash ~/.openclaw/workspace/skills/bling/scripts/connect.sh

# Atualizar variável
sed -i "s/CFO_ERP_NAME=.*/CFO_ERP_NAME=bling/" ~/.agente-cfo/.env

# Reiniciar o gateway para carregar o novo ERP
openclaw gateway restart
```

---

## Funcionamento

### Como faço para conversar com o Marcos?

**Via WhatsApp:** Mande uma mensagem de qualquer celular vinculado ao número configurado em `CFO_WHATSAPP_TO`. O número que o Marcos "escuta" é o dele (o número do chip da VPS). Para que o dono converse, ele manda mensagem *para* esse número — seja de auto-mensagem (se for o mesmo número) ou de outro celular.

**Via painel:** Acesse `/chat` no painel Lovable para um terminal de conversa direto, sem WhatsApp.

Exemplos de mensagens que o Marcos entende:

```
"Qual meu saldo agora?"
"Quem vence hoje?"
"Quanto tenho a pagar essa semana?"
"Pipeline do mês"
"Projeção de caixa para 30 dias"
"Inadimplência em aberto"
```

---

### Marcos pode pagar contas sozinho?

**Não.** Toda operação de escrita (pagar conta, criar lançamento, mover deal) exige confirmação explícita do dono.

O fluxo é:

1. Dono pede: *"Paga a conta da luz"*
2. Marcos lê a API, identifica o lançamento e mostra um rascunho:
   ```
   Confirme:
   PAGAR
   Fornecedor: CEMIG
   Valor: R$ 480,00
   Vencimento: 06/05
   Responda SIM para confirmar ou NAO para cancelar.
   ```
3. Dono responde: *"SIM"*
4. Marcos executa e confirma

Qualquer resposta que não seja confirmação explícita cancela a operação. Isso é uma garantia de segurança inegociável — o Marcos nunca age de forma autônoma em operações que alteram dados financeiros.

---

### Como ativar ou desativar as regras proativas?

As regras de detecção de anomalias (caixa baixo, inadimplência alta, pipeline em queda etc.) rodam a cada 30 minutos no daemon `cfo-proactive`.

**Via painel:** Acesse `/settings/rules` para ativar/desativar regras individualmente e ajustar thresholds.

**Via env vars** (ajuste fino):

```bash
# Exemplo: ajustar threshold de caixa baixo
echo "CFO_CASH_LOW_THRESHOLD_BRL=5000" >> ~/.agente-cfo/.env

# Desativar uma regra específica (não há flag, mas você pode remover do watcher)
# Edite ~/.openclaw/workspace/skills/agente-cfo/scripts/cfo_proactive_watcher.py
# e remova a entrada da RULE_MODULES correspondente

openclaw gateway restart
```

As 8 regras disponíveis:

| Regra | Trigger | Cooldown |
|---|---|---|
| `rule_cash_low` | Caixa projetado abaixo do threshold (7/30/90 dias) | 24h |
| `rule_overdue_critical` | Contas vencidas acima do threshold | 24h |
| `rule_concentration` | Um cliente representa >X% do total a receber | 72h |
| `rule_inadimplencia_high` | Inadimplência total acima de X% do faturamento | 48h |
| `rule_deal_stale` | Deal parado na mesma etapa há mais de N dias | 168h |
| `rule_pipeline_drop` | Vendas fechadas esse mês < 50% do mesmo período do mês anterior | 168h |
| `rule_pipeline_health` | Pipeline projetado nos próximos 30 dias abaixo do threshold | 72h |
| `rule_erp_api_health` | API do ERP com falhas repetidas | 24h |

---

### Posso adicionar mais usuários ao Marcos?

Não no MVP atual. O Marcos é configurado para responder a **um único número WhatsApp** (`CFO_WHATSAPP_TO`). Múltiplos usuários não são suportados — ele escuta apenas mensagens desse número.

---

## Dados e Segurança

### Onde ficam meus dados?

**Na sua infraestrutura.** Sempre.

| Dado | Onde fica |
|---|---|
| Credenciais ERP/CRM | `~/.openclaw/secrets/` na sua VPS |
| Histórico de conversas | `~/.agente-cfo/memory/` na sua VPS |
| Eventos e alertas | Banco Supabase do seu projeto Lovable |
| Tokens OAuth | `~/.openclaw/secrets/` na sua VPS (chmod 600) |

**Nenhum dado volta para a Viver de IA ou para os autores do template.** O Supabase é o seu projeto, criado na sua conta. A VPS é a sua máquina.

---

### Como rotacionar tokens e secrets?

**API Keys estáticas (Omie, Tiny, VHSYS, Nibo, HubSpot, RD Station, PipeRun, Pipedrive):**

```bash
# Editar diretamente o arquivo de secrets
nano ~/.openclaw/secrets/<skill>.env
# Atualizar o token
openclaw gateway restart
```

**OAuth tokens (Bling, ContaAzul):**

O refresh token é renovado automaticamente. Se quiser regenerar do zero:
```bash
bash ~/.openclaw/workspace/skills/<skill>/scripts/connect.sh --force
```

**Anthropic API Key:**
```bash
sed -i "s/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=sk-ant-nova-chave/" ~/.agente-cfo/.env
openclaw gateway restart
```

**PANEL_TOKEN (token VPS → Supabase):**

Gere um novo e atualize dos dois lados:
```bash
NEW_TOKEN=$(openssl rand -hex 32)
sed -i "s/PANEL_TOKEN=.*/PANEL_TOKEN=$NEW_TOKEN/" ~/.agente-cfo/.env
echo "Novo token: $NEW_TOKEN"
echo "Atualize agora em: Supabase → Settings → Edge Functions → Secrets → PANEL_TOKEN"
openclaw gateway restart
```

---

### Como fazer backup e recovery?

**Backup da VPS:** Crie um snapshot periódico na sua provedora (DigitalOcean, Hetzner etc.). Um snapshot completo inclui tudo — OpenClaw, wacli, secrets, histórico de conversas.

**Backup seletivo dos dados críticos:**
```bash
# Fazer backup dos secrets e .env
tar -czf agente-cfo-backup-$(date +%Y%m%d).tar.gz \
  ~/.agente-cfo/.env \
  ~/.agente-cfo/instance.env \
  ~/.openclaw/secrets/ \
  ~/.agente-cfo/memory/

# Copiar para fora da VPS
scp agente-cfo-backup-*.tar.gz usuario@backup-server:/backups/
```

**Backup do banco Supabase:**  
Acesse **Supabase → Settings → Database → Backups**. O plano free tem backups diários automáticos por 7 dias.

**Recovery:**  
Em caso de perda da VPS, provisione uma nova e reexecute o `setup.sh` com as mesmas variáveis de ambiente. O estado de memória das conversas pode ser restaurado do backup manual.
