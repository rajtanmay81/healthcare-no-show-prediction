import { Bot, Loader2, Send, User } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { AIMetaNote, Card, ErrorNote, Field, PageHeader } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import type { ChatResponse, SummaryResponse } from '../types'

const SUGGESTIONS = [
  'Which department has the highest no-show rate?',
  'How many appointments were missed this week?',
  'What is the no-show rate for Cardiology?',
  "Summarize this month's appointment trends.",
  'Which day has the highest number of no-shows?',
  'Show upcoming high-risk appointments',
]

type Message = { role: 'user'; text: string } | { role: 'assistant'; response: ChatResponse } | { role: 'error'; text: string }

export default function AssistantPage() {
  return (
    <>
      <PageHeader title="AI Assistant" description="Ask questions about appointment performance. Every number is computed from the database first; the assistant only explains it." />
      <div className="grid gap-6 xl:grid-cols-5">
        <div className="xl:col-span-3"><Chat /></div>
        <div className="xl:col-span-2"><DepartmentSummary /></div>
      </div>
    </>
  )
}

function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [messages])

  async function ask(q: string) {
    const text = q.trim()
    if (text.length < 3 || busy) return
    setMessages((m) => [...m, { role: 'user', text }])
    setQuestion('')
    setBusy(true)
    try {
      const response = await api.chat(text)
      setMessages((m) => [...m, { role: 'assistant', response }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'error', text: e instanceof Error ? e.message : 'Request failed' }])
    } finally { setBusy(false) }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void ask(question) }

  return (
    <Card title="Ask about your appointments">
      <div className="flex h-[520px] flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.length === 0 && (
            <div className="py-6">
              <p className="mb-3 text-sm text-ink-2">Try one of these:</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => <button key={s} className="rounded-full border border-line px-3 py-1.5 text-left text-xs text-ink-2 hover:border-brand hover:text-ink" onClick={() => ask(s)}>{s}</button>)}
              </div>
            </div>
          )}
          {messages.map((m, i) => m.role === 'user' ? (
            <div key={i} className="flex justify-end gap-2"><p className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand px-3.5 py-2 text-sm text-white">{m.text}</p><User size={18} className="mt-1 shrink-0 text-muted" /></div>
          ) : m.role === 'error' ? (
            <ErrorNote key={i} message={m.text} />
          ) : (
            <div key={i} className="flex gap-2">
              <Bot size={18} className="mt-1 shrink-0 text-brand" />
              <div className="max-w-[88%] rounded-2xl rounded-bl-sm border border-line bg-surface-2 px-3.5 py-2.5 text-sm leading-relaxed">
                <p className="whitespace-pre-wrap">{m.response.answer}</p>
                <details className="mt-2 text-xs text-ink-2">
                  <summary className="cursor-pointer select-none text-muted">Grounding data · {m.response.intent.replace(/_/g, ' ')} · {m.response.period_label}</summary>
                  <pre className="mt-2 max-h-60 overflow-auto rounded-md bg-surface p-2 text-[11px]">{JSON.stringify(m.response.data, null, 2)}</pre>
                </details>
                <AIMetaNote meta={m.response.meta} />
              </div>
            </div>
          ))}
          {busy && <p className="flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin" /> Computing statistics…</p>}
          <div ref={endRef} />
        </div>
        <form onSubmit={submit} className="mt-3 flex gap-2 border-t border-line pt-3">
          <input className="input" placeholder="e.g. What was the no-show rate for Dermatology last month?" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} aria-label="Question" />
          <button className="btn btn-primary" disabled={busy || question.trim().length < 3} aria-label="Send"><Send size={15} /></button>
        </form>
      </div>
    </Card>
  )
}

const PERIOD_OPTIONS = [
  ['today', 'Today'], ['yesterday', 'Yesterday'], ['this_week', 'This week'], ['last_week', 'Last week'],
  ['last_7_days', 'Last 7 days'], ['this_month', 'This month'], ['last_month', 'Last month'], ['last_30_days', 'Last 30 days'],
  ['last_90_days', 'Last 90 days'], ['this_year', 'This year'], ['all_time', 'All time'],
] as const

function DepartmentSummary() {
  const departments = useAsync(() => api.departments(), [])
  const [departmentId, setDepartmentId] = useState<number | ''>('')
  const [period, setPeriod] = useState('today')
  const [result, setResult] = useState<SummaryResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setBusy(true); setError(null)
    try { setResult(await api.departmentSummary({ period, department_id: departmentId || undefined })) } catch (e) { setError(e instanceof Error ? e.message : 'Summary failed') } finally { setBusy(false) }
  }

  return (
    <Card title="Performance summary" subtitle="Statistics from PostgreSQL, summarised in plain language.">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Department">
          <select className="input" value={departmentId} onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">All departments</option>
            {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Period">
          <select className="input" value={period} onChange={(e) => setPeriod(e.target.value)}>
            {PERIOD_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
      </div>
      <button className="btn btn-primary mt-3" onClick={run} disabled={busy}>{busy && <Loader2 size={15} className="animate-spin" />} Summarise</button>
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      {result && (
        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">{result.department_name ?? 'All departments'} · {result.period_label}</p>
          <p className="mt-2 text-sm leading-relaxed">{result.summary}</p>
          <AIMetaNote meta={result.meta} />
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer text-muted">Statistics used</summary>
            <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-surface-2 p-2 text-[11px]">{JSON.stringify(result.statistics, null, 2)}</pre>
          </details>
        </div>
      )}
    </Card>
  )
}
