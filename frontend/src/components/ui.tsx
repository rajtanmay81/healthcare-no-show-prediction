import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Loader2, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { pct, statusLabel } from '../services/format'
import type { RiskLevel } from '../types'

export function Card({ title, subtitle, action, children, className = '' }: { title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(0,0,0,0.04)] ${className}`}>
      {(title || action) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 text-sm text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function StatTile({ label, value, hint, tone = 'default' }: { label: string; value: ReactNode; hint?: ReactNode; tone?: 'default' | 'critical' }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-2 text-[28px] font-semibold leading-none ${tone === 'critical' ? 'text-critical-text' : 'text-ink'}`}>{value}</p>
      {hint && <p className="mt-2 text-xs text-ink-2">{hint}</p>}
    </div>
  )
}

const RISK_STYLE: Record<RiskLevel, { dot: string; text: string; icon: ReactNode }> = {
  LOW: { dot: 'bg-good', text: 'text-good-text', icon: <CheckCircle2 size={13} /> },
  MEDIUM: { dot: 'bg-warning', text: 'text-warning-text', icon: <CircleAlert size={13} /> },
  HIGH: { dot: 'bg-critical', text: 'text-critical-text', icon: <AlertTriangle size={13} /> },
}

/** Risk always carries icon + label, never color alone. */
export function RiskBadge({ level, probability }: { level: RiskLevel; probability?: number }) {
  const s = RISK_STYLE[level]
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-line bg-surface-2 px-2 py-0.5 text-xs font-semibold ${s.text}`}>
      {s.icon}
      {level}
      {probability !== undefined && <span className="tabular font-medium text-ink-2">· {pct(probability, 0)}</span>}
    </span>
  )
}

const STATUS_STYLE: Record<string, string> = {
  scheduled: 'bg-brand-soft text-brand-strong',
  confirmed: 'bg-brand-soft text-brand-strong',
  completed: 'bg-surface-2 text-good-text',
  cancelled: 'bg-surface-2 text-muted',
  no_show: 'bg-surface-2 text-critical-text',
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[status] ?? 'bg-surface-2 text-ink-2'}`}>{statusLabel(status)}</span>
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted">
      <Loader2 className="animate-spin" size={16} /> {label}
    </div>
  )
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-line bg-surface-2 p-3 text-sm text-critical-text" role="alert">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry && <button className="font-medium underline" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-sm text-muted">{children}</p>
}

export function Modal({ title, open, onClose, children }: { title: string; open: boolean; onClose: () => void; children: ReactNode }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onMouseDown={onClose}>
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-line bg-surface p-6 shadow-xl" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={title}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-muted hover:bg-surface-2" aria-label="Close"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  )
}

export function Pagination({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  const page = Math.floor(offset / limit) + 1
  const pages = Math.max(1, Math.ceil(total / limit))
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-ink-2">
      <span className="tabular">{total.toLocaleString()} records · page {page} of {pages}</span>
      <div className="flex gap-2">
        <button className="btn btn-ghost px-2" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))} aria-label="Previous page"><ChevronLeft size={16} /></button>
        <button className="btn btn-ghost px-2" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)} aria-label="Next page"><ChevronRight size={16} /></button>
      </div>
    </div>
  )
}

export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
            {head.map((h, i) => <th key={i} className="px-3 py-2 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">{children}</tbody>
      </table>
    </div>
  )
}

export function AIMetaNote({ meta }: { meta: { llm_used: boolean; provider: string; model: string | null; grounding_check: string } }) {
  const text = meta.llm_used
    ? `Generated by ${meta.provider}${meta.model ? ` (${meta.model})` : ''} · numbers verified against database facts`
    : meta.grounding_check === 'fallback_used'
      ? 'LLM output rejected or unavailable · grounded template used'
      : 'Grounded template (no LLM provider configured)'
  return <p className="mt-2 text-[11px] text-muted">{text}</p>
}
