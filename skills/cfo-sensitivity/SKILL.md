---
name: cfo-sensitivity
description: >
  Análise de sensibilidade: qual variável financeira tem mais impacto no
  resultado? Simula ±10% em cada variável e ranqueia por alavanca.
  Marcos usa para responder "onde devo focar minha energia pra mover o caixa?"
category: CFO/Planejamento
metadata:
  { "openclaw": { "emoji": "📐", "requires": { "bins": ["python3"] } } }
---

# CFO — Análise de Sensibilidade

## Quando usar

| Situação | Comando |
|---|---|
| "onde devo focar?" | `python3 $SKILL_DIR/scripts/analise.py --target caixa_final --horizonte 90` |
| "o que move mais o runway?" | `python3 $SKILL_DIR/scripts/analise.py --target runway_meses --horizonte 60` |

## Output

```
Variável          | +10%            | -10%           | Alavanca
receita           | +R$15k          | -R$15k         | Alta ⭐⭐⭐
inadimplencia     | +R$3k           | -R$3k          | Média ⭐⭐
despesas_fixas    | +R$1k           | -R$1k          | Baixa ⭐
```

## Interpretação de Marcos

Sempre citar a variável de maior alavanca e propor ação concreta:
"Sua maior alavanca é receita — cada +10% vale R$Xk em caixa final.
Focar no fechamento de 2 deals no CRM vale mais que cortar qualquer despesa."
