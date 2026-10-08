import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartColors } from '../../hooks/useChartColors'
import { num, pct, rateTicks } from '../../services/format'
import type { TrendPoint } from '../../types'
import { TooltipBox } from './ChartTooltip'

const label = (iso: string, granularity: string) => {
  const d = new Date(`${iso}T00:00:00`)
  return granularity === 'month'
    ? d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
    : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

/** One measure, one axis: the no-show rate over time (volume lives in its own chart, never a 2nd axis). */
export function TrendLineChart({ points, granularity, height = 260 }: { points: TrendPoint[]; granularity: string; height?: number }) {
  const c = useChartColors()
  const data = points.filter((p) => p.no_show_rate !== null).map((p) => ({ ...p, x: label(p.period, granularity) }))
  const ticks = rateTicks(Math.max(...data.map((d) => d.no_show_rate ?? 0), 0))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 12, left: -12, bottom: 0 }}>
        <CartesianGrid stroke={c['--grid']} vertical={false} />
        <XAxis dataKey="x" tick={{ fill: c['--ink-muted'], fontSize: 11 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} minTickGap={16} />
        <YAxis tickFormatter={(v) => pct(v, 0)} tick={{ fill: c['--ink-muted'], fontSize: 11 }} axisLine={false} tickLine={false} ticks={ticks} domain={[0, ticks[ticks.length - 1]]} />
        <Tooltip
          cursor={{ stroke: c['--axis'], strokeWidth: 1 }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as TrendPoint & { x: string }
            return <TooltipBox title={d.x} rows={[{ label: 'No-show rate', value: pct(d.no_show_rate) }, { label: 'No-shows', value: num(d.no_shows) }, { label: 'Appointments', value: num(d.total) }]} />
          }}
        />
        <Line type="monotone" dataKey="no_show_rate" stroke={c['--series-1']} strokeWidth={2} dot={false} activeDot={{ r: 5, strokeWidth: 2, stroke: c['--surface'] }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}
