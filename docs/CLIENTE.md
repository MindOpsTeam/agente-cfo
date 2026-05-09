# Bem-vindo ao Agente CFO

**Marcos** é seu CFO virtual no WhatsApp. Todo dia às 7h ele te manda o resumo do caixa — saldo, quem vence hoje, quem está atrasado. Às 18h fecha o dia e projeta a semana. No meio do dia, você pergunta o que quiser: "qual meu saldo?", "lista as contas vencidas", "cobra fulano" — ele responde com dados reais do seu ERP, sem você abrir planilha nenhuma.

---

## Pré-requisitos

Você precisa de 3 coisas antes de começar:

- **VPS Linux Ubuntu 22.04+** — qualquer provedor (DigitalOcean, Hetzner, Hostinger). Custo: ~R$ 30–80/mês.
- **Conta Anthropic** — em [console.anthropic.com](https://console.anthropic.com). O Marcos usa o modelo Claude. Custo: ~R$ 30–80/mês dependendo do uso.
- **ERP ativo com API** — Omie, Bling, Tiny, Granatum, VHSYS, Nibo ou ContaAzul. O Omie é o mais comum entre os alunos.

---

## Como instalar

Sem terminal, sem linha de comando. O painel guia você:

1. **Acesse o painel** e clique em **"Começar agora"** — cria sua conta com e-mail.
2. **Siga o onboarding** — 8 etapas no browser: conecta o ERP, configura o WhatsApp, define o orçamento.
3. **Cole o comando** gerado pelo painel na sua VPS — ele instala tudo em ~5 minutos.

No passo 7 do onboarding você escaneia um QR code para conectar o número WhatsApp do Marcos. Use um chip dedicado — não o seu número pessoal.

---

## Como usar

Você não precisa fazer nada depois de instalar. O Marcos já está trabalhando.

**Todos os dias, automaticamente:**
- **07:00** — Resumo matinal no WhatsApp: saldo, contas a receber e a pagar hoje, inadimplência, projeção 30 dias.
- **18:00** — Fechamento do dia: o que entrou, o que saiu, projeção da semana.

**A qualquer hora, mande mensagem para o número do Marcos:**

```
"qual o meu saldo?"
"quem vence essa semana?"
"lista as contas vencidas"
"quanto tenho a pagar esse mês?"
"como foram as vendas essa semana?"   (se tiver e-commerce)
```

**Para cobrar um cliente atrasado:**

```
Você: "cobra a Acme da fatura de R$ 1.500"
Marcos: [lê a fatura no Asaas/Iugu, mostra o rascunho]
         "Confirme: ENVIAR COBRANÇA para Acme (+5511...)
          Fatura: #4882 — R$ 1.500 — vencida há 12 dias
          Mensagem: Olá João, aqui é o financeiro da [sua empresa]...
          Responda SIM pra enviar ou NÃO pra cancelar."
Você: "sim"
Marcos: [envia e confirma]
```

**Painel web** — acesse para ver histórico de alertas, uso de tokens e ajustar configurações de regras.

---

## O que ele NÃO faz

- **Nunca age sem você confirmar** — qualquer pagamento, cobrança ou alteração requer "SIM" explícito.
- **Nunca decide por você** — apresenta os números e as opções. A escolha é sempre sua.
- **Não acessa seu banco** — apenas lê e escreve no ERP conectado (Omie, Bling etc.).
- **Não tem suporte dedicado** — é um template open source. Veja abaixo o que fazer quando der problema.

---

## Onde ficam seus dados

**Tudo na sua infraestrutura.** A Viver de IA não tem acesso a nada.

| Dado | Onde fica |
|---|---|
| Credenciais do ERP/CRM | Na sua VPS (arquivo protegido, chmod 600) |
| Histórico de conversas | Na sua VPS |
| Eventos e alertas | No banco Supabase do seu projeto Lovable |
| Chave Anthropic | Na sua VPS |

---

## Quando der problema

**Passo 1 — Diagnóstico automático:**
```
Na sua VPS:
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/doctor.sh
```
Mostra `✅` ou `❌` para cada componente. Na maioria dos casos o problema aparece aqui.

**Passo 2 — Documentação técnica:**  
[TROUBLESHOOTING.md](TROUBLESHOOTING.md) — lista os 10 problemas mais comuns com solução passo a passo.

**Passo 3 — Comunidade:**  
[github.com/MindOpsTeam/agente-cfo/issues](https://github.com/MindOpsTeam/agente-cfo/issues) — abra uma issue com o output do `doctor.sh`. É open source — a comunidade ajuda.

---

## Como cancelar

1. Pare (ou destrua) a VPS.
2. Delete o projeto no Lovable.
3. Cancele a conta na Anthropic.

Pronto. Não há contrato, não há assinatura com a Viver de IA.
