# Integrações — Agente CFO

Guia de configuração por skill. Para cada integração: como gerar as credenciais no sistema externo, o que o Marcos consegue fazer e as limitações conhecidas.

---

## ERPs

### Omie

**Auth:** App Key + App Secret (gerados por aplicativo cadastrado na conta Omie).

**Como gerar as credenciais:**

1. Acesse [app.omie.com.br](https://app.omie.com.br) → menu do usuário → **Configurações** → **API**
2. Clique em **"Novo Aplicativo"**
3. Dê um nome (ex: "Agente CFO") e salve
4. Copie o **App Key** e o **App Secret** gerados

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/omie/scripts/connect.sh
```

**Capacidades:**

| Operação | Suporte |
|---|---|
| Saldo atual | ✅ |
| Contas a receber (filtro por data) | ✅ |
| Contas a pagar (filtro por data) | ✅ |
| Inadimplência | ✅ |
| Projeção de caixa 30/90 dias | ✅ |
| Baixar conta a pagar | ✅ |
| Baixar conta a receber | ✅ |
| Criar lançamento | ✅ |
| Cancelar lançamento | ✅ |

**Limitações:** A API Omie tem rate limit de 10 req/s por aplicativo. Em operações de listagem com muitos registros, a skill usa paginação automática.

**Doc oficial:** [developer.omie.com.br](https://developer.omie.com.br)

---

### Bling

**Auth:** OAuth 2.0 — Authorization Code Flow com refresh token automático.

**Como gerar as credenciais:**

1. Acesse [developer.bling.com.br](https://developer.bling.com.br) → **Meus apps** → **Novo App**
2. Preencha nome, descrição
3. Redirect URI: `urn:ietf:wg:oauth:2.0:oob`
4. Copie o **Client ID** e o **Client Secret**

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/bling/scripts/connect.sh
```

O script abre a URL de autorização no terminal. Você autoriza no browser e cola o código.

**Capacidades:**

| Operação | Suporte |
|---|---|
| Saldo (contas correntes) | ✅ |
| Contas a receber | ✅ |
| Contas a pagar | ✅ |
| Projeção de caixa | ✅ |
| Baixar conta a pagar | ✅ |
| Baixar conta a receber | ✅ |
| Criar lançamento | ✅ |

**Limitações:** O refresh token do Bling pode expirar após longos períodos sem uso. Se isso ocorrer, execute `connect.sh --force`.

**Doc oficial:** [developer.bling.com.br/documentacao](https://developer.bling.com.br/documentacao)

---

### Tiny ERP

**Auth:** Token de API (gerado nas configurações da conta).

**Como gerar as credenciais:**

1. Acesse sua conta Tiny → **Configurações** → **Integrações** → **API**
2. Clique em **"Gerar token"**
3. Copie o token

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/tiny/scripts/connect.sh
```

**Capacidades:**

| Operação | Suporte |
|---|---|
| Saldo | ✅ |
| Contas a receber/pagar | ✅ |
| Projeção de caixa | ✅ |
| Write operations | ⚠️ Parcial — depende do plano |

**Limitações:** A API do Tiny v2 tem funcionalidades de escrita limitadas em planos básicos.

**Doc oficial:** [ajuda.tiny.com.br/api](https://ajuda.tiny.com.br/api)

---

### Granatum

**Auth:** Access Token da conta.

**Como gerar as credenciais:**

1. Acesse [app.granatum.com.br](https://app.granatum.com.br) → **Configurações** → **Integrações** → **API**
2. Copie o **Access Token**

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/granatum/scripts/connect.sh
```

**Capacidades:**

| Operação | Suporte |
|---|---|
| Saldo | ✅ |
| Contas a receber/pagar | ✅ |
| Projeção de caixa | ✅ |
| Criar lançamento | ✅ |

**Limitações:** Granatum não expõe endpoint de baixa de conta via API pública. `pay_payable` e `mark_received` retornam `not_supported`.

**Doc oficial:** [developers.granatum.com.br](https://developers.granatum.com.br)

---

### VHSYS

**Auth:** Access Token + Secret Token (par de tokens por conta).

**Como gerar as credenciais:**

1. Acesse [sistema.vhsys.com.br](https://sistema.vhsys.com.br) → **Configurações** → **API**
2. Ative a API e copie o **Access Token** e o **Secret Token**

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/vhsys/scripts/connect.sh
```

**Capacidades:**

| Operação | Suporte |
|---|---|
| Saldo | ✅ |
| Contas a receber/pagar | ✅ |
| Projeção de caixa | ✅ |
| Write operations | ✅ |

**Doc oficial:** [vhsys.com.br/api](https://vhsys.com.br/api)

---

### Nibo

**Auth:** API Token (disponível apenas em planos Premium).

**Como gerar as credenciais:**

1. Acesse [app.nibo.com.br](https://app.nibo.com.br) → **Configurações** → **Integração** → **API**
2. O token aparece somente se o plano incluir acesso à API (Premium ou superior)
3. Copie o **API Token**

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/nibo/scripts/connect.sh
```

**Capacidades:**

| Operação | Suporte |
|---|---|
| Saldo | ✅ |
| Contas a receber/pagar | ✅ |
| Projeção de caixa | ✅ |
| Write operations | ⚠️ Limitado |

**Limitações:** A API do Nibo requer plano Premium. Sem o plano, o `connect.sh` retornará 401.

**Doc oficial:** [nibo.com.br/docs/api](https://nibo.com.br/docs/api)

---

### ContaAzul

**Auth:** OAuth 2.0 — Authorization Code Flow com refresh token automático.

**Como gerar as credenciais:**

1. Acesse [developers.contaazul.com](https://developers.contaazul.com) → **Meus Apps** → **Criar App**
2. Tipo: **Authorization Code**
3. Redirect URI: `urn:ietf:wg:oauth:2.0:oob`
4. Escopos: `financeiro`
5. Copie o **Client ID** e o **Client Secret**

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/contaazul/scripts/connect.sh
```

O script abre a URL de autorização. Você autoriza no browser e cola o código no terminal.

**Capacidades:**

| Operação | Suporte |
|---|---|
| Saldo (soma de contas financeiras ativas) | ✅ |
| Contas a receber | ✅ |
| Contas a pagar | ✅ |
| Projeção de caixa | ✅ |
| Baixar conta a pagar/receber | ✅ (PATCH status LIQUIDADO) |
| Criar lançamento | ✅ |
| Cancelar lançamento | ⚠️ PATCH status CANCELADO (sem DELETE nativo) |

**Limitações:** A API v1 pública do ContaAzul não expõe DELETE de parcelas. O cancelamento usa PATCH com `status: CANCELADO`, que pode não ser suportado em todas as versões de conta.

**Doc oficial:** [developers.contaazul.com/docs/financial-apis-openapi/v1](https://developers.contaazul.com/docs/financial-apis-openapi/v1)

---

## CRMs

### HubSpot

**Auth:** Private App Token (sem OAuth, sem expiração).

**Como gerar as credenciais:**

1. Acesse [app.hubspot.com](https://app.hubspot.com) → **Configurações** (engrenagem) → **Integrações** → **Apps Privados**
2. Clique em **"Criar app privado"**
3. Na aba **Escopos**, selecione:
   - `crm.objects.deals.read`
   - `crm.objects.deals.write`
   - `crm.objects.notes.write`
4. Crie o app e copie o **Token de Acesso**

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/hubspot/scripts/connect.sh
```

O connect.sh também busca e cacheia os pipeline stages automaticamente.

**Capacidades:**

| Operação | Suporte |
|---|---|
| Listar deals (open/won/lost) | ✅ |
| Pipeline summary por stage | ✅ |
| Projeção de pipeline 30/90 dias | ✅ |
| Mover deal para outro stage | ✅ |
| Atualizar deal (valor, data) | ✅ |
| Criar deal | ✅ |
| Adicionar nota ao deal | ✅ |
| Marcar como ganho/perdido | ✅ |

**Limitações:** Deals sem stage reconhecido como "won" ou "lost" são tratados como "open". O mapeamento de stages é cacheado em `~/.openclaw/secrets/hubspot_stages.json`.

**Doc oficial:** [developers.hubspot.com](https://developers.hubspot.com/docs/api/crm/deals)

---

### RD Station CRM

**Auth:** Token de integração da conta.

**Como gerar as credenciais:**

1. Acesse [crm.rdstation.com](https://crm.rdstation.com) → **Configurações** → **Integrações** → **Token de Acesso**
2. Copie o token

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/rd-station/scripts/connect.sh
```

**Capacidades:**

| Operação | Suporte |
|---|---|
| Listar deals/oportunidades | ✅ |
| Pipeline summary | ✅ |
| Projeção de pipeline | ✅ |
| Mover deal entre etapas | ✅ |
| Criar deal | ✅ |
| Marcar como ganho/perdido | ✅ |

**Doc oficial:** [developers.rdstation.com/reference/crm](https://developers.rdstation.com/reference/crm)

---

### PipeRun

**Auth:** Token de API (gerado nas configurações da conta).

**Como gerar as credenciais:**

1. Acesse sua conta PipeRun → **Configurações** → **API** → **Tokens**
2. Clique em **"Gerar novo token"**
3. Copie o token

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/piperun/scripts/connect.sh
```

**Capacidades:**

| Operação | Suporte |
|---|---|
| Listar deals | ✅ |
| Pipeline summary | ✅ |
| Projeção de pipeline | ✅ |
| Mover deal | ✅ |
| Criar/atualizar deal | ✅ |
| Marcar como ganho/perdido | ✅ |

**Doc oficial:** [api.piperun.com](https://api.piperun.com)

---

### Pipedrive

**Auth:** API Token pessoal + subdomínio da empresa.

**Como gerar as credenciais:**

1. Faça login no Pipedrive
2. Clique no avatar → **Configurações Pessoais** → **API**
3. Copie a **Chave de API**
4. Anote o subdomínio da sua empresa (ex: `minhaempresa` de `minhaempresa.pipedrive.com`)

**Setup:**
```bash
bash ~/.openclaw/workspace/skills/pipedrive/scripts/connect.sh
```

O connect.sh pede o subdomínio e o token, testa a conexão e cacheia os stages do pipeline.

**Capacidades:**

| Operação | Suporte |
|---|---|
| Listar deals (open/won/lost) | ✅ |
| Pipeline summary por stage | ✅ |
| Projeção de pipeline 30/90 dias | ✅ |
| Mover deal para outro stage | ✅ (por ID numérico ou nome do stage) |
| Atualizar deal (valor, data) | ✅ |
| Criar deal | ✅ |
| Adicionar nota | ✅ |
| Marcar como ganho/perdido | ✅ |

**Limitações:** O token de API pessoal no Pipedrive tem acesso a todos os dados da conta — não há escopo granular como no HubSpot. Trate o token com cuidado.

**Doc oficial:** [developers.pipedrive.com](https://developers.pipedrive.com/docs/api/v1)

---

## Testando uma integração

Para testar qualquer skill individualmente:

```bash
# Testar ERP
python3 ~/.openclaw/workspace/skills/<erp>/scripts/<erp>_client.py get_balance

# Testar CRM
python3 ~/.openclaw/workspace/skills/<crm>/scripts/<crm>_client.py list_deals --status open --limit 5

# Diagnóstico completo da skill
bash ~/.openclaw/workspace/skills/<skill>/scripts/doctor.sh
```

---

## Adicionando uma nova integração

O monorepo tem um template em `skills/_template/`. Cada skill segue o padrão `BaseERPClient` ou `BaseCRMClient` de `skills/_lib/base.py`. Veja o código de qualquer skill existente como referência.
