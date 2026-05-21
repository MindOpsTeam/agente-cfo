# TELEGRAM-SETUP.md — Configurar Marcos no Telegram

> **Tempo estimado:** ~10 minutos  
> **Pré-requisito:** Marcos já instalado na VPS (setup.sh concluído)

---

## Visão geral

Marcos responde no Telegram exatamente igual ao WhatsApp — mesmo pipeline, mesmo histórico, mesmos dados do ERP. A única diferença é o canal de entrega.

```
Você (Telegram) ──→ Bot API ──→ edge fn telegram-webhook
                                        ↓
                               incoming-message
                                        ↓
                               Marcos na VPS
                                        ↓
                            panel_post_reply.sh
                                        ↓
                    telegram/scripts/send_message.sh ──→ Você
```

---

## Passo 1 — Criar bot no @BotFather

1. Abra o Telegram e busque **@BotFather**
2. Envie `/newbot`
3. Escolha um nome para o bot (ex: "CFO Marcos")
4. Escolha um username (deve terminar em `bot`, ex: `marcoscfo_bot`)
5. BotFather vai te enviar o **token** no formato:
   ```
   123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
6. **Copie o token** — você vai precisar no próximo passo

---

## Passo 2 — Configurar no painel

1. Acesse seu painel → **Configurações → Telegram**  
   (sidebar → Canais → Telegram)
2. Clique em **"Adicionar bot"**
3. Preencha:
   - **Username:** `marcoscfo_bot` (sem o @)
   - **Token:** cole o token do BotFather
4. Ative **"Marcos responde neste bot"**
5. Clique em **"Salvar e ativar webhook"**

O painel automaticamente:
- Calcula o `webhook_secret` = `sha256(token)[:32]`
- Salva o bot na tabela `telegram_bots`
- Envia comando para a VPS registrar o webhook no Telegram

---

## Passo 3 — Aguardar registro do webhook (automático)

O daemon na VPS faz um `POST /setWebhook` para:
```
https://api.telegram.org/bot{TOKEN}/setWebhook?url={URL_DA_EDGE_FN}/telegram-webhook?secret={SECRET}
```

**Verificar que funcionou:**
```bash
# Na VPS:
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

Deve retornar `"url": "https://...supabase.co/functions/v1/telegram-webhook?secret=..."`.

Se o webhook não foi registrado automaticamente, faça manualmente:
```bash
# Na VPS (substituindo TOKEN e SECRET):
TELEGRAM_BOT_TOKEN="123456789:AAxxxxxx"
WEBHOOK_SECRET="abc123..."  # ver em: openclaw config get ou telegram_bots.webhook_secret

curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{
    \"url\": \"${PANEL_BASE_URL}/telegram-webhook?secret=${WEBHOOK_SECRET}\",
    \"max_connections\": 10,
    \"allowed_updates\": [\"message\"]
  }"
```

---

## Passo 4 — Testar

1. Abra o Telegram e inicie conversa com seu bot (`@marcoscfo_bot`)
2. Envie `/start` ou qualquer mensagem
3. Marcos deve responder em ~3-10 segundos

---

## Solução de problemas

### Bot não responde

```bash
# 1. Checar webhook info
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"

# 2. Checar logs da edge fn no Supabase Dashboard
# Logs → Functions → telegram-webhook

# 3. Checar que bot está ativo no banco
# SELECT * FROM telegram_bots WHERE bot_username = 'marcoscfo_bot';

# 4. Checar que receives_marcos_chat = true
# UPDATE telegram_bots SET receives_marcos_chat = true WHERE bot_username = 'marcoscfo_bot';
```

### "Bot não configurado" (404)

O `webhook_secret` no URL não bate com o do banco. Reconfigure o webhook:
- Painel → Telegram → "Editar" → "Salvar e ativar webhook" novamente

### Marcos envia mas mensagem não chega

```bash
# Testar send_message.sh diretamente (substituir TOKEN e CHAT_ID):
TELEGRAM_BOT_TOKEN="123456789:AAxxxxxx" \
  bash ~/.openclaw/workspace/skills/telegram/scripts/send_message.sh \
  "telegram:marcoscfo_bot" "SEU_CHAT_ID" "Teste de envio"
```

Para obter seu `CHAT_ID`:
```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates"
# Procure: result[0].message.chat.id
```

---

## Usar múltiplos bots

Você pode ter N bots no Telegram — cada um com username e token diferentes. Útil para ambientes separados (produção / homologação) ou para diferentes empresas/contas.

Adicione cada bot no painel → Telegram → "Adicionar bot".

O canal Telegram é identificado por `telegram:<bot_username>` no histórico do chat.

---

## Diferenças vs WhatsApp

| Aspecto | WhatsApp | Telegram |
|---------|----------|---------|
| Conta | Chip dedicado | Bot gratuito |
| Risco de ban | Existe | Praticamente zero |
| Limite de msgs | ~1k/dia (informal) | Sem limite |
| Grupos | Suportado (vip) | Suportado nativamente |
| Mídia | Limitado | Fotos, docs, áudio |
| Custo | Chip (~R$15/mês) | Grátis |
