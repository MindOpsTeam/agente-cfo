# Memory — Manual do Sistema de Memória de Marcos

Este arquivo documenta o sistema de memória. A memória real vive em
`~/.agente-cfo/memory/*.md` na VPS do cliente, mantida por Marcos em runtime.

---

## Onde a memória vive

```
~/.agente-cfo/memory/          ← chmod 700 (criado pelo setup.sh)
├── empresa.md                 ← fatos sobre a empresa
├── preferencias_dono.md       ← preferências e acordos com o dono
├── eventos.md                 ← linha do tempo de eventos importantes
├── decisoes.md                ← decisões registradas para continuidade
└── metricas_baseline.md       ← métricas históricas como referência
```

---

## O que vai em cada arquivo

### `empresa.md`
Fatos objetivos sobre a empresa. Atualizar quando um dado mudar.

- Nome e CNPJ (se disponível no Omie)
- Segmento / tipo de negócio
- Faturamento médio mensal (última leitura do Omie)
- Sazonalidade observada (ex: "pico em dezembro, vale em fevereiro")
- Top 3 clientes recorrentes por volume (sem dados pessoais além do nome)
- Top 3 fornecedores recorrentes
- Ciclo de caixa típico (prazo médio de recebimento vs. pagamento)

**Formato:** markdown simples, chave-valor ou bullet. Sem JSON.

### `preferencias_dono.md`
Preferências explícitas do dono sobre como Marcos deve se comportar.

- Horários de preferência ("não mande nada depois das 20h no WhatsApp")
- Formato preferido ("prefiro os números em tabela, não em bullets")
- Tópicos que não quer receber ("não precisa do resumo de inadimplência todo dia")
- Nome que prefere ser chamado
- Qualquer ajuste pedido explicitamente

Só registra quando o dono expressar explicitamente. Não infere.

### `eventos.md`
Linha do tempo de eventos relevantes. **Append-only** — nunca edita o que já está.

Formato de cada entrada:
```
YYYY-MM-DD: [descrição concisa do evento]
```

Exemplos:
```
2026-03-15: Dono pediu para pausar alertas durante viagem internacional (retorno: 22/03)
2026-04-01: Ciclo de inadimplência acima de 15% pela primeira vez — notificado
2026-04-18: Renegociação com Fornecedor X concluída pelo dono (prazo +30 dias)
```

### `decisoes.md`
Decisões que o dono tomou e que Marcos precisa lembrar para não repetir análises já feitas.

Formato:
```
YYYY-MM-DD — [contexto curto]
Decisão: [o que foi decidido]
Resultado conhecido: [se já há outcome, registrar]
```

### `metricas_baseline.md`
Métricas históricas para comparação contextual. Atualizar mensalmente.

- Saldo médio do mês (últimos 3 meses)
- Ticket médio dos recebimentos
- Prazo médio de recebimento (dias)
- Prazo médio de pagamento (dias)
- Percentual médio de inadimplência
- Custo fixo médio mensal

---

## Como Marcos usa a memória

### Lendo
No início de cada cron (alerta_manha, alerta_tarde), ler:
1. `empresa.md` — para contextualizar os dados do Omie
2. `preferencias_dono.md` — para ajustar formato e conteúdo
3. `metricas_baseline.md` — para comparar com o dia atual

### Escrevendo
Ao final de cada cron, avaliar se há algo novo a registrar:
- Novo fato sobre a empresa → atualizar `empresa.md`
- Novo evento relevante → append em `eventos.md`
- Nova preferência expressa → atualizar `preferencias_dono.md`
- Decisão registrada → append em `decisoes.md`
- Fim do mês → atualizar `metricas_baseline.md`

**Só escreve se há algo novo.** Silêncio é correto quando não há.

### Decay
- Eventos com mais de 12 meses: tratar como "histórico", não base ativa para projeções.
- Métricas baseline: revisar se estão representando a realidade atual (sazonalidade muda).
- O dono pode `rm -rf ~/.agente-cfo/memory/` a qualquer momento. Marcos lida graciosamente:
  na próxima execução, reconstrói o que conseguir a partir do Omie e de zero.

---

## O que NÃO vai na memória

- Senhas, tokens, credenciais de qualquer tipo
- Conteúdo bruto de DRE ou relatórios (só referências: "DRE de abril disponível no Omie")
- Dados pessoais de clientes finais além do mínimo operacional
- Transcrições ou logs de conversas com o dono
- Qualquer dado que não tenha valor operacional para o próximo alerta

---

## Privacidade

- `chmod 700 ~/.agente-cfo/memory/` — só o usuário dono do processo pode ler
- Memória é **estritamente local** — nunca é enviada ao painel central (Supabase)
- O painel central recebe apenas: status de saúde, uso de LLM, eventos de sistema

---

## Setup

O `setup.sh` cria o diretório com as permissões corretas (idempotente):

```bash
mkdir -p ~/.agente-cfo/memory
chmod 700 ~/.agente-cfo/memory
```
