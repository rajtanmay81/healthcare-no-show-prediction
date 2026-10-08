import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartColors } from '../../hooks/useChartColors'
import { num, pct, rateTicks } from '../../services/format'
import { TooltipBox } from './ChartTooltip'

export interface RateDatum { label: string; rate: number | null; noShows: number; total: number }

/** Single-series magnitude chart: one hue, thin bars, rounded data-ends, value labels, hover tooltip. */
export function RateBarChart({ data, height = 260, layout = 'vertical' }: { data: RateDatum[]; height?: number; layout?: 'vertical' | 'horizontal' }) {
  const c = useChartColors()
  const rows = data.map((d) => ({ ...d, value: d.rate ?? 0 }))
  const horizontal = layout === 'horizontal'
  const ticks = rateTicks(Math.max(...rows.map((r) => r.value), 0))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ top: 18, right: horizontal ? 48 : 8, left: horizontal ? 8 : -12, bottom: 0 }} barCategoryGap={horizontal ? 6 : 10}>
        <CartesianGrid stroke={c['--grid']} strokeWidth={1} vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" ticks={ticks} domain={[0, ticks[ticks.length - 1]]} tickFormatter={(v) => pct(v, 0)} tick={{ fill: c['--ink-muted'], fontSize: 11 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} />
            <YAxis type="category" dataKey="label" width={118} tick={{ fill: c['--ink-2'], fontSize: 12 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} />
          </>
        ) : (
          <>
            <XAxis dataKey="label" tick={{ fill: c['--ink-2'], fontSize: 11 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} interval={0} />
            <YAxis ticks={ticks} domain={[0, ticks[ticks.length - 1]]} tickFormatter={(v) => pct(v, 0)} tick={{ fill: c['--ink-muted'], fontSize: 11 }} axisLine={false} tickLine={false} />
          </>
        )}
        <Tooltip
          cursor={{ fill: c['--grid'], opacity: 0.4 }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as RateDatum
            return <TooltipBox title={d.label} rows={[{ label: 'No-show rate', value: pct(d.rate) }, { label: 'No-shows', value: num(d.noShows) }, { label: 'Attended or missed', value: num(d.total) }]} />
          }}
        />
        <Bar dataKey="value" fill={c['--series-1']} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} maxBarSize={horizontal ? 18 : 36} isAnimationActive={false}>
          <LabelList dataKey="value" position={horizontal ? 'right' : 'top'} formatter={(v: unknown) => pct(Number(v))} style={{ fill: c['--ink-2'], fontSize: 11 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
