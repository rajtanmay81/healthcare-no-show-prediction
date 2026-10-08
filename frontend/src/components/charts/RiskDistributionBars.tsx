import { AlertTriangle, CheckCircle2, CircleAlert } from 'lucide-react'
import { num, pct } from '../../services/format'
import type { RiskDistribution, RiskLevel } from '../../types'

const META: Record<RiskLevel, { bar: string; text: string; icon: typeof CheckCircle2 }> = {
  LOW: { bar: 'bg-good', text: 'text-good-text', icon: CheckCircle2 },
  MEDIUM: { bar: 'bg-warning', text: 'text-warning-text', icon: CircleAlert },
  HIGH: { bar: 'bg-critical', text: 'text-critical-text', icon: AlertTriangle },
}

/** Risk levels use the reserved status palette, always paired with an icon and a text label. */
export function RiskDistributionBars({ dist, thresholds }: { dist: RiskDistribution; thresholds?: { low_max: number; medium_max: number } }) {
  const total = dist.scored_upcoming || 1
  const bands: Record<RiskLevel, string> = thresholds
    ? { LOW: `< ${pct(thresholds.low_max, 0)}`, MEDIUM: `${pct(thresholds.low_max, 0)}–${pct(thresholds.medium_max, 0)}`, HIGH: `≥ ${pct(thresholds.medium_max, 0)}` }
    : { LOW: '', MEDIUM: '', HIGH: '' }
  return (
    <div className="space-y-4">
      {dist.by_level.map(({ risk_level, count }) => {
        const m = META[risk_level]
        const Icon = m.icon
        const share = count / total
        return (
          <div key={risk_level} title={`${risk_level}: ${count} appointments (${pct(share)})`}>
            <div className="mb-1.5 flex items-center justify-between text-sm">
              <span className={`inline-flex items-center gap-1.5 font-semibold ${m.text}`}><Icon size={14} />{risk_level}<span className="text-xs font-normal text-muted">{bands[risk_level]}</span></span>
              <span className="tabular text-ink-2"><span className="font-semibold text-ink">{num(count)}</span> · {pct(share, 0)}</span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-2">
              <div className={`h-full rounded-full ${m.bar}`} style={{ width: `${Math.max(share * 100, count ? 1.5 : 0)}%` }} />
            </div>
          </div>
        )
      })}
      <p className="text-xs text-muted">{num(dist.scored_upcoming)} upcoming appointments scored in the next {dist.days_ahead} days{dist.unscored_upcoming ? ` · ${dist.unscored_upcoming} not yet scored` : ''}.</p>
    </div>
  )
}
