# SPRINT INT-2 — Prompt Lovable AI (PM executa)

**Sprint:** INT-2 — 17 integrações validadas + OAuth refresh + saúde mensal  
**Data:** 2026-05-25  
**Backend:** concluído (dashboard_metrics, oauth_refresh, daemon, cron mensal)  
**Próximo passo:** PM dispara o prompt abaixo no Lovable AI

---

## Prompt único: Componente `IntegrationsHealthWidget`

```
Crie o componente `src/components/IntegrationsHealthWidget.tsx` e adicione-o
no Dashboard (`src/pages/Dashboard.tsx`), abaixo do componente `<ActivityFeed />`.

---

### Dados (query Supabase)

```typescript
const { data: integrations, error, refetch } = useQuery({
  queryKey: ['integrations-health'],
  queryFn: async () => {
    const { data, error } = await supabase
      .from('integration_credentials')
      .select('skill_name, active, last_test_status, last_test_at')
      .eq('active', true)
      .order('skill_name')
    if (error) throw error
    return data
  },
  refetchInterval: 60_000,  // auto-refresh a cada 60s
})
```

---

### Ícone por categoria de skill

Mapeamento pelo `skill_name`:

```typescript
const SKILL_ICONS: Record<string, string> = {
  // ERP
  omie: '🏢', bling: '🏢', contaazul: '🏢', tiny: '🏢',
  granatum: '🏢', vhsys: '🏢', nibo: '🏢',
  // Cobrança
  asaas: '💰', iugu: '💰',
  // CRM
  hubspot: '📊', 'rd-station': '📊', piperun: '📊',
  pipedrive: '📊', kommo: '📊',
  // E-commerce
  'mercado-livre': '🛒', nuvemshop: '🛒',
  // Infra
  supabase: '🔧',
}

const SKILL_NAMES: Record<string, string> = {
  omie: 'Omie', bling: 'Bling', contaazul: 'Conta Azul',
  tiny: 'Tiny', granatum: 'Granatum', vhsys: 'VhSys', nibo: 'Nibo',
  asaas: 'Asaas', iugu: 'Iugu',
  hubspot: 'HubSpot', 'rd-station': 'RD Station', piperun: 'Piperun',
  pipedrive: 'Pipedrive', kommo: 'Kommo',
  'mercado-livre': 'Mercado Livre', nuvemshop: 'Nuvemshop',
  supabase: 'Supabase',
}
```

---

### Badge de status

Baseado em `last_test_status`:
- `'ok'` → Badge verde ✅ "OK"
- `'invalid'` → Badge vermelho ❌ "Credencial inválida"
- `'unreachable'` → Badge amarelo ⚠️ "Inacessível"
- `'unknown'` → Badge cinza ❓ "Desconhecido"
- `null` ou ausente → Badge cinza ⏳ "Nunca testado"

Use o componente `Badge` do shadcn/ui com variantes:
- ok → `variant="default"` (ou cor verde com className)
- invalid → `variant="destructive"`
- unreachable → className amarelo
- null/unknown → `variant="secondary"`

---

### Timestamp relativo

Para `last_test_at` (ISO string):
```typescript
function timeAgo(isoStr: string | null): string {
  if (!isoStr) return '—'
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'Agora'
  if (mins < 60) return `Há ${mins} min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `Há ${hrs}h`
  const days = Math.floor(hrs / 24)
  return `Há ${days} dia${days > 1 ? 's' : ''}`
}
```

---

### Botão "Testar agora"

Ao clicar no botão de teste de uma integração específica:
1. Exibe spinner (estado local por skill_name)
2. Chama:
```typescript
const { data } = await supabase.functions.invoke('integration-credentials-test', {
  body: { skill_name: integration.skill_name }
})
```
3. Após conclusão: chama `refetch()` para atualizar a lista
4. Toast de resultado: "✅ skill OK" ou "❌ skill: erro"

---

### Layout visual

```
┌─────────────────────────────────────────────┐
│ 🔌 Saúde das Integrações        [Testar tudo]│
├─────────────────────────────────────────────┤
│ 🏢 Omie          ✅ OK       Há 2h      [▶] │
│ 🏢 Bling         ⏳ Nunca    —           [▶] │
│ 💰 Asaas         ✅ OK       Há 3 dias   [▶] │
│ 📊 HubSpot       ❌ Inválido  Há 5 dias   [▶] │
│ 🛒 Mercado Livre  ✅ OK       Há 1h       [▶] │
└─────────────────────────────────────────────┘
```

- Card `Card + CardHeader + CardContent` do shadcn/ui
- Cada linha: `flex items-center justify-between gap-2`
- Nome + ícone à esquerda, badge + tempo + botão à direita
- Botão [▶] é `Button variant="ghost" size="sm"` com ícone Play ou RefreshCw do lucide-react

---

### Botão "Testar tudo"

Botão no header do card (secundário, pequeno) que dispara o teste para todas as integrações ativas em série.
Mostra spinner global enquanto roda. Após conclusão: refetch e toast "Todas as integrações testadas."

---

### Loading skeleton

Enquanto `isLoading` (primeira carga):
```typescript
<div className="space-y-2">
  {Array.from({length: 4}).map((_, i) => (
    <Skeleton key={i} className="h-10 w-full" />
  ))}
</div>
```

---

### Estados vazios e de erro

- `integrations?.length === 0`: 
  ```
  <p className="text-muted-foreground text-sm text-center py-4">
    Nenhuma integração ativa configurada.
  </p>
  ```
- `error !== null`:
  ```
  <p className="text-destructive text-sm">
    Não foi possível carregar as integrações.
  </p>
  ```

---

### Posição no Dashboard

Em `src/pages/Dashboard.tsx`, localizar o componente `<ActivityFeed />` e adicionar imediatamente abaixo:
```typescript
<IntegrationsHealthWidget />
```

**NÃO** remover, mover ou modificar nenhum outro componente existente no Dashboard.

---

### Restrições

- Usar apenas shadcn/ui (Card, Badge, Button, Skeleton, Toast) já instalados
- Usar o hook `useSupabase` / cliente Supabase já existente no projeto
- Tailwind CSS para estilo — sem CSS custom
- TypeScript estrito — sem `any`
- Não criar novas Edge Functions — usar apenas `integration-credentials-test` já existente
- Não alterar tabelas — `integration_credentials` já tem os campos `last_test_status` e `last_test_at`
- Componente deve ser self-contained (sem props obrigatórias)
```

---

## Checklist pós-deploy (PM valida)

- [ ] `IntegrationsHealthWidget.tsx` criado em `src/components/`
- [ ] Componente visível no Dashboard abaixo do ActivityFeed
- [ ] Lista skills com badge de status correto
- [ ] Botão "Testar" dispara `integration-credentials-test` e atualiza status
- [ ] Auto-refresh a cada 60s funcionando
- [ ] Loading skeleton exibido na primeira carga
- [ ] Funciona com lista vazia (nenhuma integração ativa)
- [ ] Pipeline existente intacto (ActivityFeed, cfo-write-events, etc.)
