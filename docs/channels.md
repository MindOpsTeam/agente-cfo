# Pipeline Cross-Channel — Agente CFO

## Sprint 35 — arquitetura unificada

Qualquer mensagem externa (WhatsApp, Telegram) segue o mesmo pipeline interno.
Marcos tem os mesmos tools, MCPs e contexto em todos os canais.

---

## Arquitetura

```
WhatsApp (Evolution API)
    │  POST /whatsapp-incoming-webhook  (thin wrapper)
    ↓
Telegram
    │  POST /telegram-incoming-webhook  (thin wrapper)
    ↓
        ┌─────────────────────────────────────┐
        │   POST /incoming-message            │
        │   (entrada única, verify_jwt=false)  │
        │                                     │
        │  1. valida secret por canal          │
        │  2. insere chat_messages (user)      │
        │  3. insere placeholder Marcos        │
        │  4. dispara /hooks/agent na VPS      │
        └───────────────┬─────────────────────┘
                        │
                        ↓ POST /hooks/agent
              ┌─────────────────────────────┐
              │   OpenClaw VPS — Marcos      │
              │   tools, MCPs, contexto      │
              └──────────┬──────────────────┘
                         │
          ┌──────────────┼──────────────────┐
          ↓              ↓                  ↓
    send_evolution.sh  send_telegram.sh  panel_reply.sh
    (WhatsApp)         (Telegram)        (painel web)
          └──────────────┼──────────────────┘
                         ↓
              POST /chat-marcos-reply
              (grava no histórico)
```

---

## Thread IDs por canal

| Canal | Formato | Exemplo |
|-------|---------|---------|
| Painel web | `panel:<user_id>` | `panel:abc-123-uuid` |
| WhatsApp | `wa:<instance>:<phone>` | `wa:principal:5548992044331` |
| Telegram | `tg:<bot_username>:<chat_id>` | `tg:marcoscfo_bot:987654321` |

## Channel values em chat_messages

| Canal | Valor | Exemplo |
|-------|-------|---------|
| Painel web | `panel` | `panel` |
| WhatsApp | `whatsapp:<instance>` | `whatsapp:principal` |
| Telegram | `telegram:<bot>` | `telegram:marcoscfo_bot` |

---

## Edge functions (painel)

| Função | Auth | Descrição |
|--------|------|-----------|
| `/incoming-message` | webhook_secret | Entrada única para canais externos |
| `/whatsapp-incoming-webhook` | X-Webhook-Secret | Thin wrapper Evolution → incoming-message |
| `/telegram-incoming-webhook` | ?secret= query | Thin wrapper Telegram → incoming-message |
| `/chat-send-message` | JWT Supabase | Canal painel web (usuário logado) |
| `/chat-marcos-reply` | X-Panel-Token | VPS grava resposta do Marcos |

---

## Scripts VPS

| Script | Uso |
|--------|-----|
| `panel_post_reply.sh <channel> <external_id> <reply>` | Resposta unificada (Marcos chama) |
| `send_evolution.sh <instance> <phone> <text>` | WhatsApp via Evolution |
| `send_telegram.sh <bot_username> <chat_id> <text>` | Telegram via Bot API |
| `panel_reply.sh <thread_id> <run_id> <content>` | Grava no histórico do painel |

---

## Prompt Marcos (exemplo WhatsApp)

```
[WHATSAPP_CHAT]
Canal: WhatsApp (instância: principal)
De: Guilherme
ID externo: 5548992044331
Mensagem: Qual o saldo da conta?

Você é Marcos, CFO virtual. Responda em português...

Quando terminar, RESPONDA no canal de origem e grave no histórico:
  bash "$HOME/.openclaw/workspace/skills/evolution-api/scripts/send_evolution.sh" \
    "principal" "5548992044331" "<sua resposta>"
  bash "$HOME/.openclaw/workspace/skills/agente-cfo/scripts/panel_reply.sh" \
    "wa:principal:5548992044331" "ext_1234_abc" "<sua resposta>" "sent"
```

---

## Adicionar novo canal (extensibilidade)

1. Criar thin wrapper edge function (valida secret → chama `/incoming-message`)
2. Adicionar case em `channel_utils.ts` → `getThreadId()` e `buildReplyInstructions()`
3. Criar helper `send_<canal>.sh` na skill correspondente
4. Adicionar case em `panel_post_reply.sh`
5. Registrar webhook no serviço externo apontando pro wrapper

---

## FAQ

**Por que thin wrappers e não entrada direta em /incoming-message?**
Cada serviço tem seu próprio formato de payload (Evolution vs Telegram Update object).
Os wrappers lidam com parsers específicos, e incoming-message recebe formato normalizado.

**Marcos enxerga o histórico de outros canais?**
Thread separado por canal/contato. O histórico do WhatsApp não aparece no Telegram
(e vice-versa). O histórico do painel web também é isolado. Em sprint futuro:
view unificada por usuário identificado.

**Como testar sem Evolution/Telegram reais?**
```bash
curl -X POST https://<tunnel>/functions/v1/incoming-message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "whatsapp:test",
    "external_id": "5511999999999",
    "text": "Teste",
    "secret": "<webhook_secret_da_instância>"
  }'
```
