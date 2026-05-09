# Troubleshooting — Agente CFO

Guia de diagnóstico para os problemas mais comuns. Para cada problema: sintoma, causa provável e solução.

> **Dica:** Comece sempre pelo diagnóstico automático:
> ```bash
> bash ~/.openclaw/workspace/skills/agente-cfo/scripts/doctor.sh
> ```
> O output indica com `✅` / `❌` / `⚠️` o estado de cada componente.

---

## 1. WhatsApp não pareia

### Sintoma
O QR code aparece mas o pareamento falha, ou o setup trava em "Aguardando pareamento...".

### Causas e soluções

**QR code expirou antes de escanear**  
O QR expira em ~20 segundos. O `wacli` gera um novo automaticamente. Tente mais rápido ou aproxime mais o celular.

**Número já conectado em outro dispositivo**  
O WhatsApp só permite 1 pareamento `wacli` por número. Se o número já está pareado em outro lugar, desconecte primeiro:
```
WhatsApp → Aparelhos conectados → [seu aparelho wacli] → Desconectar
```

**App WhatsApp desatualizado**  
Atualize o WhatsApp no celular. Versões antigas às vezes não leem o QR gerado pelo `wacli`.

**Número de chip novo (restrição Meta)**  
Chips novos ativados há menos de 24h podem ter restrições de pareamento de aparelhos vinculados. Aguarde 24h.

**Verificar status atual do pareamento:**
```bash
wacli status
```
Output esperado: `{"connected": true, "phone": "+55119..."}`.

---

## 2. Setup.sh aborta no PASSO X

### Como identificar o passo
O output mostra `[CFO] PASSO X/13 — ...` antes do erro. Cada passo e suas falhas comuns:

**PASSO 1 — Dependências do sistema**
```
Causa: apt falhando, VPS sem internet, permissão negada.
Solução: rode `sudo apt update` manualmente. Confira se tem acesso root.
```

**PASSO 2 — Node.js / OpenClaw**
```
Causa: versão do Node.js incompatível (precisa v18+).
Diagnóstico: node --version
Solução: instale via nvm:
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  source ~/.bashrc
  nvm install 20
  nvm use 20
```

**PASSO 4 — PANEL_BASE_URL inválida**
```
Causa: URL no formato errado ou sem /functions/v1 no final.
Formato correto: https://<ref>.supabase.co/functions/v1
```

**PASSO 5 — Gateway não sobe**
```
Causa: porta 18789 ocupada, config corrompida, secrets ausentes.
Diagnóstico:
  openclaw gateway status
  openclaw status
Solução: veja seção 3 abaixo.
```

**PASSO 7 — Pareamento WhatsApp**
```
Causa: QR expirou, número bloqueado. Veja seção 1 acima.
```

**PASSO 8 — Cloudflare Tunnel**
```
Causa: cloudflared não instalado, sem internet, firewall bloqueando.
Veja seção 4 abaixo.
```

**PASSO 11 — Skill agente-cfo**
```
Causa: falha no clone do monorepo (repo privado? sem git? sem internet?).
Diagnóstico:
  git clone --depth 1 https://github.com/MindOpsTeam/agente-cfo.git /tmp/test-clone
  rm -rf /tmp/test-clone
```

**Passo genérico — .env ausente ou incompleto**
```
Diagnóstico:
  cat ~/.agente-cfo/.env
Variáveis obrigatórias:
  ANTHROPIC_API_KEY, CFO_WHATSAPP_TO, CFO_ERP_NAME, PANEL_BASE_URL, PANEL_TOKEN
```

Para reexecutar o setup a partir do zero (idempotente):
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh)
```

---

## 3. Gateway não sobe

### Sintoma
`openclaw gateway status` retorna `inactive` ou `failed`. Marcos não responde nada.

### Diagnóstico

```bash
# Ver status do serviço systemd
systemctl status openclaw-gateway

# Ver logs recentes
journalctl -u openclaw-gateway -n 50 --no-pager

# Verificar config do gateway
openclaw status
```

### Causas comuns

**`gateway.mode` ausente na config**  
O gateway precisa de um modo definido. Verifique:
```bash
openclaw config get gateway.mode
```
Se vazio, defina:
```bash
openclaw config set gateway.mode agent
```

**Secrets do OpenClaw ausentes ou corrompidos**  
```bash
ls ~/.openclaw/secrets/
# Deve ter: openclaw.env ou similar com ANTHROPIC_API_KEY
```

**Porta 18789 já em uso**  
```bash
lsof -i :18789
# Se outro processo estiver usando, kill ele antes de subir o gateway
```

**Reiniciar o gateway:**
```bash
openclaw gateway restart
# Aguardar 5 segundos
openclaw gateway status
```

---

## 4. Tunnel Cloudflare sem URL

### Sintoma
O setup pede pra esperar a URL do tunnel e ela nunca aparece. Ou o tunnel sobe mas a URL muda a cada restart (tunnel efêmero).

### Diagnóstico

```bash
systemctl status cloudflared
journalctl -u cloudflared -n 30 --no-pager
```

### Causas e soluções

**`cloudflared` não instalado**  
```bash
which cloudflared || apt install cloudflared
```

**Firewall bloqueando saída na porta 7844 (Cloudflare)**  
O cloudflared precisa de saída TCP nas portas 7844 e 443. Verifique com:
```bash
curl -v https://api.cloudflare.com/client/v4/ips 2>&1 | head -5
```

**Tunnel efêmero (URL muda todo restart)**  
O setup usa tunnel efêmero por padrão. Isso é intencional para o MVP. Se quiser uma URL fixa, configure um tunnel nomeado via `cloudflared tunnel create agente-cfo` com conta Cloudflare. A URL do painel (`ingress_url`) precisa ser atualizada após cada reinicialização neste caso.

**Verificar URL ativa do tunnel:**
```bash
grep INGRESS_URL ~/.agente-cfo/instance.env
```

---

## 5. OAuth Bling / ContaAzul falha

### Sintoma
`connect.sh` retorna `Falha ao obter tokens` ou a API responde 401/400 após o authorization code.

### Causas e soluções

**Client ID ou Client Secret incorretos**  
Copie novamente do painel de developers do sistema. Não confunda com o ID de integração (são diferentes).

**Redirect URI mismatch**  
O app OAuth precisa ter exatamente `urn:ietf:wg:oauth:2.0:oob` no campo de Redirect URI. Qualquer espaço ou caractere extra quebra.

**Authorization code expirado**  
O código gerado após autorizar no browser tem validade curta (~60 segundos no Bling). Cole-o imediatamente no terminal.

**Refresh token inválido após período longo sem uso**  
Bling e ContaAzul podem invalidar o refresh token após longos períodos de inatividade. Reconecte:
```bash
# Bling
bash ~/.openclaw/workspace/skills/bling/scripts/connect.sh --force

# ContaAzul
bash ~/.openclaw/workspace/skills/contaazul/scripts/connect.sh --force
```

**Verificar token atual:**
```bash
# Ver expiração
grep TOKEN_EXPIRY ~/.openclaw/secrets/bling.env
python3 -c "import time; e=int(open('$HOME/.openclaw/secrets/bling.env').read().split('BLING_TOKEN_EXPIRY=')[1].split()[0]); print(f'Expira em {int((e-time.time())/60)} min')"
```

---

## 6. Marcos não responde no WhatsApp

### Sintoma
Você manda mensagem no WhatsApp mas não recebe resposta. Ou a resposta demora mais de 30 segundos.

### Diagnóstico em ordem

```bash
# 1. Gateway está rodando?
openclaw gateway status

# 2. wacli-inbound está rodando?
systemctl status wacli-inbound
journalctl -u wacli-inbound -n 20 --no-pager

# 3. WhatsApp ainda pareado?
wacli status

# 4. API key Anthropic válida?
grep ANTHROPIC_API_KEY ~/.agente-cfo/.env

# 5. Testar a Anthropic diretamente
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $(grep ANTHROPIC_API_KEY ~/.agente-cfo/.env | cut -d= -f2)" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-20240307","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}'
```

### Causas comuns

**Gateway caiu** → `openclaw gateway restart`

**wacli-inbound parado:**
```bash
systemctl restart wacli-inbound
journalctl -u wacli-inbound -f   # acompanhar logs em tempo real
```

**WhatsApp despareado (sessão expirou):**
```bash
wacli qr   # gera novo QR para reparear
```

**Anthropic API Key inválida ou com saldo zerado**  
Verifique em [console.anthropic.com](https://console.anthropic.com) → Usage / API Keys.

**Número errado no CFO_WHATSAPP_TO**  
O `wacli-inbound` só escuta mensagens do número configurado em `CFO_WHATSAPP_TO`. Verifique:
```bash
grep CFO_WHATSAPP_TO ~/.agente-cfo/.env
```

---

## 7. Eventos não chegam ao painel

### Sintoma
O painel não exibe alertas ou o status fica estático. O agente funciona mas não aparece no dashboard.

### Diagnóstico

```bash
# Ver logs de envio para o painel
grep "panel" ~/.agente-cfo/logs/proactive.log | tail -20

# Testar conexão com o painel manualmente
source ~/.agente-cfo/.env
curl -s -X POST "${PANEL_BASE_URL}/event" \
  -H "Content-Type: application/json" \
  -H "X-Panel-Token: ${PANEL_TOKEN}" \
  -d '{"instance_id":"test","type":"ping","severity":"info","payload":{}}'
```

### Causas comuns

**PANEL_TOKEN diferente entre VPS e Supabase**  
O token gerado pelo setup precisa ser o mesmo configurado em **Supabase → Edge Functions → Secrets → PANEL_TOKEN**. Se regenerou o token no setup mas não atualizou no Supabase, tudo falha silenciosamente.

**PANEL_BASE_URL desatualizada**  
Se mudou o projeto Supabase, atualize:
```bash
grep PANEL_BASE_URL ~/.agente-cfo/.env
# Se errado:
sed -i "s|PANEL_BASE_URL=.*|PANEL_BASE_URL=https://novo-ref.supabase.co/functions/v1|" ~/.agente-cfo/.env
openclaw gateway restart
```

**Edge Functions não deployadas**  
Se as migrations foram aplicadas mas as edge functions não foram deployadas, o painel responde 404.
```bash
cd painel/
supabase functions deploy --project-ref <ref>
```

**ingress_url do tunnel offline**  
O painel envia comandos de volta para a VPS via `ingress_url`. Se o tunnel caiu, os comandos falham mas os eventos ainda chegam (sentido VPS→Supabase). Verifique o tunnel (seção 4).

---

## 8. Cron jobs não disparam

### Sintoma
As mensagens de 07:00 e 18:00 não chegam no WhatsApp.

### Diagnóstico

```bash
# Listar cron jobs registrados
openclaw cron list

# Ver runs do último cron de alerta
openclaw cron runs <job-id>

# Verificar horário do servidor (precisa bater com America/Sao_Paulo)
date
timedatectl
```

### Causas comuns

**Timezone errada na VPS**  
Os crons são definidos com timezone `America/Sao_Paulo`. Se a VPS está em UTC e o cron não especifica timezone, dispara no horário errado.
```bash
timedatectl set-timezone America/Sao_Paulo
```

**Cron jobs não foram registrados**  
Se o setup abortou antes do PASSO 12, os crons podem não ter sido criados. Reexecute o setup ou registre manualmente:
```bash
# Ver se os jobs existem
openclaw cron list
# Se vazio, reexecute o setup (é idempotente)
bash <(curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh)
```

**Gateway offline no horário do disparo**  
O cron dispara mas o gateway não está rodando para processar. Garanta que o gateway sobe automaticamente:
```bash
systemctl enable openclaw-gateway
```

---

## 9. Como ler o output do doctor.sh

O `doctor.sh` verifica todos os componentes. Legenda:

| Símbolo | Significado |
|---|---|
| `✅` | Componente ok |
| `❌` | Componente com falha — ação necessária |
| `⚠️` | Aviso — funciona mas atenção recomendada |

**Output esperado numa instalação saudável:**

```
=== doctor.sh [agente-cfo] ===
✅ OpenClaw: gateway rodando
✅ wacli: pareado (+55119XXXXXXXX)
✅ ERP (omie): API acessível
✅ CRM: não configurado (ok)
✅ Cron jobs: alerta_manha + alerta_tarde registrados
✅ Tunnel: https://xxx.trycloudflare.com
✅ Painel: registrado (instance_id: abc123)
✅ wacli-inbound: rodando
✅ cfo-proactive: rodando
```

**Rodando doctor de uma skill específica:**
```bash
# ERP
bash ~/.openclaw/workspace/skills/omie/scripts/doctor.sh

# CRM
bash ~/.openclaw/workspace/skills/hubspot/scripts/doctor.sh
```

---

## 10. Logs úteis

| Log | Caminho |
|---|---|
| Watcher proativo | `~/.agente-cfo/logs/proactive.log` |
| Gateway OpenClaw | `journalctl -u openclaw-gateway -n 100` |
| wacli-inbound | `journalctl -u wacli-inbound -n 100` |
| cfo-proactive | `journalctl -u cfo-proactive -n 100` |
| Alertas enviados | `~/.agente-cfo/state/proactive_alerts.json` |

---

Não encontrou seu problema aqui? Abra uma issue no [repositório](https://github.com/MindOpsTeam/agente-cfo/issues) com o output do `doctor.sh`.
