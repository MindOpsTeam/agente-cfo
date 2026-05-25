# SPRINT CHAN-1 — Prompts Lovable AI (PM executa)

**Sprint:** CHAN-1 — Pareamento WhatsApp + Telegram 100% pelo painel  
**Data:** 2026-05-25  
**Backend:** concluído (scripts + migration + smoke test)  
**Próximo passo:** PM dispara os 3 prompts abaixo no Lovable AI em sequência

---

## ⚠️ Ordem de execução

Execute os prompts **na ordem**: 1 → 2 → 3.
Aguarde o deploy de cada um antes de disparar o próximo.

---

## Prompt 1 — Deploy da Edge Function `telegram-webhook` (já existe no repo)

```
A edge function `telegram-webhook` já existe no repositório em
`supabase/functions/telegram-webhook/index.ts` mas ainda não foi deployada.

Por favor:
1. Confirme que o arquivo `supabase/functions/telegram-webhook/index.ts` existe
   e está completo (deve ter Deno.serve, validação de secret via query param,
   lookup em telegram_bots, e chamada para /incoming-message).
2. Se existir e estiver correto, faça o deploy via `supabase functions deploy telegram-webhook`.
3. Certifique-se que a função roda com `verify_jwt=false` (configurado em
   `supabase/functions/telegram-webhook/config.toml` ou equivalente), pois ela
   é chamada diretamente pelo Telegram Bot API, não por usuários autenticados.
4. Confirme o URL público da função após o deploy.

NÃO modifique a lógica interna da função — só garanta o deploy.
```

---

## Prompt 2 — 2 novas Edge Functions no painel

```
Crie duas novas edge functions Supabase no painel agente-cfo.
Ambas requerem JWT válido (verify_jwt=true).

---

### Edge Function 1: `whatsapp-pair-start`

**Arquivo:** `supabase/functions/whatsapp-pair-start/index.ts`
**Auth:** verify_jwt=true
**Método:** POST

**Body esperado:**
```json
{ "instance_name": "string" }
```

**Comportamento:**
1. Valida JWT do usuário (via Supabase auth, já garantido pelo verify_jwt).
2. Valida que `instance_name` é string não-vazia com apenas alnum/hifen/underscore.
3. Faz POST para `${HOOKS_URL}/hooks/agent` na VPS com o body:
   ```json
   {
     "message": "[ADMIN_ACTION] whatsapp_pair_new --instance <instance_name>",
     "source": "panel"
   }
   ```
   Header: `Authorization: Bearer ${HOOKS_TOKEN}` (secret do Supabase).
4. Retorna:
   ```json
   {
     "ok": true,
     "instance_name": "<instance_name>",
     "polling_field": "qr_code_b64",
     "polling_table": "whatsapp_instances",
     "message": "QR code sendo gerado. Faça polling de whatsapp_instances.qr_code_b64 a cada 2s."
   }
   ```
   Em caso de erro no hooks, retorna `{"ok": false, "error": "<msg>"}` com HTTP 502.

**Secrets necessários (já devem existir):**
- `HOOKS_URL` — URL base da VPS onde roda o agente
- `HOOKS_TOKEN` — token de autenticação dos hooks

---

### Edge Function 2: `telegram-webhook-register`

**Arquivo:** `supabase/functions/telegram-webhook-register/index.ts`
**Auth:** verify_jwt=true
**Método:** POST

**Body esperado:**
```json
{
  "bot_token": "string",
  "bot_name": "string (opcional, label amigável)"
}
```

**Comportamento:**
1. Valida JWT.
2. Valida que `bot_token` tem formato `[0-9]+:[A-Za-z0-9_-]+`.
3. GET `https://api.telegram.org/bot<TOKEN>/getMe`
   - Se `ok: false` → retorna erro `{"ok": false, "error": "Token inválido: <desc>"}` HTTP 400.
   - Extrai `result.username` e `result.first_name`.
4. Gera `webhook_secret` aleatório: `crypto.randomUUID()`.
5. Monta webhook URL:
   `${SUPABASE_URL}/functions/v1/telegram-webhook?secret=${webhook_secret}`
6. POST `https://api.telegram.org/bot<TOKEN>/setWebhook`
   Body: `{ "url": "<webhook_url>", "allowed_updates": ["message"] }`
   - Se não OK → retorna erro HTTP 502.
7. INSERT em `telegram_bots`:
   ```sql
   INSERT INTO telegram_bots (bot_token, bot_username, webhook_secret, active, receives_marcos_chat)
   VALUES ($1, $2, $3, true, false)
   ON CONFLICT (bot_username) DO UPDATE SET
     bot_token = EXCLUDED.bot_token,
     webhook_secret = EXCLUDED.webhook_secret,
     active = true
   ```
8. Retorna:
   ```json
   {
     "ok": true,
     "bot_username": "@<username>",
     "bot_name": "<first_name>",
     "webhook_url": "<url configurada>"
   }
   ```

**Secrets necessários:**
- `SUPABASE_URL` — URL do projeto Supabase (para montar o webhook URL)
- Service role key para INSERT (já disponível via adminClient ou env).
```

---

## Prompt 3 — UI Updates (3 componentes)

```
Implemente 3 updates de UI no painel agente-cfo:

---

### Update A: `/settings/whatsapp` — Modal de pareamento com QR

Na página de configurações de WhatsApp (ou crie `/settings/whatsapp` se não existir):

1. Adicione botão **"Parear instância"** que abre um modal.
2. O modal contém:
   - Campo de texto para `instance_name` (label: "Nome da instância")
   - Botão "Gerar QR Code"
3. Ao clicar "Gerar QR Code":
   a. Chama a edge function `whatsapp-pair-start` com `{ instance_name }`.
   b. Exibe spinner "Gerando QR...".
   c. Faz **polling a cada 2 segundos** da tabela `whatsapp_instances`
      filtrando por `instance_name`, lendo o campo `qr_code_b64`.
   d. Quando `qr_code_b64` não é null/vazio, renderiza a imagem:
      ```html
      <img src="data:image/png;base64,<qr_code_b64>" alt="QR Code WhatsApp" />
      ```
   e. Instrução ao usuário: "Abra o WhatsApp no celular → Aparelhos conectados → Conectar aparelho → Escanear QR"
4. Continua polling até `whatsapp_instances.status` virar `'open'`:
   - Quando `status === 'open'`: fecha modal, exibe toast "✅ WhatsApp conectado!"
   - Timeout em 5 minutos: exibe "QR expirado. Tente novamente."
   - Intervalo de polling: 2 segundos.
5. Use o hook `useSupabase` existente para o polling (ou `supabase.from('whatsapp_instances').select(...).eq('instance_name', name)`).

---

### Update B: `/settings/telegram` — Registro automático de webhook

Na página de configurações do Telegram (ou crie se não existir):

1. Substitua qualquer instrução manual de curl/webhook por um formulário:
   - Campo: **Bot Token** (placeholder: `1234567890:ABCdef...`)
   - Campo: **Nome do bot** (opcional, para identificação)
   - Botão: "Registrar Bot"
2. Ao submeter:
   a. Chama a edge function `telegram-webhook-register` com `{ bot_token, bot_name }`.
   b. Exibe spinner "Registrando...".
   c. Em caso de sucesso: toast "✅ Bot @<username> registrado! Webhook configurado automaticamente."
   d. Em caso de erro: toast vermelho com a mensagem de erro.
3. Abaixo do formulário, lista os bots registrados (query em `telegram_bots` onde `active=true`),
   mostrando: `bot_username`, status ativo/inativo, botão "Desativar".

---

### Update C: Dashboard — Banner "WhatsApp Offline"

No Dashboard principal (`/dashboard`):

1. Adicione query Supabase para buscar instâncias WhatsApp:
   ```typescript
   const { data: waInstances } = await supabase
     .from('whatsapp_instances')
     .select('instance_name, status, updated_at')
     .neq('status', 'open')
   ```
2. Se houver instâncias com `status != 'open'` E `updated_at` nos últimos 5 minutos
   (indica que a VPS está ativa mas o WA desconectou):
   - Mostre card no topo do dashboard:
     ```
     🔴 WhatsApp desconectou — <instance_name>
     [Reparear agora →]
     ```
   - Card vermelho (use `bg-red-50 border-red-200 text-red-800` ou equivalente do design system).
   - Botão "Reparear agora" navega para `/settings/whatsapp` e abre o modal de pareamento
     automaticamente (via query param `?pair=<instance_name>`).
3. Se não houver instâncias offline: não renderiza nada (sem card vazio).
4. Atualize a query automaticamente a cada 30 segundos (use `useInterval` ou `refetchInterval`).

**Importante:** NÃO modificar os componentes existentes `ActivityFeed` e `cfo-write-events`.
O banner é um card independente acima deles.
```

---

## Checklist pós-deploy (PM valida)

- [ ] `telegram-webhook` deployada e acessível publicamente
- [ ] `whatsapp-pair-start` deployada, requer JWT
- [ ] `telegram-webhook-register` deployada, requer JWT
- [ ] Migration `20260525000001_whatsapp_qr_storage.sql` aplicada via `lovable_query_sql`
- [ ] `/settings/whatsapp` mostra botão Parear + modal com QR polling
- [ ] `/settings/telegram` tem formulário de registro automático
- [ ] Dashboard mostra banner vermelho quando WA desconecta
- [ ] Instâncias existentes (ex: cfo-test-01) continuam funcionando sem alteração
