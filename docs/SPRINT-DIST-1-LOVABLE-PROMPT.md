# SPRINT DIST-1 — Lovable AI Prompts: Refinos de Onboarding

> **Uso:** Cole cada prompt diretamente no Lovable AI do projeto painel.
> Execute na ordem indicada. Cada refino é independente.

---

## Refino 1 — Auto-detect heartbeat no step "Cole na VPS"

**Arquivo alvo:** `src/routes/onboarding.tsx` (ou o componente do step de instalação)

**Prompt para Lovable:**

```
No step de onboarding onde o usuário cola o comando curl na VPS, adicione detecção
automática de conexão via polling do Supabase. Após o usuário colar o comando,
mostrar loader animado que verifica a cada 5 segundos se um heartbeat recente
chegou da instância.

Lógica de polling (adicionar como useEffect no componente do step):

```tsx
useEffect(() => {
  if (!showingCurlStep) return;
  const interval = setInterval(async () => {
    const { data } = await supabase
      .from("instances")
      .select("id, last_heartbeat")
      .order("last_heartbeat", { ascending: false, nullsFirst: false })
      .limit(1)
      .maybeSingle();
    const fresh =
      data?.last_heartbeat &&
      Date.now() - new Date(data.last_heartbeat).getTime() < 5 * 60 * 1000;
    if (fresh) {
      setVpsConnected(true);
      clearInterval(interval);
      toast.success("Marcos online! Avançando...");
      setTimeout(() => goToNextStep(), 2000);
    }
  }, 5000);
  return () => clearInterval(interval);
}, [showingCurlStep]);
```

Enquanto aguarda, mostrar:
- Loader animado (spinner ou dots animados, estilo loading do painel)
- Texto: "Aguardando Marcos se conectar à VPS..."
- Sub-texto em cinza: "Leva ~5min após você colar o comando"
- Botão secundário: "Já colei o comando →" que avança manualmente para o próximo step
- Se não conectar em 10 minutos (120 ticks × 5s), mostrar mensagem amarela:
  "Não conectou? [Ver guia de troubleshooting](docs/TROUBLESHOOTING.md)"

Estado necessário: `vpsConnected: boolean`, `showingCurlStep: boolean`
Função necessária: `goToNextStep()` (já deve existir no wizard)
```

---

## Refino 2 — Cards VPS provider com tutoriais detalhados inline

**Arquivo alvo:** `src/routes/onboarding.tsx` (step de escolha de VPS)

**Prompt para Lovable:**

```
No step de seleção de VPS provider, cada card (Hetzner, DigitalOcean, Hostinger)
deve abrir um accordion ou modal com tutorial passo-a-passo inline. Não apenas
um link externo — o usuário lê tudo sem sair da página.

Design: cards com ícone do provider, preço/mês e botão "Ver como criar". Ao clicar,
expande accordion com os passos abaixo. Ao final de cada tutorial, botão primário
"Vamos colar o comando lá agora →" que avança para o step do curl.

--- HETZNER (card 1) ---
Preço: "CX22 ~€4/mês"
Ícone: vermelho/laranja
Tutorial:
1. Acesse hetzner.com/cloud e crie uma conta
2. No console, clique em "Add Server"
3. Location: Helsinki ou Falkenstein (mais barato)
4. Image: Ubuntu 22.04
5. Type: CX22 (2 vCPU, 4 GB RAM — €4,35/mês)
6. SSH Key: cole sua chave pública OU marque "Root password" (Hetzner envia por email)
7. Clique em "Create & Buy Now"
8. Aguarde ~30s. Anote o IP exibido.
9. Acesse via terminal: `ssh root@<SEU_IP>`

--- DIGITALOCEAN (card 2) ---
Preço: "$12/mês"
Ícone: azul
Destaque: "(cupom $200 de trial disponível)"
Tutorial:
1. Acesse digitalocean.com — use código de referral para ganhar $200 de crédito
2. Create → Droplets
3. Image: Ubuntu 22.04 LTS x64
4. Plan: Basic — Regular Intel — $12/mês (2 GB RAM, 1 vCPU)
5. Datacenter region: New York ou São Paulo (menor latência para o Brasil)
6. Authentication: SSH Key (recomendado) ou Password
7. Clique em "Create Droplet"
8. Aguarde ~1min. Anote o IP exibido no painel.
9. Acesse: `ssh root@<SEU_IP>`

--- HOSTINGER (card 3) ---
Preço: "R$24/mês (anual)"
Ícone: roxo
Tutorial:
1. Acesse hostinger.com.br/vps
2. Escolha "VPS 1" (R$24/mês no plano anual, 4 GB RAM, 2 vCPU)
3. Em "Sistema operacional", selecione: Ubuntu 22.04 + clean install
4. Conclua o pagamento
5. O IP e a senha root chegam por email em ~5 minutos
6. Acesse via terminal: `ssh root@<SEU_IP>`
   (ou use o terminal web no painel da Hostinger)

Cada tutorial termina com botão verde grande: "Vamos colar o comando lá agora →"
```

---

## Refino 3 — Welcome final mais claro após Marcos online

**Arquivo alvo:** `src/routes/onboarding.tsx` (step final / success state)

**Prompt para Lovable:**

```
No último step do onboarding, após Marcos estar online (vpsConnected = true),
substituir o estado final genérico por uma tela de celebração clara e acionável.

Layout:
- Emoji grande: 🎉 ou confetti animado (se o painel já tiver animação de sucesso, use)
- Título grande: "Pronto! Marcos está online."
- Subtítulo: "Seu CFO virtual já está rodando na sua VPS. O que você quer fazer agora?"

3 botões grandes em grid (ou lista vertical em mobile), cada um com ícone:
┌─────────────────────────────────────┐
│  💬  Conversar com Marcos no painel │  → navega para /chat
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  📱  Conectar WhatsApp              │  → navega para /settings/whatsapp
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  🔌  Conectar mais integrações      │  → navega para /integrations
└─────────────────────────────────────┘

Abaixo dos botões, nota informativa em cinza claro:
"💡 Marcos vai te enviar a ronda matinal amanhã às 7h com os principais KPIs."

Não mostrar formulários nem inputs neste step — é puro CTA de próximo passo.
```

---

## Refino 4 — Steps opcionais com botão "Pular" mais visível

**Arquivo alvo:** `src/routes/onboarding.tsx` (steps de ERP, CRM, Cobrança, E-commerce)

**Prompt para Lovable:**

```
Nos steps opcionais do onboarding (ERP/CRM/Cobrança/E-commerce), tornar o botão
"Pular" (Skip) muito mais visível e adicionar tooltip explicativo.

Mudanças por step opcional:

1. Botão "Pular este step" deve ser SECUNDÁRIO (outline, não ghost/link):
   - Tamanho: mesmo height que o botão primário "Continuar"
   - Texto: "Pular por agora →"
   - Posicionado ao lado do botão Continuar (ou acima dele em mobile)

2. Ao passar o mouse (hover) no botão Pular, mostrar tooltip com 1 linha:
   - ERP step: "Você pode conectar depois em Configurações → Integrações"
   - CRM step: "CRM é opcional. Conecte depois se quiser análise de funil."
   - Cobrança step: "Asaas/Iugu opcionais. Conecte para conciliação de cobranças."
   - E-commerce step: "Shopify/ML opcionais. Conecte para análise de pedidos."

3. Adicionar texto pequeno abaixo do título do step:
   "Opcional — você pode configurar isso depois"
   (em cinza, font-size menor, itálico ou normal)

4. Manter o comportamento atual: pular avança para o próximo step sem salvar credenciais.

Não alterar a lógica dos steps obrigatórios (Anthropic key, Supabase URL, VPS).
```

---

## Notas para o PM

- Os refinos 1 e 3 dependem de `goToNextStep()` e estados de wizard já existentes no onboarding
- O refino 2 pode ser implementado com Radix UI Accordion (já no stack) ou Shadcn Dialog
- O refino 4 pode usar Radix UI Tooltip (já no stack)
- Aplicar na ordem: 4 → 2 → 1 → 3 (do menos ao mais impacto em estado)
