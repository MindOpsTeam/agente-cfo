# Holdprint (Holdworks) — ERP de gráfica/impressão

Integração do Agente CFO com a API REST do **Holdprint** (https://docs.holdworks.ai).
Leitura de contas a pagar/receber, clientes, fornecedores, orçamentos e jobs de produção.

## Conexão

- **Base URL:** `https://api.holdworks.ai`
- **Auth:** header `x-api-key: <token>` — token pessoal em **Holdprint → Ajustes → API → Copiar**.
- **Rate limit:** 100 requisições/min por API Key.
- **Sandbox:** ❌ não existe. Testar exige uma API Key real.

Configurar: `bash scripts/connect.sh` (lê `HOLDPRINT_API_KEY` do ambiente/painel ou pergunta).
Diagnóstico: `bash scripts/doctor.sh`.

## Endpoints mapeados

| Recurso | Endpoint | Uso |
|---|---|---|
| Contas a Pagar | `GET /api-key/expenses/data` | `list_payables` |
| Contas a Receber | `GET /api-key/incomes/data` | `list_receivables` |
| Clientes | `GET /api-key/customers/data` | `list_customers` |
| Fornecedores | `GET /api-key/suppliers/data` | `list_suppliers` |
| Orçamentos | `GET /api-key/budgets/data` | `list_budgets` |
| Jobs (produção) | `GET /api-key/jobs/data` | `list_jobs` |

Filtros comuns: `page`, `limit` (máx 100), `start_date`, `end_date` (YYYY-MM-DD), `status`.
> ⚠️ Sem datas, a API retorna só o **mês corrente** — o client passa uma janela ampla
> (-365d a +365d) por padrão para vencidos e projeção funcionarem.

## Tools MCP

`holdprint_saldo`, `holdprint_contas_pagar`, `holdprint_contas_receber`, `holdprint_vencidos`,
`holdprint_projecao_caixa`, `holdprint_dashboard`, `holdprint_clientes`, `holdprint_fornecedores`,
`holdprint_orcamentos`, `holdprint_jobs`.

## Limitações

- **Saldo bancário:** o Holdprint não expõe endpoint de saldo → `get_balance` retorna `0`
  (a projeção de caixa funciona como fluxo líquido entradas − saídas).
- **Somente leitura nos financeiros:** a doc pública não traz POST/PUT para despesas/receitas,
  então `pay_payable`/`create_payable`/etc. retornam `not_supported`.

## CLI (debug)

```bash
python3 scripts/holdprint_client.py get_balance
python3 scripts/holdprint_client.py list_payables --from 2025-01-01 --to 2025-12-31 --status pending
python3 scripts/holdprint_client.py list_receivables --limit 100
python3 scripts/holdprint_client.py list_overdue
python3 scripts/dashboard_metrics.py
```
