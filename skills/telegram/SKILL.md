---
name: telegram
description: >
  Integração Telegram via Bot API. O daemon telegram_sync.py registra o webhook
  de cada bot no Telegram apontando para a edge function telegram-incoming-webhook
  do painel. Marcos responde via send_telegram.sh com os mesmos tools e contexto
  do chat web (pipeline unificado via chat_messages.channel).
category: messaging
---

# Telegram — Skill

## O que faz

- **Daemon `telegram_sync.py`**: loop a cada 30s, busca bots ativos no painel,
  registra webhook no Telegram e atualiza status
- **`telegram_client.py`**: wrapper Python da Bot API do Telegram
- **`send_telegram.sh`**: helper que Marcos usa para enviar mensagens
  (`send_telegram.sh <bot_username> <chat_id> <texto>`)

## Auth

Usa as mesmas credenciais da VPS:
- `PANEL_BASE_URL`, `PANEL_TOKEN`, `HOOKS_TOKEN` (de `~/.agente-cfo/.env`)
- Token do bot buscado via `telegram-bots-vps-token` edge function (sem armazenar localmente)

## Systemd

```bash
systemctl status cfo-telegram-sync
journalctl -u cfo-telegram-sync -f
```

## Fluxo de conexão

1. User cria bot via @BotFather no Telegram → obtém token
2. User adiciona bot no painel → daemon registra webhook automaticamente
3. Usuário envia mensagem → webhook → pipeline chat_messages → Marcos responde

## Logs

`~/.agente-cfo/logs/telegram-sync.log`
