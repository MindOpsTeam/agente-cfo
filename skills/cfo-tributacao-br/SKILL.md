---
name: cfo-tributacao-br
description: >
  Conhecimento fiscal brasileiro: regimes tributários (Simples Nacional, Lucro
  Presumido, Lucro Real), alíquotas, datas críticas (DAS, DARF, IRPJ, GPS/INSS,
  FGTS), calendário fiscal e sugestão de regime. Marcos usa para contextualizar
  obrigações fiscais e antecipar vencimentos críticos.
category: CFO/Tributação
metadata:
  { "openclaw": { "emoji": "🧾", "requires": { "bins": ["python3"] } } }
---

# CFO — Tributação BR

> ⚠️ **Aviso legal:** este módulo é referência educativa para o CFO virtual orientar
> o dono sobre o contexto fiscal. **Não substitui contador ou advogado tributarista.**
> Marcos cita estes dados para dar contexto, nunca para dar parecer fiscal oficial.

## Regimes Tributários

### Simples Nacional (SN)
- Faturamento até **R$ 4,8 milhões/ano**
- DAS unificado mensal (IRPJ + CSLL + PIS + COFINS + CPP + ISS/IPI/ICMS)
- Alíquotas: 4% a 22,9% dependendo do anexo e faixa
- Vencimento DAS: **dia 20** do mês seguinte

### Lucro Presumido (LP)
- Faturamento até **R$ 78 milhões/ano**
- IRPJ: 15% sobre 8% (comércio) ou 32% (serviços) da receita = 1,2% a 4,8%
- CSLL: 9% sobre 12% (comércio) ou 32% (serviços) = 1,08% a 2,88%
- PIS: 0,65% | COFINS: 3% (regime cumulativo)
- DARF trimestral: **último dia útil** de jan/abr/jul/out

### Lucro Real (LR)
- Obrigatório acima de R$ 78 milhões, bancos e holdings
- IRPJ: 15% + adicional 10% sobre lucro > R$20.000/mês
- CSLL: 9%
- PIS: 1,65% | COFINS: 7,6% (não-cumulativo — mas gera créditos)
- Apuração trimestral ou anual com antecipações mensais

## Calendário Fiscal Recorrente

| Obrigação | Regime | Vencimento |
|-----------|--------|-----------|
| DAS (Simples) | SN | Dia 20 mês seguinte |
| DARF IRPJ/CSLL | LP/LR | Trimestral — jan/abr/jul/out |
| PIS/COFINS | LP/LR | Dia 25 mês seguinte |
| IRRF s/ salários | Todos | Dia 20 mês seguinte |
| GPS (INSS empresa) | Todos | Dia 20 mês seguinte |
| FGTS | Todos | Dia 7 mês seguinte |
| ICMS | SN/LP | Varia por estado (ver tabela) |
| ISS | SN/LP | Varia por município (geralmente dia 10-15) |
| 13º parcela 1ª | Todos | Até 30/novembro |
| 13º parcela 2ª | Todos | Até 20/dezembro |
| INSS 13º | Todos | Junto com 2ª parcela |

## Datas especiais brasileiras (planejamento CFO)

| Data | Impacto financeiro |
|------|-------------------|
| Janeiro | Férias coletivas, IPTU/IPVA em muitos estados |
| Fevereiro | Carnaval — queda de faturamento em varejo |
| Março | IRPJ 1º trimestre vence |
| Junho | IRPJ 2º trimestre |
| Setembro | IRPJ 3º trimestre |
| Novembro | 1ª parcela 13º |
| Dezembro | 2ª parcela 13º + férias + pró-labore extra |

## Quando usar `scripts/calendario_fiscal.py`

Marcos chama quando dono pergunta "que imposto vence essa semana/mês?" ou
quando detecta baixa de caixa que pode coincidir com obrigação fiscal próxima.

## Quando usar `scripts/sugerir_regime.py`

Apenas para **ilustrar** a diferença de carga tributária entre regimes — não
para recomendar mudança formal (isso é decisão contábil/jurídica).
