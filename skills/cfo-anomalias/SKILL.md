---
name: cfo-anomalias
description: >
  Detecção estatística de anomalias financeiras: z-score por categoria,
  variação de despesas fora do padrão histórico, concentração de clientes.
  Marcos usa para identificar proativamente o que está "fora do normal".
category: CFO/Anomalias
metadata:
  { "openclaw": { "emoji": "🔍", "requires": { "bins": ["python3"] } } }
---

# CFO — Detecção de Anomalias

## Quando usar

| Situação | Comando |
|---|---|
| Discovery proativo (sempre ao iniciar) | `python3 $SKILL_DIR/scripts/zscore.py` |
| "o que aumentou mais esse mês?" | `python3 $SKILL_DIR/scripts/anomalia_categoria.py` |
| "dependemos muito de um cliente?" | `python3 $SKILL_DIR/scripts/concentracao_cliente.py` |

## Thresholds

- **Z-score > 2.0**: anomalia (despesa 2 desvios padrão acima da média)
- **Z-score > 3.0**: anomalia crítica (acontece <1% das vezes)
- **Concentração > 30%** de um cliente: risco de concentração
- **Variação MoM > 20%** em categoria: investigar
