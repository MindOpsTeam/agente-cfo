---
name: cfo-analise-estrategica
description: >
  Análise financeira estratégica: DRE, margens (bruta/operacional/líquida),
  análise vertical/horizontal, KPIs financeiros (DSO, DPO, CCC, ROI, ROE, ROIC,
  working capital, ponto de equilíbrio). Marcos usa para formar juízo estratégico
  sobre a saúde financeira da empresa.
category: CFO/Análise
metadata:
  { "openclaw": { "emoji": "📈", "requires": { "bins": ["python3"] } } }
---

# CFO — Análise Estratégica

Playbooks e scripts para análise financeira profunda. Marcos usa estes scripts quando
precisa ir além do saldo — entender se a empresa está saudável, em que direção está indo
e o que precisa mudar.

## Quando usar

| O dono pergunta / situação | Comando |
|---|---|
| "como vamos?", "tá tudo ok?", "análise do mês" | `python3 $SKILL_DIR/scripts/kpis.py` |
| "qual nossa margem?", "estamos lucrando?" | `python3 $SKILL_DIR/scripts/margem.py` |
| "quero ver o DRE" | `python3 $SKILL_DIR/scripts/dre.py` |
| "quanto representa cada categoria?" | `python3 $SKILL_DIR/scripts/analise_vertical.py` |
| "melhoramos ou pioramos vs mês passado?" | `python3 $SKILL_DIR/scripts/analise_horizontal.py` |

## Onde `$SKILL_DIR`

```bash
SKILL_DIR="${HOME}/.openclaw/workspace/skills/cfo-analise-estrategica"
```

## Interpretação de KPIs para PME BR

| KPI | Cálculo | Sinal de alerta |
|-----|---------|-----------------|
| **DSO** (dias de recebimento) | (contas a receber / receita) × 30 | > 45 dias → risco |
| **DPO** (dias de pagamento) | (contas a pagar / compras) × 30 | < 30 dias → pode negociar prazo |
| **CCC** (ciclo caixa) | DSO - DPO | > 60 dias → aperto de capital de giro |
| **Working Capital** | ativo circulante - passivo circulante | < 0 → insolvência técnica |
| **Margem bruta** | (receita - CMV) / receita | < 30% → serviço/revenda em risco |
| **Margem líquida** | lucro líquido / receita | < 5% → empresa frágil |
| **Runway** | caixa / burn mensal | < 3 meses → emergência |
| **Burn mensal** | total saídas mês | Se crescendo → investigar |

## Contexto de uso

Marcos nunca apresenta KPI isolado. Sempre:
1. Calcula o valor atual
2. Compara com snapshot anterior (se disponível em memory/)
3. Emite juízo: "bom/preocupante/crítico porque..."
4. Propõe 1 ação concreta
