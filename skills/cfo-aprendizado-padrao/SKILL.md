---
name: cfo-aprendizado-padrao
description: >
  Memória de padrões de categorização: aprende com cada write_event e sugere
  categorias automaticamente. Marcos chama antes de mostrar rascunho de write —
  se padrão claro (>=3 ocorrências), já preenche a categoria sem perguntar.
category: CFO/Aprendizado
metadata:
  { "openclaw": { "emoji": "🧠", "requires": { "bins": ["python3"] } } }
---

# CFO — Aprendizado de Padrões

## Quando usar

| Situação | Comando |
|---|---|
| Antes de propor rascunho de create_payable/receivable | `python3 $SKILL_DIR/scripts/sugerir_categoria.py --supplier "Uber"` |
| Após cada write_event executado | `python3 $SKILL_DIR/scripts/aprender.py --supplier "Uber" --category "Transporte"` |

## Como funciona

1. `aprender.py` registra cada par (supplier, category) em `memory/padroes-categorias.json`
2. `sugerir_categoria.py` retorna a categoria mais comum pra um supplier
3. Se confiança >= 3 ocorrências: Marcos usa sem perguntar; caso contrário, sugere como default

## Exemplo de fluxo

```
Dono: "gastei 80 com Uber"
Marcos: chama sugerir_categoria.py --supplier "Uber"
        → {"categoria": "Transporte", "confianca": 8, "auto": true}
Marcos: preenche categoria=Transporte sem perguntar
        rascunho: "Lançar R$80 pago para Uber, categoria Transporte, data hoje. Confirma?"
```
