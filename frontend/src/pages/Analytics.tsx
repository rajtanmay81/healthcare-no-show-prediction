import { useState } from 'react'
import { CountBarChart } from '../components/charts/CountBarChart'
import { RateBarChart } from '../components/charts/RateBarChart'
import { TrendLineChart } from '../components/charts/TrendLineChart'
import { PeriodFilter } from '../components/PeriodFilter'
import { periodRange } from '../services/periods'
import { Card, ErrorNote, PageHeader, Spinner, StatTile, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import { formatDate, num, pct } from '../services/format'

type Granularity = 'day' | 'week' | 'month'

export default function AnalyticsPage() {
  const [period, setPeriod] = useState('365')
  const [departmentId, setDepartmentId] = useState<number | ''>('')
  const [granularity, setGranularity] = useState<Granularity>('month')
  const [showTable, setShowTable] = useState(false)
  const range = periodRange(period)
  const filter = { ...range, department_id: departmentId }

  const departments = useAsync(() => api.departments(), [])
  const overview = useAsync(() => api.overview(filter), [period, departmentId])
  const deptStats = useAsync(() => api.departmentStats(range), [period])
  const trends = useAsync(() => api.trends(granularity, filter), [period, departmentId, granularity])
  const dow = useAsync(() => api.dayOfWeek(filter), [period, departmentId])
  const o = overview.data

  return (
    <>
      <PageHeader title="Analytics" description="Department-wise attendance, no-show trends and weekday patterns, computed directly from PostgreSQL." />
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <PeriodFilter value={period} onChange={setPeriod} />
        <select className="input w-auto" value={departmentId} onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : '')} aria-label="Department">
          <option value="">All departments</option>
          {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select className="input w-auto" value={granularity} onChange={(e) => setGranularity(e.target.value as Granularity)} aria-label="Trend granularity">
          <option value="month">Monthly</option><option value="week">Weekly</option><option value="day">Daily</option>
        </select>
      </div>

      {overview.error && <ErrorNote message={overview.error} />}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Appointments" value={o ? num(o.total_appointments) : '…'} />
        <StatTile label="No-show rate" value={o ? pct(o.no_show_rate) : '…'} hint={o ? `${num(o.no_shows)} no-shows` : undefined} />
        <StatTile label="Cancellation rate" value={o ? pct(o.cancellation_rate) : '…'} hint={o ? `${num(o.cancelled)} cancelled` : undefined} />
        <StatTile label="Completed" value={o ? num(o.completed) : '…'} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="No-show rate over time" subtitle={`${granularity[0].toUpperCase()}${granularity.slice(1)}ly · periods without outcomes are omitted`}>
          {trends.loading ? <Spinner /> : trends.error ? <ErrorNote message={trends.error} /> : <TrendLineChart points={trends.data?.points ?? []} granularity={granularity} />}
        </Card>
        <Card title="Appointment volume" subtitle="Bookings per period (all statuses)">
          {trends.loading ? <Spinner /> : (
            <CountBarChart columns height={260} data={(trends.data?.points ?? []).map((p) => ({ label: granularity === 'month' ? new Date(`${p.period}T00:00:00`).toLocaleDateString(undefined, { month: 'short', year: '2-digit' }) : formatDate(p.period), value: p.total }))} />
          )}
        </Card>
        <Card title="No-show rate by day of week">
          {dow.loading ? <Spinner /> : dow.error ? <ErrorNote message={dow.error} /> : (
            <RateBarChart data={(dow.data ?? []).filter((d) => d.total).map((d) => ({ label: d.day.slice(0, 3), rate: d.no_show_rate, noShows: d.no_shows, total: d.total }))} />
          )}
        </Card>
        <Card title="No-show rate by department" subtitle="For the selected period (department filter not applied)">
          {deptStats.loading ? <Spinner /> : (
            <RateBarChart layout="horizontal" data={[...(deptStats.data ?? [])].sort((a, b) => (b.no_show_rate ?? 0) - (a.no_show_rate ?? 0)).map((d) => ({ label: d.department_name, rate: d.no_show_rate, noShows: d.no_shows, total: d.completed + d.no_shows }))} />
          )}
        </Card>
      </div>

      <Card className="mt-6" title="Department breakdown" action={<button className="btn btn-ghost py-1 text-xs" onClick={() => setShowTable((v) => !v)}>{showTable ? 'Hide' : 'Show'} table</button>}>
        {showTable && deptStats.data && (
          <Table head={['Department', 'Appointments', 'Completed', 'No-shows', 'Cancelled', 'No-show rate', 'Cancellation rate', 'Avg lead (days)', 'Upcoming', 'High-risk upcoming']}>
            {deptStats.data.map((d) => (
              <tr key={d.department_id}>
                <td className="px-3 py-2 font-medium">{d.department_name}</td>
                {[d.total_appointments, d.completed, d.no_shows, d.cancelled].map((v, i) => <td key={i} className="tabular px-3 py-2">{num(v)}</td>)}
                <td className="tabular px-3 py-2">{pct(d.no_show_rate)}</td>
                <td className="tabular px-3 py-2">{pct(d.cancellation_rate)}</td>
                <td className="tabular px-3 py-2">{d.avg_booking_lead_days ?? '–'}</td>
                <td className="tabular px-3 py-2">{num(d.upcoming)}</td>
                <td className="tabular px-3 py-2">{num(d.high_risk_upcoming)}</td>
              </tr>
            ))}
          </Table>
        )}
        {!showTable && <p className="text-sm text-muted">Tabular view of every department's figures for the selected period.</p>}
        {o && <p className="mt-3 text-xs text-muted">No-show rate = {o.no_show_rate_definition}.</p>}
      </Card>
    </>
  )
}
