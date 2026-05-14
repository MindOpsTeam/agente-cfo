# Telegram — Bot Integration

Integração do Agente CFO com Telegram via Bot API. Zero SSH — configuração 100% via painel.

## Como conectar (zero SSH)

1. Abra o Telegram e fale com **@BotFather**
2. Digite `/newbot` e siga as instruções para criar seu bot
3. Copie o token gerado (`123456789:AAH...`)
4. No painel Agente CFO → Configurações → Telegram → "Adicionar bot"
5. Cole o token e clique em "Salvar"
6. Em até 30s o daemon registra o webhook automaticamente
7. Teste enviando `/start` para o bot

## Variáveis (todas via painel — nenhuma manual)

| Variável | Origem |
|----------|--------|
| `TELEGRAM_BOT_TOKEN` | edge fn `telegram-bots-vps-token` |
| Webhook URL | `${PANEL_BASE_URL}/telegram-incoming-webhook` |

## Gerenciamento

```bash
systemctl status cfo-telegram-sync
journalctl -u cfo-telegram-sync -f
systemctl restart cfo-telegram-sync  # forçar re-sync
```

## Enviar mensagem (Marcos usa automaticamente)

```bash
bash ~/.openclaw/workspace/skills/telegram/scripts/send_telegram.sh \
  "marcoscfo_bot" "123456789" "Olá do Marcos!"
```

## Pipeline unificado

Mensagens Telegram usam o mesmo `chat_messages.channel` do WhatsApp:
- `thread_id = telegram:<bot_username>:<chat_id>`
- `channel = telegram:<bot_username>`
- Histórico compartilhado com o painel web (se mesmo usuário)
