# SPRINT SYNC-1 — Lovable AI Prompt: Feed de Atividade

> **Uso:** Cole este prompt diretamente no Lovable AI do projeto painel.
> Aplica refatoração completa do widget de write events para "Feed de Atividade"
> com tabs por origem, visibilidade no topo do dashboard e empty state claro.

---

## Prompt único (aplicar de uma vez)

```
Refatorar o widget CfoWriteEventsWidget existente (ou criar ActivityFeedWidget
se não existir) e promovê-lo ao topo do dashboard. Mudanças completas abaixo.

─────────────────────────────────────────────────────────────────────────────
1. RENOMEAR E MOVER
─────────────────────────────────────────────────────────────────────────────

- Renomear componente: CfoWriteEventsWidget → ActivityFeedWidget
- Mover para o TOPO do dashboard (acima dos cards de KPI — primeira seção visível)
- Remover do meio do dashboard onde está atualmente

─────────────────────────────────────────────────────────────────────────────
2. HEADER DESTACADO
─────────────────────────────────────────────────────────────────────────────

Substituir o header atual por:

```tsx
<div className="flex items-center justify-between mb-3">
  <div>
    <h2 className="text-lg font-semibold flex items-center gap-2">
      🔄 Atividade recente
    </h2>
    <p className="text-sm text-muted-foreground">
      Lançamentos feitos via chat, sync com ERP e ações manuais
    </p>
  </div>
  <Button variant="ghost" size="sm" onClick={() => refetch()} title="Atualizar">
    <RefreshCw className="h-4 w-4" />
  </Button>
</div>
```

─────────────────────────────────────────────────────────────────────────────
3. TABS FILTRO POR ORIGEM
─────────────────────────────────────────────────────────────────────────────

Adicionar tabs acima da lista de eventos:

```tsx
const ORIGIN_TABS = [
  { value: "all",            label: "Tudo" },
  { value: "chat",           label: "💬 Chat",         icon: "💬" },
  { value: "erp_sync",       label: "🔄 ERP Sync",     icon: "🔄" },
  { value: "manual",         label: "✋ Manual",        icon: "✋" },
  { value: "reconciliation", label: "⚖️ Conciliação",  icon: "⚖️" },
  { value: "system",         label: "⚙️ Sistema",      icon: "⚙️" },
];

const [activeTab, setActiveTab] = useState("all");
```

Filtrar a query/dados pelo tab ativo:
- Tab "Tudo": sem filtro
- Demais tabs: `.filter(e => e.origin === activeTab)` (ou `.eq("origin", activeTab)` na query Supabase)

─────────────────────────────────────────────────────────────────────────────
4. QUERY SUPABASE ATUALIZADA
─────────────────────────────────────────────────────────────────────────────

Substituir a query atual por:

```typescript
const fetchEvents = async (origin?: string) => {
  let query = supabase
    .from("cfo_write_events")
    .select("id, channel, action, erp, erp_record_id, amount, supplier, status, origin, created_at, raw_text")
    .order("created_at", { ascending: false })
    .limit(20);

  if (origin && origin !== "all") {
    query = query.eq("origin", origin);
  }

  const { data, error } = await query;
  return { data, error };
};
```

Chamar novamente quando `activeTab` mudar:
```typescript
useEffect(() => {
  fetchEvents(activeTab === "all" ? undefined : activeTab).then(({ data }) => {
    if (data) setEvents(data);
  });
}, [activeTab]);
```

─────────────────────────────────────────────────────────────────────────────
5. ÍCONE DE ORIGEM EM CADA ITEM
─────────────────────────────────────────────────────────────────────────────

Adicionar ícone de origem ao lado de cada evento na lista:

```typescript
const ORIGIN_ICONS: Record<string, string> = {
  chat:           "💬",
  erp_sync:       "🔄",
  manual:         "✋",
  reconciliation: "⚖️",
  system:         "⚙️",
};

// No JSX de cada evento:
<span title={`Origem: ${event.origin || "chat"}`}>
  {ORIGIN_ICONS[event.origin ?? "chat"] ?? "💬"}
</span>
```

Badge colorido para origem (opcional, mas recomendado):
- chat:           badge azul claro
- erp_sync:       badge verde (sync automático)
- manual:         badge amarelo
- reconciliation: badge roxo
- system:         badge cinza

─────────────────────────────────────────────────────────────────────────────
6. EMPTY STATE MAIS CONVIDATIVO
─────────────────────────────────────────────────────────────────────────────

Substituir o empty state genérico por:

```tsx
{events.length === 0 && (
  <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
    <span className="text-5xl">📋</span>
    <p className="text-base font-medium text-foreground">
      Nenhuma atividade ainda
    </p>
    <p className="text-sm text-muted-foreground max-w-xs">
      Quando você mandar "gastei X com Y" no WhatsApp, ou houver um
      lançamento novo no Omie, ele aparece aqui automaticamente.
    </p>
    <a
      href="/docs/como-funciona"
      className="text-sm text-primary underline underline-offset-2"
    >
      Como funciona →
    </a>
  </div>
)}
```

Empty state específico por tab (quando tab selecionada mas sem items):
- chat:           "Nenhuma mensagem processada ainda. Mande 'saldo' no WhatsApp para começar."
- erp_sync:       "Nenhum lançamento sincronizado ainda. O sync automático roda a cada 5 minutos."
- manual:         "Nenhum lançamento manual registrado."
- reconciliation: "Nenhuma divergência conciliada ainda."
- system:         "Nenhuma ação do sistema registrada."

─────────────────────────────────────────────────────────────────────────────
7. LAYOUT E PAGINAÇÃO
─────────────────────────────────────────────────────────────────────────────

- Mostrar até 20 eventos visíveis diretamente (sem truncar em 5)
- Adicionar botão "Ver todos →" no footer do widget que navega para /activity
  (ou expande o widget se não houver rota dedicada)
- Realtime Supabase subscription mantida (já deve existir — não remover)
- Botão Refresh manual (implementado no header, item 2)

─────────────────────────────────────────────────────────────────────────────
8. RESPONSIVIDADE
─────────────────────────────────────────────────────────────────────────────

- Em mobile (< md): tabs ficam em scroll horizontal (overflow-x: auto)
- Ícone de origem + valor + fornecedor na mesma linha condensada
- Status badge menor em mobile

─────────────────────────────────────────────────────────────────────────────
RESUMO DAS MUDANÇAS
─────────────────────────────────────────────────────────────────────────────

Arquivos afetados:
- src/components/dashboard/ActivityFeedWidget.tsx (renomear/refatorar)
- src/routes/index.tsx (mover widget para topo, linha ~437)

Não alterar:
- Lógica de realtime subscription existente
- Tabela cfo_write_events (já tem coluna `origin` — apenas usá-la)
- Outros widgets do dashboard
```

---

## Contexto técnico para o PM

- Coluna `origin` já existe em `cfo_write_events` (migration aplicada: `ALTER TABLE cfo_write_events ADD COLUMN origin text NOT NULL DEFAULT 'chat' CHECK (origin IN ('chat', 'erp_sync', 'manual', 'reconciliation', 'system'))`)
- Entries existentes já têm `origin='chat'` (backfill feito)
- Daemon `erp_sync.py` insere com `origin='erp_sync'` automaticamente a cada 5min
- Index criado: `idx_cfo_write_events_origin ON cfo_write_events(origin, created_at DESC)`
