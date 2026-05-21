---
name: cfo-relatorios-executivos
description: >
  Geração de relatórios executivos estruturados: semanal (saldo+fluxo+anomalias+
  recomendações) e mensal (DRE+comparativo+inadimplência). Output em markdown
  formatado para painel, email ou fragmentado no WhatsApp.
category: CFO/Relatórios
metadata:
  { "openclaw": { "emoji": "📑", "requires": { "bins": ["python3"] } } }
---

# CFO — Relatórios Executivos

## Quando usar

| Situação | Comando |
|---|---|
| Relatório semanal (sexta 16h) | `python3 $SKILL_DIR/scripts/relatorio_semanal.py` |
| Relatório mensal (dia 1 do mês) | `python3 $SKILL_DIR/scripts/relatorio_mensal.py` |
| Sob demanda | Qualquer um com `--format markdown` |

## Estrutura Semanal

1. Snapshot financeiro (saldo + burn + runway)
2. Fluxo da semana (entradas vs saídas)
3. Anomalias detectadas
4. Top 3 inadimplentes
5. Recomendações priorizadas (máx 3, com ação concreta)

## Estrutura Mensal

1. Headline (uma frase: "Mês X foi Y — por causa de Z")
2. DRE simplificado
3. Comparativo mês anterior + YoY
4. Inadimplência (aging + top devedores)
5. Análise vertical de despesas
6. KPIs (runway, burn, working capital, DSO/DPO)
7. Top 3 recomendações para o próximo mês
