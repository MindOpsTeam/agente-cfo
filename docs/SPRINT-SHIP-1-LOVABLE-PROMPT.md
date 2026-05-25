# SPRINT SHIP-1 — Prompt Lovable AI (PM executa)

**Sprint:** SHIP-1 — Launch público: botão "?" + modal report-issue  
**Data:** 2026-05-25  
**Backend:** edge fn `report-issue` já deployada  
**Pré-requisito:** Adicionar secret `GITHUB_REPORT_ISSUE_TOKEN` no Supabase (PAT com escopo `issues`)

---

## Prompt único: Botão "?" global + Modal Report-Issue

```
Adicione um botão de feedback/report no header global da aplicação.

---

### 1. Botão "?" no Header

No componente de header global (provavelmente `src/components/layout/Header.tsx` ou similar),
adicione um botão com ícone de interrogação à direita do header, antes do avatar do usuário:

```typescript
import { HelpCircle } from 'lucide-react'

// Dentro do header, antes do avatar/menu do usuário:
<Button
  variant="ghost"
  size="icon"
  onClick={() => setReportOpen(true)}
  title="Reportar problema ou enviar feedback"
  className="text-muted-foreground hover:text-foreground"
>
  <HelpCircle className="h-5 w-5" />
</Button>
```

Estado: `const [reportOpen, setReportOpen] = useState(false)` no componente do header.

---

### 2. Modal ReportIssueModal

Crie o componente `src/components/ReportIssueModal.tsx`:

```typescript
interface ReportIssueModalProps {
  open: boolean
  onClose: () => void
}
```

**Campos do formulário:**
- `subject`: Input obrigatório, placeholder "Descreva o problema em poucas palavras..."
- `description`: Textarea obrigatório, 4 linhas, placeholder "Explique o que aconteceu, o que esperava e o que viu..."
- `include_telemetry`: Checkbox com label "Incluir informações técnicas (heartbeat, último erro) — ajuda a diagnosticar mais rápido"
- Botão "Cancelar" (ghost) e "Enviar Report" (primary)

**Submit:**
```typescript
const handleSubmit = async () => {
  setLoading(true)
  try {
    const { data, error } = await supabase.functions.invoke('report-issue', {
      body: { subject, description, include_telemetry: includeTelemetry }
    })
    if (error) throw error
    toast.success(`Issue criado! ${data.issue_url}`)
    // Abre link do issue em nova aba
    window.open(data.issue_url, '_blank', 'noopener,noreferrer')
    onClose()
    // Reset form
    setSubject('')
    setDescription('')
    setIncludeTelemetry(false)
  } catch (e: any) {
    toast.error(`Erro ao criar issue: ${e.message}`)
  } finally {
    setLoading(false)
  }
}
```

**Validação (antes de enviar):**
- subject: obrigatório, mínimo 5 caracteres, máximo 200
- description: obrigatório, mínimo 20 caracteres, máximo 5000
- Mostrar contador de caracteres no textarea (ex: "143/5000")

**Visual do modal:**
```
┌─────────────────────────────────────────────────┐
│ 🐛 Reportar Problema / Enviar Feedback    [✕]   │
├─────────────────────────────────────────────────┤
│ Assunto *                                        │
│ [Input: "Descreva o problema..."]               │
│                                                  │
│ Descrição *                                      │
│ [Textarea: "O que aconteceu?"]                  │
│                                          143/5000│
│                                                  │
│ ☐ Incluir informações técnicas                  │
│   (heartbeat, último erro registrado)            │
│                                                  │
│ Seu feedback vai direto para o GitHub Issues.   │
│ Máximo 5 reports por hora.                      │
│                                                  │
│              [Cancelar]  [🚀 Enviar Report]     │
└─────────────────────────────────────────────────┘
```

**Use:**
- `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle` do shadcn/ui
- `Input`, `Textarea`, `Checkbox`, `Button`, `Label` do shadcn/ui
- `toast` do sonner para feedback
- `useState` para form state
- `supabase.functions.invoke` para chamar a edge fn

---

### 3. Integração no Header

```typescript
// Em _root.tsx ou no layout principal:
import { ReportIssueModal } from '@/components/ReportIssueModal'

// No JSX:
<ReportIssueModal open={reportOpen} onClose={() => setReportOpen(false)} />
```

---

### Restrições

- NÃO modificar rotas, tabelas, ou edge functions existentes
- NÃO remover nenhum elemento existente do header
- O botão "?" deve aparecer em TODAS as páginas autenticadas (via layout global)
- TypeScript estrito — sem `any` exceto no catch
- Edge fn `report-issue` já existe — apenas consumi-la
- Secret `GITHUB_REPORT_ISSUE_TOKEN` já será configurado pelo PM antes do deploy
```

---

## Migration necessária (PM aplica via lovable_query_sql)

```sql
-- Tabela de rate limiting para report-issue
CREATE TABLE IF NOT EXISTS public.report_issues_log (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  subject text NOT NULL,
  issue_url text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Índice para rate limit queries
CREATE INDEX IF NOT EXISTS idx_report_issues_log_user_created
  ON public.report_issues_log (user_id, created_at DESC);

-- RLS: apenas admins leem, todos authenticated podem inserir
ALTER TABLE public.report_issues_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users can insert own reports"
  ON public.report_issues_log FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);
```

---

## Checklist pós-deploy (PM valida)

- [ ] Secret `GITHUB_REPORT_ISSUE_TOKEN` adicionado no Supabase Dashboard
- [ ] Migration `report_issues_log` aplicada via lovable_query_sql
- [ ] Edge fn `report-issue` deployada (ou confirmar que auto-deployou)
- [ ] Botão "?" visível no header em todas as páginas autenticadas
- [ ] Modal abre ao clicar
- [ ] Submit cria issue no GitHub (testar com assunto "Teste SHIP-1")
- [ ] Link do issue abre em nova aba após submit
- [ ] Rate limit funciona (mais de 5 em 1h retorna erro)
