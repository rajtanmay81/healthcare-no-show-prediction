import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useChartColors } from '../../hooks/useChartColors'
import { num } from '../../services/format'
import { TooltipBox } from './ChartTooltip'

/** Single-series count chart (e.g. appointments by status, volume per period). */
export function CountBarChart({ data, height = 240, valueLabel = 'Appointments', columns = false }: { data: { label: string; value: number }[]; height?: number; valueLabel?: string; columns?: boolean }) {
  const c = useChartColors()
  if (columns) {
    // Time series: time runs left to right.
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }} barCategoryGap={4}>
          <CartesianGrid stroke={c['--grid']} vertical={false} />
          <XAxis dataKey="label" tick={{ fill: c['--ink-muted'], fontSize: 11 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} minTickGap={8} />
          <YAxis tick={{ fill: c['--ink-muted'], fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => num(v)} />
          <Tooltip
            cursor={{ fill: c['--grid'], opacity: 0.4 }}
            content={({ active, payload }) => (active && payload?.length ? <TooltipBox title={String(payload[0].payload.label)} rows={[{ label: valueLabel, value: num(Number(payload[0].value)) }]} /> : null)}
          />
          <Bar dataKey="value" fill={c['--series-1']} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    )
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 56, left: 8, bottom: 0 }} barCategoryGap={6}>
        <CartesianGrid stroke={c['--grid']} horizontal={false} />
        <XAxis type="number" tick={{ fill: c['--ink-muted'], fontSize: 11 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} tickFormatter={(v) => num(v)} />
        <YAxis type="category" dataKey="label" width={86} interval={0} tick={{ fill: c['--ink-2'], fontSize: 12 }} axisLine={{ stroke: c['--axis'] }} tickLine={false} />
        <Tooltip
          cursor={{ fill: c['--grid'], opacity: 0.4 }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as { label: string; value: number }
            return <TooltipBox title={d.label} rows={[{ label: valueLabel, value: num(d.value) }]} />
          }}
        />
        <Bar dataKey="value" fill={c['--series-1']} radius={[0, 4, 4, 0]} maxBarSize={18} isAnimationActive={false}>
          <LabelList dataKey="value" position="right" formatter={(v: unknown) => num(Number(v))} style={{ fill: c['--ink-2'], fontSize: 11 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
