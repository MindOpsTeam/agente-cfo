# Integrations Research — ERPs e CRMs PME Brasil
> Fase A — Research  
> Data: 2026-05-08  
> Autor: Marcos (Agente CFO)  
> Escopo: 7 ERPs + 5 CRMs alvo para expansão de integrações

---

## 1. Tabela Completa

> **Legenda de esforço:** XS <4h · S 1-2 dias · M 3-5 dias · L 1-2 sem · XL >2 sem  
> **ClawHub:** verificado via `openclaw skills search` — nenhuma skill BR-ERP encontrada além de `omie` já instalada.

### ERPs

| Campo | **Omie** ✅ | **Bling** | **ContaAzul** | **Tiny / Olist** | **VHSYS** | **Granatum** | **Nibo** |
|---|---|---|---|---|---|---|---|
| **Categoria** | ERP | ERP | ERP | ERP | ERP | Financeiro | Financeiro/Contábil |
| **Skill ClawHub?** | ✅ `omie` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **API tipo** | REST/JSON-RPC | REST + OAuth 2.0 | REST + OAuth 2.0 | REST (v2 token estático, v3 OAuth 2.0) | REST (dual token: access + secret) | REST (access_token na query string) | REST + OData (API key header) |
| **Auth complexity** | Trivial (APP_KEY + APP_SECRET no body) | Alto (OAuth 2.0 com refresh token, código de autorização) | Alto (OAuth 2.0 PKCE, redirect) | Médio-Alto (v2: token estático; v3: OAuth 2.0) | Trivial/Médio (par access-token + secret-access-token, estáticos) | Trivial (access_token na URL ou header, estático) | Trivial (ApiToken no header `X-API-Key`, estático) |
| **Doc oficial** | https://developer.omie.com.br/ | https://developer.bling.com.br/ | https://developers.contaazul.com/ | https://tiny.com.br/api-docs/api | https://developers.vhsys.com.br/ | https://static.granatum.com.br/financeiro/api/ | https://nibo.readme.io/reference/como-utilizar-a-api |
| **Endpoints CFO-relevantes** | `financas.pesquisarContasPagar`, `financas.pesquisarContasReceber`, `financas.consultarResumoFinanceiro` | `GET /contas-receber`, `GET /contas-pagar`, `GET /extrato/contas-correntes/{id}` | `GET /v1/payables`, `GET /v1/receivables`, `GET /v1/bank-statements` | `GET /contas.pagar.listar`, `GET /contas.receber.listar` (v2) | `GET /v2/contas-receber`, `GET /v2/contas-pagar`, `GET /v2/extrato` | `GET /v1/lancamentos` (valor negativo=despesa, positivo=receita), `GET /v1/contas` | `GET /empresas/v1/schedules/debit` (a pagar), `GET /empresas/v1/schedules/credit` (a receber), `GET /empresas/v1/bankAccounts` |
| **Rate limit** | ~3 req/s (não documentado, verificado empiricamente) | ~30 req/min documentado (OAuth app) | Não documentado publicamente | Não documentado | Não documentado | 100 req/min · 200 req/5min (documentado) | 500 registros/query (OData `$top`), limite geral não documentado |
| **Plano free?** | Sim (trial 30 dias; API em todos os planos pagos, a partir de ~R$79/mês) | Sim (API disponível em todos os planos, incluindo gratuito com funcionalidades limitadas) | Não (API requer plano pago; sem trial de API) | Sim (trial + API disponível em planos básicos) | Sim (trial; API em planos pagos a partir de R$89/mês) | Não claramente (API disponível só em plano Premium ~R$79/mês) | Não (API disponível apenas no plano Premium; plano básico sem acesso) |
| **Adoção PME BR** | **Alta** (líder declarado em PME, >100k empresas) | **Alta** (líder em e-commerce/varejo, centenas de milhares de usuários, destaque EXAME) | **Média** (forte em serviços e SaaS, ~50k empresas) | **Média** (forte em e-commerce/marketplace via Olist, ~80k usuários) | **Baixa-Média** (foco em varejo regional, forte no Sul) | **Baixa** (nicho financeiro, não ERP completo) | **Baixa-Média** (contador/contabilidade, ~20k empresas) |
| **Esforço adapter** | ✅ Pronto | **S** (OAuth 2.0 com refresh; endpoints bem documentados) | **M** (OAuth 2.0 PKCE; doc incompleta em partes financeiras) | **S** (v2 token estático funcional; v3 OAuth para futuro) | **S** (dual token estático; endpoints claros no llms.txt) | **XS** (token estático query string; API doc completa e clara) | **S** (ApiToken simples; OData requer lógica de $filter e paginação) |
| **Recomendação MVP** | ✅ Baseline | **Sim** — maior penetração PME e-commerce | **Talvez** — boa API mas OAuth complexo e custo de dev alto | **Sim** — Tiny v2 token estático, implementação rápida | **Talvez** — menor adoção, mas auth simples | **Sim** — financeiro puro, auth trivial, doc excelente | **Não** — nicho contábil, sem PME direta, plano free ausente |

---

### CRMs

| Campo | **RD Station CRM** | **PipeRun** | **Pipedrive** | **HubSpot (Free+Starter)** | **Agendor** |
|---|---|---|---|---|---|
| **Categoria** | CRM | CRM | CRM | CRM | CRM |
| **Skill ClawHub?** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **API tipo** | REST + Bearer token (API Key estático disponível; OAuth legado) | REST (token de usuário no header `token:`) | REST v1/v2 + OAuth 2.0 (ou API token estático) | REST v3 (CRMs API) + OAuth 2.0 ou Private App token | REST + Bearer token (JWT estático por conta) |
| **Auth complexity** | Médio (token estático de aplicativo privado disponível; OAuth para apps públicos) | Trivial (token de usuário estático, gerado no perfil) | Médio (API token estático disponível; OAuth 2.0 para marketplace) | Médio (Private App token estático para uso interno; OAuth para publicação) | Trivial (Bearer token estático gerado no painel) |
| **Doc oficial** | https://developers.rdstation.com/ | https://developers.pipe.run/ | https://developers.pipedrive.com/docs/api/v1 | https://developers.hubspot.com/docs/api/overview | https://api.agendor.com.br/docs/ |
| **Endpoints CFO-relevantes** | `GET /crm/v1/deals` (oportunidades), `GET /crm/v1/pipelines`, `GET /crm/v1/activities` | `GET /v1/deals` (negócios), `GET /v1/pipelines`, `GET /v1/companies` | `GET /deals`, `GET /deals/{id}/summary`, `GET /pipelines`, `GET /deals?status=open\|won\|lost` | `GET /crm/v3/objects/deals`, `GET /crm/v3/pipelines/deals`, `GET /crm/v3/objects/deals/search` | `GET /v3/deals` (oportunidades), `GET /v3/pipelines`, `GET /v3/deals?status=ongoing` |
| **Rate limit** | Não documentado publicamente para CRM (Marketing: 24 req/dia no Light) | Não documentado publicamente | 100 req/10s por token (documentado) | 100 req/10s por app (Free/Starter private); 250k req/dia por conta | Não documentado |
| **Plano free?** | Sim (plano básico com API disponível em planos pagos; sem confirmação de trial API) | Não (requer conta ativa paga) | Sim (trial 14 dias; API disponível em todos os planos) | Sim (**API disponível no plano gratuito** com limite de 250k req/dia) | Sim (trial disponível; API parece disponível em todos os planos segundo docs) |
| **Adoção PME BR** | **Alta** (líder CRM Brasil, referência em inbound BR) | **Média** (foco PME e agências BR, crescimento recente) | **Alta** (global, muito usado por PME tech/startup BR) | **Alta** (global, free tier muito acessível a PMEs) | **Média** (CRM nacional focado em força de vendas, ~5k empresas BR) |
| **Esforço adapter** | **S** (token estático disponível; endpoints bem documentados) | **XS** (token trivial; API v1.1 simples e bem documentada) | **S** (API token estático; doc excelente; SDK Python oficial) | **M** (doc excelente, SDK oficial Python; OAuth para apps, Private App token para uso interno) | **S** (Bearer token simples; doc OpenAPI; foco em deals e funil) |
| **Recomendação MVP** | **Sim** — líder BR, integração natural com base de clientes Viver de IA | **Sim** — token trivial, menor esforço, foco PME BR | **Talvez** — excelente API mas foco global; muitas PMEs BR já têm | **Sim** — free tier com API robusta; HubSpot + Omie é combo comum | **Não** — menor penetração, pouco diferencial frente a Pipedrive e RD |

---

## 2. Recomendação Top 5 ERPs + Top 3 CRMs para o MVP

### Top 5 ERPs (ordem de prioridade)

| # | ERP | Justificativa |
|---|-----|---------------|
| 1 | **Omie** ✅ | Já integrado. Líder declarado PME BR. Mantém. |
| 2 | **Bling** | Maior penetração em e-commerce/varejo (segmento ENORME da base Viver de IA). OAuth 2.0 é o único desafio — resolver com refresh token cacheado. |
| 3 | **Tiny / Olist** | API v2 com token estático → implementação XS. Forte em marketplace (Shopee, ML, Amazon). Segunda maior base PME e-commerce depois do Bling. |
| 4 | **Granatum** | Auth trivial (token na URL), doc clara, endpoints CFO perfeitos (lançamentos = contas pagar/receber unificados). Nicho financeiro puro = cliente ideal pro Marcos. |
| 5 | **VHSYS** | Auth dual-token estático → implementação simples. Forte no Sul/Sudeste varejo físico. Menos prioridade por menor adoção nacional. |

**Fora do MVP (Fase B ou C):**
- **ContaAzul**: OAuth PKCE complexo + doc financeira incompleta + sem free → postergar.  
- **Nibo**: público-alvo é contador, não o dono da PME diretamente. Útil se quisermos integrar via escritório contábil.

### Top 3 CRMs (ordem de prioridade)

| # | CRM | Justificativa |
|---|-----|---------------|
| 1 | **HubSpot Free** | API gratuita robusta + SDK Python oficial + maior base instalada global que PMEs BR também usam. Pipeline de vendas como dado de receita futura = ouro pro CFO. |
| 2 | **RD Station CRM** | Líder absoluto CRM Brasil, base Viver de IA com alta probabilidade de overlap. Token estático de app privado disponível — implementação S. |
| 3 | **PipeRun** | Token trivial (XS de implementação), foco 100% PME BR, crescimento acelerado. Menor esforço do portfólio CRM. |

**Fora do MVP:**
- **Pipedrive**: excelente API + SDK Python, mas público mais global. Prioridade B.
- **Agendor**: menor penetração, sem SDK oficial. Prioridade C.

---

## 3. Riscos Descobertos

### ⚠️ Risco 1 — Bling: OAuth 2.0 com redirect_uri (alto impacto)
A API v3 do Bling usa **OAuth 2.0 com authorization code flow** — o cliente precisa autorizar via browser com redirect. Para um agente em VPS headless, isso exige:
- Um endpoint HTTP temporário para receber o callback (ou redirect para `localhost`), OU
- Uma tela de setup interativa no painel web (Lovable) para capturar o `code` e trocar por `access_token + refresh_token`.
- O `refresh_token` expira e precisa ser renovado.

**Impacto:** setup mais complexo que Omie. Não é blocker mas exige uma etapa extra no `setup.sh` ou na interface do painel. **Sugestão:** o painel web faz o OAuth flow e salva os tokens criptografados na VPS via `push-command`.

### ⚠️ Risco 2 — Tiny v2 vs v3: endpoints financeiros ausentes na v3 pública
A API Tiny **v2** (token estático) tem endpoints de contas a pagar/receber bem documentados. A **v3** (2025, OAuth 2.0) ainda não documenta endpoints financeiros publicamente — foco atual está em pedidos/produtos/estoque. Para o CFO, v2 é a escolha segura agora, mas a Olist está migrando para v3. **Risco:** v2 pode ser descontinuada. Implementar v2 hoje + monitorar v3.

### ⚠️ Risco 3 — ContaAzul: API financeira incompleta na documentação pública
A doc ContaAzul cita "contas a pagar e receber" nas capacidades, mas os endpoints específicos não estão disponíveis publicamente sem login na plataforma de developers. Há evidência de existirem (`/v1/payables`, `/v1/receivables`) mas não foi possível confirmar campos, filtros e rate limits sem acesso. **Sugestão:** postergar para Fase B; um cliente ContaAzul pode nos dar acesso de teste.

### ⚠️ Risco 4 — Granatum: não é ERP, é financeiro puro
Granatum não tem estoque, NF-e, clientes/fornecedores robustos. Clientes que usam Granatum provavelmente usam outro sistema para vendas. O Marcos não teria dados de pedidos ou pipeline — só fluxo de caixa. **Isso é OK para o caso de uso CFO**, mas limita análises como "quais clientes estão inadimplentes" (precisa de dados de cliente do Omie/Bling/etc.).

### ⚠️ Risco 5 — HubSpot CRM Free: deals sem valor financeiro por padrão
No plano Free, os deals do HubSpot têm campo `amount` mas é opcional. PMEs que não treinaram o time para preencher `amount` em cada deal terão pipeline sem valor monetário — o CFO não consegue projetar receita futura. **Sugestão:** no prompt de análise, tratar `amount=null` como "pipeline sem valor estimado" e avisar o usuário.

### ⚠️ Risco 6 — Nibo: dois produtos distintos com APIs distintas
Nibo tem **Nibo Empresa** (financeiro da empresa, `nibo.readme.io/reference/como-utilizar-a-api`) e **Nibo Contador** (contabilidade, `nibo.readme.io/reference/acesso-e-token`) com autenticações e endpoints diferentes. Integrar os dois é esforço L. Integrar só "Nibo Empresa" (financeiro) é S, mas o público é pequeno.

### ℹ️ Risco 7 — Rate limits: maioria não documentada
Granatum é o único ERP BR com rate limit **explicitamente documentado** (100 req/min). Os demais — Bling, Tiny, VHSYS, ContaAzul, Nibo — não publicam limites. Omie é ~3 req/s empiricamente. Para os adapters, implementar **exponential backoff com jitter** em todos por padrão é obrigatório.

---

## 4. Bibliotecas Python/Go Existentes

| Ferramenta | Tipo | Status | Link | Nota |
|---|---|---|---|---|
| `omie-python` (skill atual) | Python client interno | ✅ ativo (nosso) | repo local | Base de referência para outros adapters |
| `bling-sdk-python` | Não oficial, Python | ⚠️ inativo (2022) | github.com/tatic-art/bling-sdk-python | Cobre Bling v2 (legado). v3 OAuth não suportado. |
| `bling-api` (JS/TS) | Não oficial, TypeScript | ✅ ativo (45 ⭐) | github.com/AlexandreBellas/bling-api | TypeScript, não Python. Útil como referência de endpoints. |
| `python-pipedrive` | Não oficial | ⚠️ semi-ativo | github.com/MarketingPipeline/python-pipedrive | Pipedrive v1, funcional mas não mantido ativamente. |
| `hubspot-api-client` | **SDK Oficial Python** | ✅ ativo (HubSpot mantém) | pip install hubspot-api-client | Melhor SDK do portfólio. Cobre CRM, deals, pipelines. |
| `pipedrive` (Python) | **SDK Oficial Python** | ✅ ativo | pip install pipedrive | SDK oficial Pipedrive, atualizado para v2. |
| `rdstation` (Python) | Não oficial | ⚠️ RD Marketing (não CRM) | pypi.org/project/rdstation | Cobre RD Marketing, não RD Station CRM. |
| `nibo-api-python` | Não encontrado | ❌ nenhum ativo | — | Precisamos criar do zero. |
| `granatum-python` | Não encontrado | ❌ nenhum ativo | — | Simples de criar dado que auth é trivial. |
| `contaazul-python` | Legado (2018) | ❌ abandonado | github.com (vários forks) | OAuth2 da época (não PKCE). Não reutilizável. |

**Resumo:** para 8 dos 12 alvos, precisaremos escrever o adapter do zero ou adaptar algo legado. Os dois com SDK oficial Python mantido são **HubSpot** e **Pipedrive** — motivo extra para priorizá-los.

---

## 5. Decisão de Arquitetura Sugerida

### Opções avaliadas

**Opção A — Shell + Python (como Omie hoje)**
- Adapter = script Python chamado via `bash $SCRIPT omie_client.py <operation>`
- Pros: consistente com o que existe, o agente LLM pode chamar direto via `Execute: python3 ...`
- Contras: sem tipagem, sem retry/backoff padronizado, cada adapter vira um arquivo .py solto

**Opção B — Pure Python adapter package com interface comum**
- Pasta `skills/agente-cfo/adapters/<erp>/` com `client.py` implementando uma `BaseERPAdapter` (ABC)
- Interface: `get_balance() → dict`, `get_payables(start, end) → list`, `get_receivables(start, end) → list`, `get_pipeline() → list` (CRM only)
- Pros: tipagem, reutilização, testabilidade, retry centralizado, fácil adicionar novo adapter
- Contras: requer refatorar omie-pull-wrapper.sh existente

**Opção C — gRPC sidecar**
- Processo Python separado que expõe gRPC para o agente OpenClaw
- Pros: linguagem agnóstica, performático
- Contras: overhead brutal para 12 adapters de uso esporádico (cron 2x/dia), complexidade desnecessária

### Recomendação: **Opção B — Pure Python com ABC**

```
skills/agente-cfo/
├── adapters/
│   ├── base.py              # BaseERPAdapter, BaseCRMAdapter (ABC)
│   ├── omie/client.py       # Refactored from omie-pull-wrapper.sh
│   ├── bling/client.py      # Fase B
│   ├── tiny/client.py       # Fase B
│   ├── granatum/client.py   # Fase B
│   ├── vhsys/client.py      # Fase B
│   ├── hubspot/client.py    # Fase B
│   ├── rdstation/client.py  # Fase B
│   └── piperun/client.py    # Fase B
├── erp_gateway.py           # Detecta ERP_PROVIDER do .env, instancia adapter correto
└── scripts/
    ├── cfo-reporter.sh      # Substitui omie-pull-wrapper.sh por python erp_gateway.py
    └── ...
```

**`erp_gateway.py`** é o único ponto de entrada:
```python
# python erp_gateway.py resumo_financeiro
# python erp_gateway.py contas_receber 1 50
# Lê ERP_PROVIDER do .env, instancia adapter, chama método normalizado
```

**Tradeoffs:**
- ✅ O agente LLM não precisa saber qual ERP é — os prompts ficam iguais
- ✅ `setup.sh` pergunta `ERP_PROVIDER=omie|bling|tiny|granatum|vhsys` → grava no `.env`
- ✅ Retry/backoff/rate-limit implementado uma vez na `BaseERPAdapter`
- ⚠️ OAuth 2.0 (Bling, ContaAzul, Tiny v3) requer storage de refresh_token → `~/.agente-cfo/tokens/<provider>.json` com 600 perm
- ⚠️ Refatorar `omie-pull-wrapper.sh` para chamar `erp_gateway.py` (1 sprint de Fase B)

**Base para `BaseERPAdapter`:**
```python
from abc import ABC, abstractmethod
from typing import Any

class BaseERPAdapter(ABC):
    @abstractmethod
    def get_balance(self) -> dict[str, Any]: ...
    
    @abstractmethod
    def get_payables(self, page: int = 1, per_page: int = 50) -> list[dict]: ...
    
    @abstractmethod
    def get_receivables(self, page: int = 1, per_page: int = 50) -> list[dict]: ...
    
    def _request(self, method, url, **kwargs):
        """Retry com exponential backoff + respeita rate limit."""
        ...

class BaseCRMAdapter(ABC):
    @abstractmethod
    def get_pipeline(self) -> list[dict]: ...
    
    @abstractmethod
    def get_open_deals(self) -> list[dict]: ...
```

---

## 6. Próximos Passos (Fase B)

Ordem de implementação sugerida baseada em esforço × impacto:

1. **`base.py`** — ABC + retry/backoff centralizado (XS, ~2h)
2. **Granatum adapter** — auth trivial, doc completa (XS, ~3h) 
3. **Tiny v2 adapter** — token estático, endpoints confirmados (S, ~1 dia)
4. **VHSYS adapter** — dual token, llms.txt bom (S, ~1 dia)
5. **Nibo adapter** — OData requer lógica de $filter (S, ~1 dia)
6. **Bling adapter** — OAuth 2.0 com refresh token (M, ~3 dias incluindo flow de autorização no painel)
7. **HubSpot adapter** — SDK oficial, deals + pipeline (S, ~1 dia)
8. **RD Station CRM adapter** — token estático (S, ~1 dia)
9. **PipeRun adapter** — token trivial (XS, ~3h)
10. **`erp_gateway.py`** + refactor de `cfo-reporter.sh` para usar gateway (M, ~2 dias)
11. **`setup.sh`**: adicionar pergunta `ERP_PROVIDER` + configuração do token por provider (S, ~1 dia)

**Total estimado Fase B:** ~3 semanas de trabalho (pode ser paralelizado).

---

*Research gerado automaticamente por Marcos (Agente CFO) com base em docs públicas consultadas em 2026-05-08.*
