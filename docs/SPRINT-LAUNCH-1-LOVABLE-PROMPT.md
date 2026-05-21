# SPRINT-LAUNCH-1-LOVABLE-PROMPT.md

> Texto pronto para PM disparar via lovable_send_prompt.
> Ref: Sprint LAUNCH-1 — Health indicator + landing CTA + onboarding polish.

---

## Prompt 1: Health Indicator no Dashboard

```
Quero adicionar um card de status do agente Marcos no topo do dashboard principal
(arquivo src/routes/_authenticated/index.tsx).

### Comportamento

O card deve:
1. Buscar `instances.last_heartbeat` e `instances.status` do Supabase ao carregar
2. Auto-refresh a cada 30 segundos (usar setInterval)
3. Exibir estado do Marcos:
   - 🟢 ONLINE — "Marcos online · última atividade há Xs" (se last_heartbeat < 5 min atrás)
   - 🟡 ALERTA — "Marcos sem sinal há Xm" (se entre 5–15 min)
   - 🔴 OFFLINE — "Marcos offline há Xm — verificar VPS" (se > 15 min ou sem instância)
   - ⚪ SEM VPS — "VPS não configurada — siga o onboarding" (se sem instância)

### Layout

Card compacto no topo da página, antes dos outros widgets:

```tsx
<Card className="border-l-4" style={{borderLeftColor: statusColor}}>
  <CardContent className="flex items-center justify-between py-3 px-4">
    <div className="flex items-center gap-2">
      <div className={`h-3 w-3 rounded-full ${statusDotClass}`} />
      <span className="font-medium text-sm">Marcos</span>
      <span className="text-sm text-muted-foreground">{statusText}</span>
    </div>
    {isOffline && (
      <Button size="sm" variant="outline" asChild>
        <Link to="/settings">Verificar</Link>
      </Button>
    )}
    {!hasInstance && (
      <Button size="sm" asChild>
        <Link to="/onboarding">Configurar →</Link>
      </Button>
    )}
  </CardContent>
</Card>
```

### Dados

```typescript
// Query
const { data: instance } = await supabase
  .from("instances")
  .select("id, last_heartbeat, status, hostname")
  .limit(1)
  .maybeSingle();

// Calcular estado
const lastHb = instance?.last_heartbeat ? new Date(instance.last_heartbeat) : null;
const minutesAgo = lastHb ? Math.floor((Date.now() - lastHb.getTime()) / 60000) : null;
const isOnline = minutesAgo !== null && minutesAgo < 5;
const isAlert = minutesAgo !== null && minutesAgo >= 5 && minutesAgo < 15;
const isOffline = minutesAgo !== null && minutesAgo >= 15;
const hasInstance = !!instance;
```

### Auto-refresh

```typescript
useEffect(() => {
  const interval = setInterval(fetchStatus, 30_000);
  return () => clearInterval(interval);
}, []);
```

---

## Prompt 2: Landing page /install com CTA melhorado

Arquivo: `src/routes/install.tsx`

Adicionar seção "Como funciona" com 4 steps visuais antes do CTA principal:

```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-4 my-8">
  {[
    { step: "1", icon: "🔀", title: "Remix", desc: "Clique em Remixar — cria seu painel em 1 min" },
    { step: "2", icon: "⚙️", title: "Configure", desc: "ERP + WhatsApp + API key no wizard" },
    { step: "3", icon: "🖥️", title: "Instale na VPS", desc: "1 comando, ~5 minutos" },
    { step: "4", icon: "💬", title: "Converse", desc: "Marcos responde no WhatsApp" },
  ].map(s => (
    <Card key={s.step} className="text-center p-4">
      <div className="text-3xl mb-2">{s.icon}</div>
      <div className="text-xs text-muted-foreground font-medium mb-1">PASSO {s.step}</div>
      <div className="font-semibold text-sm mb-1">{s.title}</div>
      <div className="text-xs text-muted-foreground">{s.desc}</div>
    </Card>
  ))}
</div>
```

Também adicionar custo estimado abaixo do CTA principal:
```tsx
<p className="text-xs text-muted-foreground text-center mt-4">
  Custo estimado: ~R$60–110/mês (VPS + Anthropic API) · Lovable grátis · Open-source MIT
</p>
```

---

## Prompt 3: Onboarding — step de VPS provider (novo step entre Anthropic e ERP)

Arquivo: `src/routes/onboarding.tsx`

Após o step de Anthropic API key, adicionar step "Escolha sua VPS":

Mostrar 3 cards clicáveis com link externo:

```tsx
const VPS_OPTIONS = [
  { name: "Hetzner", desc: "Mais barata — €4,35/mês", price: "~R$26/mês", recommended: true, url: "https://hetzner.com/cloud", badge: "Recomendado" },
  { name: "DigitalOcean", desc: "Mais conhecida — $12/mês", price: "~R$65/mês", url: "https://digitalocean.com" },
  { name: "Hostinger", desc: "Opção BR — R$24/mês", price: "R$24/mês", url: "https://hostinger.com.br/vps" },
];
```

Cards com botão "Criar VPS →" que abre em nova aba. Step é informativo — usuário clica "Já tenho VPS" ou "Criei agora" para avançar.

Instrução no step:
> "Você precisa de uma VPS Ubuntu 22.04+ (1 vCPU / 1 GB RAM) onde o Marcos vai rodar. Crie agora em um dos provedores abaixo ou use uma VPS que já tenha."

---

## Como disparar

```javascript
// Via lovable_send_prompt (um por vez, na ordem):
lovable_send_prompt(prompt1)  // Health indicator
lovable_send_prompt(prompt2)  // Landing CTA
lovable_send_prompt(prompt3)  // Onboarding VPS step
```

## Contexto para PM

- `instances` já existe no schema com `last_heartbeat`
- O heartbeat é enviado a cada 5 min pelo daemon `heartbeat.sh` na VPS
- `src/routes/_authenticated/index.tsx` é o dashboard principal
- `src/routes/install.tsx` é a landing page pública (/install)
- `src/routes/onboarding.tsx` tem wizard de 902 linhas — adicionar step sem quebrar fluxo existente
```
