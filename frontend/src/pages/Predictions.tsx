import { Loader2, RefreshCw, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TooltipBox } from '../components/charts/ChartTooltip'
import { Card, Empty, ErrorNote, PageHeader, RiskBadge, Spinner, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { useChartColors } from '../hooks/useChartColors'
import { api } from '../services/api'
import { formatDate, formatDateTime, formatTime, num, pct } from '../services/format'
import type { ModelMetrics, RetrainStatus } from '../types'

const METRIC_COLUMNS: { key: 'no_show_recall' | 'no_show_precision' | 'no_show_f1' | 'roc_auc' | 'pr_auc' | 'accuracy'; label: string }[] = [
  { key: 'no_show_recall', label: 'No-show recall' },
  { key: 'no_show_precision', label: 'No-show precision' },
  { key: 'no_show_f1', label: 'No-show F1' },
  { key: 'roc_auc', label: 'ROC-AUC' },
  { key: 'pr_auc', label: 'PR-AUC' },
  { key: 'accuracy', label: 'Accuracy' },
]

export default function PredictionsPage() {
  const navigate = useNavigate()
  const { hasRole } = useAuth()
  const model = useAsync(() => api.modelInfo(), [])
  const [minProb, setMinProb] = useState(0.3)
  const upcoming = useAsync(() => api.highRisk(14, 50, minProb), [minProb])
  const [batchMsg, setBatchMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [retrain, setRetrain] = useState<RetrainStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { reload: reloadModel } = model
  const { reload: reloadUpcoming } = upcoming

  useEffect(() => {
    if (retrain?.state !== 'running') return
    const t = window.setInterval(async () => {
      try {
        const s = await api.retrainStatus()
        setRetrain(s)
        if (s.state !== 'running') { reloadModel(); reloadUpcoming() }
      } catch { /* keep polling */ }
    }, 2500)
    return () => window.clearInterval(t)
  }, [retrain?.state, reloadModel, reloadUpcoming])

  async function scoreUpcoming() {
    setBusy(true); setError(null)
    try {
      const r = await api.batchPredict(30)
      setBatchMsg(`Scored ${r.scored} upcoming appointments: ${Object.entries(r.risk_counts).map(([k, v]) => `${v} ${k}`).join(', ') || 'none'}`)
      upcoming.reload()
    } catch (e) { setError(e instanceof Error ? e.message : 'Batch scoring failed') } finally { setBusy(false) }
  }
  async function startRetrain() {
    setError(null)
    try { setRetrain(await api.retrain('db')) } catch (e) { setError(e instanceof Error ? e.message : 'Could not start retraining') }
  }

  const m = model.data?.metrics
  return (
    <>
      <PageHeader
        title="Predictions"
        description="Upcoming appointment risk, model evaluation and retraining."
        actions={
          <>
            {hasRole('ADMIN', 'STAFF') && <button className="btn btn-ghost" onClick={scoreUpcoming} disabled={busy}>{busy ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />} Score next 30 days</button>}
            {hasRole('ADMIN') && <button className="btn btn-primary" onClick={startRetrain} disabled={retrain?.state === 'running'}>{retrain?.state === 'running' ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Retrain from live data</button>}
          </>
        }
      />
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      {batchMsg && <p className="mb-4 rounded-lg border border-line bg-surface p-3 text-sm">{batchMsg}</p>}
      {retrain && retrain.state !== 'idle' && (
        <p className="mb-4 rounded-lg border border-line bg-surface p-3 text-sm">
          Retraining <span className="font-semibold">{retrain.state}</span>{retrain.detail ? ` · ${retrain.detail}` : ''}{retrain.finished_at ? ` · finished ${formatDateTime(retrain.finished_at)}` : ''}
        </p>
      )}

      <Card
        title="Upcoming appointments by risk"
        subtitle="Next 14 days · latest stored prediction for each appointment"
        action={
          <select className="input w-auto py-1 text-xs" value={minProb} onChange={(e) => setMinProb(Number(e.target.value))} aria-label="Minimum probability">
            <option value={0}>All scored</option><option value={0.3}>MEDIUM and HIGH</option><option value={model.data?.risk_thresholds.medium_max ?? 0.6}>HIGH only</option>
          </select>
        }
      >
        {upcoming.loading ? <Spinner /> : upcoming.error ? <ErrorNote message={upcoming.error} /> : !upcoming.data?.length ? <Empty>No upcoming appointments at this risk level.</Empty> : (
          <Table head={['Patient', 'Department', 'Doctor', 'Appointment', 'Top model factor', 'Risk']}>
            {upcoming.data.map((a) => (
              <tr key={a.appointment_id} className="cursor-pointer hover:bg-surface-2" onClick={() => navigate(`/appointments/${a.appointment_id}`)}>
                <td className="px-3 py-2.5 font-medium">{a.patient_name}</td>
                <td className="px-3 py-2.5">{a.department_name}</td>
                <td className="px-3 py-2.5 text-ink-2">{a.doctor_name}</td>
                <td className="tabular whitespace-nowrap px-3 py-2.5 text-ink-2">{formatDate(a.appointment_date)} · {formatTime(a.appointment_time)}</td>
                <td className="px-3 py-2.5 text-xs text-ink-2">{a.top_factor ?? '–'}</td>
                <td className="px-3 py-2.5"><RiskBadge level={a.risk_level} probability={a.no_show_probability} /></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {model.loading ? <Spinner /> : model.error ? <ErrorNote message={model.error} /> : !m ? <Card className="mt-6"><Empty>No trained model yet. Run <code>python -m app.ml.train</code>.</Empty></Card> : (
        <>
          <div className="mt-6 grid gap-6 lg:grid-cols-3">
            <Card title="Active model">
              <dl className="grid grid-cols-2 gap-y-2 text-sm">
                <dt className="text-muted">Algorithm</dt><dd className="text-right font-medium">{m.models[m.selected_model].display_name}</dd>
                <dt className="text-muted">Version</dt><dd className="tabular text-right">{m.model_version}</dd>
                <dt className="text-muted">Trained</dt><dd className="text-right">{formatDateTime(m.trained_at)}</dd>
                <dt className="text-muted">Data source</dt><dd className="text-right">{m.data_source === 'csv' ? 'Synthetic CSV' : 'Live database'}</dd>
                <dt className="text-muted">Labelled rows</dt><dd className="tabular text-right">{num(m.dataset.labelled_rows)}</dd>
                <dt className="text-muted">Base no-show rate</dt><dd className="tabular text-right">{pct(m.dataset.no_show_rate)}</dd>
                <dt className="text-muted">Alert threshold</dt><dd className="tabular text-right">{pct(model.data?.decision_threshold)}</dd>
                <dt className="text-muted">Risk bands</dt><dd className="tabular text-right">LOW &lt; {pct(model.data?.risk_thresholds.low_max, 0)} · HIGH ≥ {pct(model.data?.risk_thresholds.medium_max, 0)}</dd>
              </dl>
              <p className="mt-3 text-xs text-muted">Selection: {m.selection_criterion}. Split: {m.split_strategy}.</p>
            </Card>
            <Card title="Confusion matrix" subtitle={`Held-out test set · threshold ${pct(m.models[m.selected_model].test.threshold, 0)}`}>
              <ConfusionMatrix metrics={m} />
            </Card>
            <Card title="What the model relies on" subtitle="Mean |SHAP| on the test set (global importance)">
              <ImportanceChart metrics={m} />
            </Card>
          </div>

          <Card className="mt-6" title="Model comparison" subtitle="Held-out test set (most recent 15% of appointments). Selected on validation no-show F1, not accuracy.">
            <Table head={['Model', 'Threshold', ...METRIC_COLUMNS.map((c) => c.label)]}>
              {Object.entries(m.models).map(([key, r]) => (
                <tr key={key} className={key === m.selected_model ? 'bg-brand-soft/60' : ''}>
                  <td className="px-3 py-2.5 font-medium">{r.display_name}{key === m.selected_model && <span className="ml-2 rounded bg-brand px-1.5 py-0.5 text-[10px] font-semibold text-white">SELECTED</span>}</td>
                  <td className="tabular px-3 py-2.5">{r.test.threshold.toFixed(2)}</td>
                  {METRIC_COLUMNS.map((c) => <td key={c.key} className="tabular px-3 py-2.5">{c.key.startsWith('no_show') || c.key === 'accuracy' ? pct(r.test[c.key]) : r.test[c.key].toFixed(3)}</td>)}
                </tr>
              ))}
            </Table>
            {m.synthetic_data && <p className="mt-3 text-xs text-muted">Trained and evaluated on synthetic data - metrics describe the pipeline, not real-world performance.</p>}
          </Card>
        </>
      )}
    </>
  )
}

function ConfusionMatrix({ metrics }: { metrics: ModelMetrics }) {
  const cm = metrics.models[metrics.selected_model].test.confusion_matrix
  const total = cm.tn + cm.fp + cm.fn + cm.tp
  const cell = (label: string, v: number, strong: boolean) => (
    <div className={`rounded-lg p-3 text-center ${strong ? 'bg-brand-soft' : 'bg-surface-2'}`}>
      <p className="tabular text-xl font-semibold">{num(v)}</p>
      <p className="text-[11px] text-ink-2">{label}</p>
      <p className="tabular text-[11px] text-muted">{pct(v / total)}</p>
    </div>
  )
  return (
    <div>
      <div className="mb-1 grid grid-cols-[80px_1fr_1fr] gap-2 text-center text-[11px] text-muted"><span /><span>Predicted attend</span><span>Predicted no-show</span></div>
      <div className="grid grid-cols-[80px_1fr_1fr] items-center gap-2">
        <span className="text-right text-[11px] text-muted">Attended</span>{cell('True negative', cm.tn, true)}{cell('False alarm', cm.fp, false)}
        <span className="text-right text-[11px] text-muted">No-show</span>{cell('Missed no-show', cm.fn, false)}{cell('Caught no-show', cm.tp, true)}
      </div>
    </div>
  )
}

function ImportanceChart({ metrics }: { metrics: ModelMetrics }) {
  const c = useChartColors()
  const data = metrics.global_feature_importance.slice(0, 8)
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, left: 4, bottom: 0 }} barCategoryGap={4}>
        <CartesianGrid stroke={c['--grid']} horizontal={false} />
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="label" width={150} tick={{ fill: c['--ink-2'], fontSize: 11 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} />
        <Tooltip cursor={{ fill: c['--grid'], opacity: 0.4 }} content={({ active, payload }) => active && payload?.length ? <TooltipBox title={String(payload[0].payload.label)} rows={[{ label: 'Mean |SHAP|', value: Number(payload[0].value).toFixed(3) }]} /> : null} />
        <Bar dataKey="mean_abs_shap" fill={c['--series-1']} radius={[0, 4, 4, 0]} maxBarSize={14} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}
