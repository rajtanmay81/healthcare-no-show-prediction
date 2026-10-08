import { ArrowRight } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CountBarChart } from '../components/charts/CountBarChart'
import { RateBarChart } from '../components/charts/RateBarChart'
import { RiskDistributionBars } from '../components/charts/RiskDistributionBars'
import { TrendLineChart } from '../components/charts/TrendLineChart'
import { Card, Empty, ErrorNote, PageHeader, RiskBadge, Spinner, StatTile, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import { PeriodFilter } from '../components/PeriodFilter'
import { periodRange } from '../services/periods'
import { formatDate, formatTime, num, pct, statusLabel, todayIso } from '../services/format'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [period, setPeriod] = useState('all')
  const filter = periodRange(period)

  const overview = useAsync(() => api.overview(filter), [period])
  const departments = useAsync(() => api.departmentStats(filter), [period])
  const dow = useAsync(() => api.dayOfWeek(filter), [period])
  const trends = useAsync(() => api.trends('month', { date_from: todayIso(-365) }), [])
  const risk = useAsync(() => api.riskDistribution(30), [])
  const model = useAsync(() => api.modelInfo(), [])
  const highRisk = useAsync(() => api.highRisk(14, 8), [])

  const o = overview.data
  return (
    <>
      <PageHeader title="Dashboard" description="Attendance performance and upcoming no-show risk across the hospital." actions={<PeriodFilter value={period} onChange={setPeriod} />} />

      {overview.error && <ErrorNote message={overview.error} onRetry={overview.reload} />}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Total appointments" value={o ? num(o.total_appointments) : '…'} hint={o ? `${num(o.upcoming)} upcoming` : undefined} />
        <StatTile label="Completed" value={o ? num(o.completed) : '…'} />
        <StatTile label="Cancelled" value={o ? num(o.cancelled) : '…'} hint={o ? `${pct(o.cancellation_rate)} of bookings` : undefined} />
        <StatTile label="No-shows" value={o ? num(o.no_shows) : '…'} />
        <StatTile label="No-show rate" value={o ? pct(o.no_show_rate) : '…'} hint="of attended + missed" />
        <StatTile label="High-risk upcoming" value={o ? num(o.high_risk_upcoming) : '…'} tone="critical" hint="HIGH risk, not yet held" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Card
          className="xl:col-span-2"
          title="Upcoming high-risk appointments"
          subtitle="Next 14 days · sorted by predicted no-show probability"
          action={<Link to="/predictions" className="inline-flex items-center gap-1 text-xs font-medium text-brand-strong hover:underline">All predictions <ArrowRight size={13} /></Link>}
        >
          {highRisk.loading ? <Spinner /> : highRisk.error ? <ErrorNote message={highRisk.error} /> : !highRisk.data?.length ? <Empty>No HIGH-risk appointments in the next 14 days.</Empty> : (
            <Table head={['Patient', 'Department', 'Appointment', 'Top model factor', 'Risk']}>
              {highRisk.data.map((a) => (
                <tr key={a.appointment_id} className="cursor-pointer hover:bg-surface-2" onClick={() => navigate(`/appointments/${a.appointment_id}`)}>
                  <td className="px-3 py-2.5 font-medium">{a.patient_name}</td>
                  <td className="px-3 py-2.5 text-ink-2">{a.department_name}</td>
                  <td className="tabular whitespace-nowrap px-3 py-2.5 text-ink-2">{formatDate(a.appointment_date)} · {formatTime(a.appointment_time)}</td>
                  <td className="px-3 py-2.5 text-xs text-ink-2">{a.top_factor ?? '–'}</td>
                  <td className="px-3 py-2.5"><RiskBadge level={a.risk_level} probability={a.no_show_probability} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        <Card title="Risk distribution" subtitle="Upcoming appointments, next 30 days">
          {risk.loading ? <Spinner /> : risk.error ? <ErrorNote message={risk.error} /> : risk.data && <RiskDistributionBars dist={risk.data} thresholds={model.data?.risk_thresholds} />}
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="No-show rate by department" subtitle="Share of attended + missed appointments that were missed">
          {departments.loading ? <Spinner /> : departments.error ? <ErrorNote message={departments.error} /> : (
            <RateBarChart
              layout="horizontal"
              height={300}
              data={[...(departments.data ?? [])].sort((a, b) => (b.no_show_rate ?? 0) - (a.no_show_rate ?? 0)).map((d) => ({ label: d.department_name, rate: d.no_show_rate, noShows: d.no_shows, total: d.completed + d.no_shows }))}
            />
          )}
        </Card>
        <Card title="No-show trend" subtitle="Monthly no-show rate, last 12 months">
          {trends.loading ? <Spinner /> : trends.error ? <ErrorNote message={trends.error} /> : <TrendLineChart points={trends.data?.points ?? []} granularity="month" height={300} />}
        </Card>
        <Card title="Appointments by status">
          {o && <CountBarChart data={(['completed', 'no_show', 'cancelled', 'scheduled', 'confirmed'] as const).map((s) => ({ label: statusLabel(s), value: o.status_counts[s] }))} />}
        </Card>
        <Card title="No-show rate by day of week">
          {dow.loading ? <Spinner /> : dow.error ? <ErrorNote message={dow.error} /> : (
            <RateBarChart height={240} data={(dow.data ?? []).filter((d) => d.total > 0).map((d) => ({ label: d.day.slice(0, 3), rate: d.no_show_rate, noShows: d.no_shows, total: d.total }))} />
          )}
        </Card>
      </div>
    </>
  )
}
