---
name: cfo-cenarios-nomeados
description: >
  Salva e compara cenários financeiros nomeados. O dono pode criar cenários
  ("crescimento_agressivo", "cautela") com parâmetros próprios e Marcos
  compara projeções lado-a-lado com tradeoffs explícitos.
category: CFO/Planejamento
metadata:
  { "openclaw": { "emoji": "🗂️", "requires": { "bins": ["python3"] } } }
---

# CFO — Cenários Nomeados

## Quando usar

| Situação | Comando |
|---|---|
| Criar cenário | `python3 $SKILL_DIR/scripts/criar_cenario.py --nome "crescimento" --params "receita_mensal_pct=+30;despesa_pct=+15"` |
| Listar cenários | `python3 $SKILL_DIR/scripts/listar_cenarios.py` |
| Comparar dois | `python3 $SKILL_DIR/scripts/comparar.py --a "crescimento" --b "cautela" --metrica caixa_final` |

## Parâmetros suportados

| Parâmetro | Descrição | Exemplo |
|-----------|-----------|---------|
| `receita_mensal_pct` | Variação % na receita | `+30` (crescimento 30%) |
| `despesa_pct` | Variação % nas despesas | `-10` (corte 10%) |
| `inadimplencia_pct` | % de inadimplência prevista | `8` |
| `cac` | Custo de aquisição de cliente (R$) | `200` |
| `novos_clientes_mes` | Novos clientes por mês | `5` |
| `receita_fixa_adicional` | Receita extra mensal fixa (R$) | `5000` |
| `despesa_extra` | Custo extra mensal (R$) | `2000` |
