# OpenClaw Gateway — Protocolo para clientes browser

> **Sprint 31 — investigação real, testado em OpenClaw 2026.3.28**

## TL;DR para o Lovable AI

O gateway tem **dois caminhos viáveis** para o painel web:

### Caminho A — `/tools/invoke` HTTP (mais simples, já funciona)

```http
POST http://<tunnel-url>/tools/invoke
Authorization: Bearer <gateway.auth.token>
Content-Type: application/json

{ "tool": "sessions_list", "args": {}, "sessionKey": "main" }
```

Funciona agora, sem configuração extra, com o `gateway.auth.token` atual.
Limitação: não suporta streaming de texto e não pode disparar `sessions_send` (policy).

### Caminho B — `/v1/chat/completions` SSE streaming (requer config extra)

```json
// openclaw.json — adicionar:
{
  "gateway": {
    "http": { "endpoints": { "chatCompletions": { "enabled": true } } },
    "controlUi": { "dangerouslyDisableDeviceAuth": true, "allowInsecureAuth": true }
  }
}
```

```http
POST https://<tunnel-url>/v1/chat/completions
Authorization: Bearer <gateway.auth.token>
Content-Type: application/json

{
  "model": "openclaw",
  "messages": [{"role":"user","content":"Qual o saldo atual?"}],
  "stream": true,
  "max_tokens": 2048
}
```

Resposta: `text/event-stream` (SSE), formato OpenAI-compatible.

### Caminho C — WebSocket nativo (máximo controle, mais complexo)

Requer device pairing ou `dangerouslyDisableDeviceAuth=true`.
Ver seção "WebSocket avançado" abaixo.

---

## URL de conexão

| Ambiente | URL |
|----------|-----|
| VPS (produção) | `https://<tunnel>.trycloudflare.com/` |
| Local dev | `http://localhost:18789/` (requer `allowInsecureAuth=true`) |

O Cloudflare Tunnel suporta WebSocket upgrade automaticamente (sem config extra).

## Autenticação

Token em `~/.openclaw/openclaw.json` → `gateway.auth.token` (48 chars hex).

**HTTP API:**
```
Authorization: Bearer <token>
```

**WebSocket:**
```json
{ "auth": { "token": "<token>" } }
```
(incluído no payload do `connect` request, não no header HTTP)

---

## WebSocket — Protocolo completo

### 1. Sequência de handshake

```
Gateway → Client: connect.challenge  (nonce + ts)
Client  → Gateway: connect request   (role + scopes + auth.token)
Gateway → Client: hello-ok           (protocol version + features)
```

### 2. connect request (valores obrigatórios testados)

```json
{
  "type": "req",
  "id": "c1",
  "method": "connect",
  "params": {
    "minProtocol": 3,
    "maxProtocol": 3,
    "client": {
      "id": "cli",
      "version": "1.0.0",
      "platform": "macos",
      "mode": "cli"
    },
    "role": "operator",
    "scopes": ["operator.read", "operator.write"],
    "caps": [],
    "commands": [],
    "permissions": {},
    "auth": { "token": "<gateway.auth.token>" },
    "locale": "pt-BR",
    "userAgent": "painel-cfo/1.0"
  }
}
```

**Valores válidos de `client.id`** (enum estrito):
```
"cli"                  ✓ funciona com token simples
"openclaw-tui"         ✓ funciona com token simples
"webchat-ui"           ⚠ requer origin permitida
"webchat"              ⚠ requer origin permitida
"openclaw-control-ui"  ⚠ requer origin permitida
```

**Valores válidos de `client.mode`:**
```
"cli" | "webchat" | "ui" | "backend" | "node" | "probe" | "test"
```

### 3. Framing de mensagens

| Tipo | Formato |
|------|---------|
| Request | `{type:"req", id, method, params}` |
| Response | `{type:"res", id, ok, payload \| error}` |
| Event | `{type:"event", event, payload, seq?}` |

### 4. Métodos WS disponíveis (pós-connect)

| Método | Scope mínimo | Descrição |
|--------|-------------|-----------|
| `health` | nenhum | Status do gateway |
| `config.get` | operator.read | Lê config |
| `chat.send` | operator.write + device token | Envia mensagem ao agente |
| `agent.run` | operator.admin + device token | Roda agente isolado |
| `sessions.send` | operator.admin + device token | Envia para sessão específica |

> ⚠️ **Token simples não tem scopes de escrita** — só `health` e `config.get` funcionam
> sem device pairing. Para `chat.send`, use `/tools/invoke` HTTP ou ative
> `dangerouslyDisableDeviceAuth=true`.

### 5. Eventos recebidos (server-push)

| Event | Quando | Payload relevante |
|-------|--------|-------------------|
| `connect.challenge` | Ao conectar | `{nonce, ts}` |
| `health` | Periódico (~15s) | `{ok, ts, channels}` |
| `system-presence` | Ao conectar | lista de devices |
| `chat.message` | Resposta do agente | `{sessionKey, message}` |
| `chat.session.update` | Fim de run | `{sessionKey, status}` |
| `exec.approval.requested` | Exec pendente | `{requestId, command}` |

---

## Configuração para browser (CORS + auth)

```bash
# Permite origem do painel
openclaw config set 'gateway.controlUi.allowedOrigins' '["https://painel.lovable.app", "*"]' --strict-json

# Permite HTTP inseguro (se não usar HTTPS)
openclaw config set 'gateway.controlUi.allowInsecureAuth' true --strict-json

# Desabilita device pairing (permite token simples fazer escrita via browser)
# ⚠️ Segurança reduzida — só em deploy controlado
openclaw config set 'gateway.controlUi.dangerouslyDisableDeviceAuth' true --strict-json

# Habilita /v1/chat/completions
openclaw config set 'gateway.http.endpoints.chatCompletions' '{"enabled":true}' --strict-json

# Reinicia para aplicar
openclaw gateway restart
```

---

## Exemplo JS standalone (para debug)

Ver: `skills/agente-cfo/scripts/ws_chat_example.html`

---

## Recuperação de desconexão (browser)

```javascript
let retryDelay = 1000;

function connectWithRetry() {
  const ws = new WebSocket(`wss://${TUNNEL}/`);
  ws.onclose = () => {
    setTimeout(connectWithRetry, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 30000); // backoff até 30s
  };
  ws.onopen = () => { retryDelay = 1000; };
}
```

---

## Fluxo atual do painel (sem mudanças)

```
Painel → edge fn chat-send-message → POST /hooks/agent (ingress_url)
       → Marcos processa → panel_reply.sh → POST /whatsapp-incoming-webhook
       → Painel atualiza via Supabase realtime
```

Este fluxo continua funcionando e é recomendado para o MVP.
WebSocket direto é upgrade opcional para streaming em tempo real.

---

## Limitações conhecidas

1. **Token simples vs device token**: O `gateway.auth.token` sozinho não tem `operator.write` via WS. Para streaming real, precisa de `dangerouslyDisableDeviceAuth=true` ou device pairing.
2. **Browser origin check**: IDs de cliente "browser" (webchat-ui, webchat) são bloqueados se a origem não estiver em `allowedOrigins`.
3. **`/v1/chat/completions` requer device scope**: Mesmo habilitado, retorna `403 missing scope: operator.write` sem `dangerouslyDisableDeviceAuth`.
4. **`/tools/invoke` não suporta sessões_send**: Está na deny list padrão do endpoint HTTP.
5. **Cloudflare Tunnel**: WS upgrade é transparente — funciona sem config extra.
