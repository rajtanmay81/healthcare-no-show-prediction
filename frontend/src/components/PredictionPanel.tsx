import { ArrowDown, ArrowUp, Info, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { api } from '../services/api'
import { formatDateTime, pct } from '../services/format'
import type { ExplainResponse, Prediction } from '../types'
import { AIMetaNote, Card, ErrorNote, RiskBadge } from './ui'

/** Diverging factor bars: red raises the estimate, blue lowers it; direction is also stated in text. */
export function FactorBars({ prediction }: { prediction: Prediction }) {
  const max = Math.max(...prediction.factors.map((f) => Math.abs(f.contribution)), 1e-6)
  return (
    <ul className="space-y-2.5">
      {prediction.factors.map((f) => {
        const up = f.direction === 'increases_risk'
        const width = `${(Math.abs(f.contribution) / max) * 50}%`
        return (
          <li key={f.feature}>
            <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
              <span><span className="font-medium">{f.label}</span>: <span className="text-ink-2">{f.display_value}</span></span>
              <span className={`inline-flex shrink-0 items-center gap-0.5 text-xs ${up ? 'text-critical-text' : 'text-brand-strong'}`}>
                {up ? <ArrowUp size={12} /> : <ArrowDown size={12} />}{up ? 'raises estimate' : 'lowers estimate'}
              </span>
            </div>
            <div className="relative h-2 rounded-full bg-surface-2" title={`SHAP contribution ${f.contribution.toFixed(3)}`}>
              <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--axis)]" />
              <div className="absolute inset-y-0 rounded-full" style={{ width, left: up ? '50%' : undefined, right: up ? undefined : '50%', background: up ? '#e34948' : 'var(--series-1)' }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export function PredictionPanel({ appointmentId, prediction, canPredict, onUpdated }: { appointmentId: number; prediction: Prediction | null; canPredict: boolean; onUpdated: (p: Prediction) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [explain, setExplain] = useState<ExplainResponse | null>(null)
  const [explaining, setExplaining] = useState(false)

  async function run() {
    setBusy(true); setError(null); setExplain(null)
    try { onUpdated(await api.predict(appointmentId)) } catch (e) { setError(e instanceof Error ? e.message : 'Prediction failed') } finally { setBusy(false) }
  }
  async function askAI() {
    setExplaining(true); setError(null)
    try { setExplain(await api.explain(appointmentId)) } catch (e) { setError(e instanceof Error ? e.message : 'Explanation failed') } finally { setExplaining(false) }
  }

  return (
    <Card
      title="No-show prediction"
      subtitle={prediction ? `${prediction.model_name.replace(/_/g, ' ')} · v${prediction.model_version} · ${formatDateTime(prediction.predicted_at)}` : 'Not scored yet'}
      action={canPredict && <button className="btn btn-ghost py-1.5 text-xs" onClick={run} disabled={busy}>{busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} {prediction ? 'Re-run' : 'Run prediction'}</button>}
    >
      {error && <div className="mb-3"><ErrorNote message={error} /></div>}
      {!prediction ? <p className="text-sm text-muted">Run the model to estimate this appointment's no-show probability.</p> : (
        <>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted">No-show probability</p>
              <p className="text-4xl font-semibold leading-tight">{pct(prediction.no_show_probability, 0)}</p>
            </div>
            <div className="pb-1.5"><RiskBadge level={prediction.risk_level} /></div>
            {prediction.flagged_by_model && <span className="pb-2 text-xs text-ink-2">Above the model's tuned alert threshold</span>}
          </div>
          <h3 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted">Top model factors</h3>
          <FactorBars prediction={prediction} />
          <p className="mt-4 flex gap-1.5 rounded-lg bg-surface-2 p-3 text-xs text-ink-2"><Info size={14} className="mt-0.5 shrink-0" />{prediction.explanation_note}</p>
          {canPredict && (
            <div className="mt-4">
              <button className="btn btn-ghost text-xs" onClick={askAI} disabled={explaining}>{explaining ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} Explain with AI assistant</button>
              {explain && (
                <div className="mt-3 rounded-lg border border-line p-3 text-sm leading-relaxed">
                  {explain.explanation}
                  <AIMetaNote meta={explain.meta} />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </Card>
  )
}
