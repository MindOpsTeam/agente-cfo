# Roteiro do vídeo — Como instalar o Agente CFO (Marcos)

**Duração alvo:** 10–12 minutos
**Público:** dono de PME leigo em tecnologia
**Tom:** simpático, direto, sem jargão. "Cola e funciona."

---

## Antes de gravar — checklist (5 min)

- [ ] Tenha aberta a página final do painel já com Marcos online (pra mostrar o "resultado" antes do passo a passo) — abra em outra aba
- [ ] Tenha um **email novo** de teste pra criar a conta ao vivo (ex: `demo+video@gmail.com`)
- [ ] Tenha uma **conta Anthropic** já com US$5 carregados e a `sk-ant-...` em algum lugar fácil de copiar (NÃO mostre a key na tela — borre ou use placeholder)
- [ ] Crie **AGORA** uma VPS Hetzner CX22 vazia (Ubuntu 22.04) — vai usar ao vivo. Anote IP e senha root
- [ ] Tenha um **WhatsApp aberto no celular** ao lado pra escanear o QR
- [ ] OBS/ScreenStudio configurado: webcam canto inferior direito, narração limpa, mouse highlight ligado
- [ ] Aba do navegador com lovable.dev/projects/<ID>/install (a landing pública) já carregada
- [ ] Terminal limpo (zsh sem prompt poluído), font grande (16pt+)

---

## ESTRUTURA (com timing)

| Bloco | Duração | Conteúdo |
|---|---|---|
| 1. Hook | 0:00–0:45 | "Em 10 min você vai ter um CFO virtual no seu WhatsApp" + demo de 1 mensagem |
| 2. Pré-requisitos | 0:45–2:00 | Anthropic + VPS + WhatsApp |
| 3. Remix do painel | 2:00–3:30 | Lovable: 1 clique |
| 4. Onboarding (wizard) | 3:30–6:30 | Email, Anthropic key, VPS, comando curl |
| 5. Setup VPS ao vivo | 6:30–9:00 | curl|bash + QR WhatsApp |
| 6. Primeira conversa | 9:00–11:00 | "Marcos, gastei 50 com Uber" → SIM → confirmação |
| 7. Outro | 11:00–12:00 | "Você acabou de instalar um CFO. Link na descrição." |

---

## BLOCO 1 — Hook (0:00 → 0:45)

**Tela:** seu WhatsApp aberto, conversa com "Marcos"

**Fala:**
> "Oi. Em 10 minutos eu vou te mostrar como instalar um CFO virtual brasileiro
> que mora no seu WhatsApp. Olha só."

**Ação:** Digite no WhatsApp: `Quanto tenho em caixa?`

Aguarda Marcos responder (3–5s).

**Fala (sobreposto à resposta):**
> "Esse é o Marcos. Ele lê do seu ERP, responde em português, e ainda
> lança despesa, cobra inadimplente, faz relatório mensal sozinho.
> Custa uns 60 reais por mês de infra. Sem mensalidade nossa.
> Vamos instalar agora."

**Corta para:** logo + título do vídeo "INSTALAR O AGENTE CFO EM 10 MIN"

---

## BLOCO 2 — Pré-requisitos (0:45 → 2:00)

**Tela:** slide simples com 3 ícones (Anthropic / VPS / WhatsApp)

**Fala:**
> "Pra começar você precisa de 3 coisas. Anota aí."

**Mostra cada ícone:**

1. **Conta Anthropic com 5 dólares** *(mostra console.anthropic.com)*
   > "É quem faz o Marcos pensar. Cinco dólares dura mais de um mês."

2. **Uma VPS Ubuntu 22.04** *(mostra hetzner.com/cloud)*
   > "Eu uso a Hetzner CX22, custa uns 26 reais por mês. Hostinger e DigitalOcean
   > também funcionam. Specs mínimas: 1 vCPU e 2 GB de RAM."

3. **Um WhatsApp** *(mostra ícone)*
   > "Qualquer número que você queira usar pro Marcos. Pode ser o do seu negócio."

**Fala (corte rápido):**
> "Tudo isso na descrição do vídeo. Bora pro painel."

---

## BLOCO 3 — Remix do painel (2:00 → 3:30)

**Tela:** navegador na URL pública do projeto Lovable

**Fala:**
> "O painel é um template Lovable. Você 'remixa' — clica em um botão
> e ele cria uma cópia inteira só sua, com banco isolado, em 1 minuto.
> Seus dados nunca passam por mim, ficam só na sua conta Supabase."

**Ação:** Clique no botão **"Remix"** (canto superior direito)

**Fala (enquanto carrega):**
> "Olha — ele tá provisionando o banco, as 51 funções de backend,
> aplicando todas as migrações. Um minuto e tá pronto."

**Corte de tempo** (acelera 4x até terminar)

**Fala:**
> "Pronto. Esse aqui agora é o **meu** painel. Esse endereço lovable.app
> é único, só meu."

**Ação:** Copie a URL do painel próprio, abre em nova aba `/install`

---

## BLOCO 4 — Onboarding (3:30 → 6:30)

**Tela:** painel novo recém-criado

**Fala:**
> "Primeiro acesso eu caio na tela de login."

### 4.1 Login

**Ação:**
1. Digita email
2. Clica "Receber código"
3. Abre Gmail em outra aba, copia o código de 6 dígitos
4. Cola no painel

**Fala:**
> "Sem senha. Só email com código. Mais seguro e mais simples."

### 4.2 Wizard

**Tela:** wizard de onboarding (passo 1 de 7)

**Fala (caminhando pelos passos):**

**Passo 1 — Welcome:**
> "Welcome. Próximo."

**Passo 2 — Anthropic Key:**
**Ação:** cola a `sk-ant-...` (BORRA NA EDIÇÃO ou use uma key descartável)
> "Cola a chave da Anthropic. Ele valida na hora. Verde, próximo."

**Passo 3 — WhatsApp do dono:**
**Ação:** digita `+5511999999999`
> "Esse é o **seu** número — é onde o Marcos vai te chamar pra alertas.
> Não é o número do bot ainda, isso vem depois."

**Passo 4 — Escolha sua VPS:**
**Ação:** clica no card **Hetzner**
> "Eu já tenho minha Hetzner, então pulo. Se você ainda não tem,
> clica nesse botão que abre o site do provedor."

**Passo 5 — Comando curl** ⚠️ **PARTE MAIS IMPORTANTE**

**Tela:** painel mostra um bloco de código grande com `curl ... | bash`

**Fala:**
> "Esse é o único comando que você roda na vida. UM comando.
> Clica em 'Copiar'."

**Ação:** clica no botão 📋

---

## BLOCO 5 — Setup na VPS ao vivo (6:30 → 9:00)

**Tela:** alterna pro terminal já com SSH conectado na VPS

**Fala:**
> "Aqui é a minha VPS Hetzner, recém-criada, vazia. Tô logado como root.
> Cola o comando e Enter."

**Ação:** cola, dá Enter

**Acelera 8x** (o setup leva ~5 min real)

**Narra por cima do timelapse:**
> "Enquanto roda, ele instala o OpenClaw — que é o cérebro do Marcos —,
> baixa 20 skills financeiras, sobe 9 daemons em background,
> registra 5 rotinas automáticas e configura o WhatsApp.
> Tudo automático, você não precisa fazer mais nada."

**Quando aparecer o QR no terminal:**

**Fala:**
> "OLHA O QR! Pega o celular, abre o WhatsApp, vai em Aparelhos Conectados,
> Conectar Dispositivo, e escaneia."

**Ação:** mostra o celular escaneando (corta pra cena do celular ~3s)

**Fala:**
> "Conectado. Volta pro painel."

### Volta pro painel

**Tela:** wizard mostra "✅ Marcos online! Avançando..."

**Fala:**
> "Olha aí — o painel detectou sozinho. Não precisei fazer nada.
> Pode pular o passo das integrações, dá pra conectar Omie, Bling,
> HubSpot, qualquer um depois pela tela de Integrações."

**Ação:** clica "Pular por enquanto" → finaliza wizard

---

## BLOCO 6 — Primeira conversa (9:00 → 11:00)

**Tela:** dashboard principal

**Fala:**
> "Esse é o dashboard. Tem saldo, contas a pagar, projeção 90 dias,
> inadimplentes. Tudo puxado dos seus sistemas reais."

**Ação:** abre o WhatsApp no celular (ou WhatsApp Web na tela)

**Fala:**
> "Mas o legal é falar com ele. Olha."

**Ação:** digita no WhatsApp: `Gastei 50 com Uber`

**Marcos responde com confirmação estruturada.**

**Fala:**
> "Viu? Ele entendeu, sugeriu categoria, pediu confirmação. Eu mando SIM."

**Ação:** envia `SIM`

**Marcos:** "✅ Lançado R$ 50,00 em Omie, categoria Transporte."

**Fala:**
> "Foi pro ERP de verdade. Sem eu abrir o Omie. Agora pergunta outra coisa."

**Ação:** digita `Como vamos esse mês?`

**Espera resposta com análise + 3 recomendações.**

**Fala:**
> "Isso é o CFO. Ele lê seus dados, sintetiza, recomenda ação concreta.
> 24 horas por dia. Sem você abrir planilha."

---

## BLOCO 7 — Outro (11:00 → 12:00)

**Tela:** retorno pro dashboard, navega rapidamente pelas telas
(/integrations, /alerts, /chat) — montagem rápida 1 frame por tela

**Fala (sobreposta à montagem):**
> "Tem ainda: 17 integrações, alertas customizados, chat web,
> conciliação automática toda madrugada, ronda matinal, relatório semanal.
> Tudo no template.
>
> Custo total: 26 da VPS + uns 30 da Anthropic. Sem mensalidade minha.
>
> Link do template na descrição. Se travar em algum ponto, tem o botão
> de '?' no canto superior direito que abre um issue direto no GitHub.
>
> Bom proveito. Tchau."

**Tela final:** card com URL do template + link do canal/contato + thumbnail

---

## Pontos críticos para NÃO ESQUECER

1. **NUNCA mostre a `sk-ant-...` na íntegra** — borra na edição ou usa key descartável
2. **NUNCA mostre senha root da VPS** — apaga essa parte na edição
3. **Mostre o QR do WhatsApp bem rápido** (3s max) — se alguém pausar e escanear, pareia o WhatsApp DELE no seu Marcos. Borre/pixele se ficar muito tempo
4. **Se o setup demorar mais que 5min**, corta o vídeo e fala "aqui acelerei 8x" — não fica parado
5. **Se algo der erro ao vivo**, NÃO PARE A GRAVAÇÃO — mostra que tem o botão "?" que abre issue direto. Vira parte do conteúdo.

---

## Texto pra descrição do vídeo (YouTube/LinkedIn)

```
Agente CFO — CFO virtual brasileiro no seu WhatsApp.

📥 Template Lovable (clica e remixa):
https://lovable.dev/projects/ddcd382f-f68a-478d-a2a5-811a860ba83c

⚡ Setup: 10 minutos
💰 Custo: ~R$ 60/mês de infra (sem mensalidade nossa)
🔓 Código aberto MIT
🇧🇷 100% português

Capítulos:
0:00 - O que é o Marcos
0:45 - 3 pré-requisitos
2:00 - Remix do painel Lovable
3:30 - Onboarding (criar conta + wizard)
6:30 - Setup na VPS (1 comando)
9:00 - Primeira conversa
11:00 - Outras features

🔗 Doc completa: docs/COMO-INSTALAR-E-USAR.md
🐛 Achou bug? Botão "?" no painel cria issue direto no GitHub.
```

---

## Pós-gravação — checklist

- [ ] Cortar pausas longas (corte seco quando começar a "uhmmm")
- [ ] Borrar TODA aparição da `sk-ant-...` e senha SSH
- [ ] Acelerar timelapses (setup VPS = 8x, remix Lovable = 4x)
- [ ] Legendas automáticas + revisão (pra acessibilidade)
- [ ] Thumbnail: print do WhatsApp + "INSTALEI EM 10 MIN" em letras grandes
- [ ] Subir em rascunho primeiro, testa link do template antes de publicar
