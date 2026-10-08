import { Check, Copy, Loader2, MessageSquareText } from 'lucide-react'
import { useState } from 'react'
import { api } from '../services/api'
import type { ReminderChannel, ReminderResponse, ReminderTone } from '../types'
import { AIMetaNote, Card, ErrorNote, Field } from './ui'

export function ReminderPanel({ appointmentId }: { appointmentId: number }) {
  const [channel, setChannel] = useState<ReminderChannel>('sms')
  const [tone, setTone] = useState<ReminderTone>('professional')
  const [result, setResult] = useState<ReminderResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  async function generate() {
    setBusy(true); setError(null); setCopied(false)
    try { setResult(await api.reminder(appointmentId, channel, tone)) } catch (e) { setError(e instanceof Error ? e.message : 'Could not generate reminder') } finally { setBusy(false) }
  }
  async function copy() {
    if (!result) return
    try {
      await navigator.clipboard.writeText(result.subject ? `Subject: ${result.subject}\n\n${result.message}` : result.message)
      setCopied(true)
    } catch { setError('Clipboard is not available in this browser') }
  }

  return (
    <Card title="Patient reminder" subtitle="Drafted by the assistant. Risk scores are never included in patient messages.">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Channel">
          <select className="input" value={channel} onChange={(e) => setChannel(e.target.value as ReminderChannel)}>
            <option value="sms">SMS</option><option value="email">Email</option><option value="whatsapp">WhatsApp</option>
          </select>
        </Field>
        <Field label="Tone">
          <select className="input" value={tone} onChange={(e) => setTone(e.target.value as ReminderTone)}>
            <option value="professional">Professional</option><option value="friendly">Friendly</option>
          </select>
        </Field>
      </div>
      <button className="btn btn-primary mt-3" onClick={generate} disabled={busy}>{busy ? <Loader2 size={15} className="animate-spin" /> : <MessageSquareText size={15} />} Generate reminder</button>
      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      {result && (
        <div className="mt-4 rounded-lg border border-line bg-surface-2 p-3">
          {result.subject && <p className="mb-2 text-sm"><span className="text-muted">Subject:</span> <span className="font-medium">{result.subject}</span></p>}
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.message}</p>
          <div className="mt-3 flex items-center justify-between">
            <span className="tabular text-xs text-muted">{result.character_count} characters</span>
            <button className="btn btn-ghost py-1 text-xs" onClick={copy}>{copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}</button>
          </div>
          <AIMetaNote meta={result.meta} />
        </div>
      )}
    </Card>
  )
}
