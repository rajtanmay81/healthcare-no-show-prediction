import { ArrowLeft, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PredictionPanel } from '../components/PredictionPanel'
import { ReminderPanel } from '../components/ReminderPanel'
import { Card, ErrorNote, Field, PageHeader, Spinner, StatusBadge } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { api, ApiError } from '../services/api'
import { formatDate, formatDateTime, formatTime, statusLabel, todayIso } from '../services/format'
import type { AppointmentDetail, AppointmentStatus, Prediction } from '../types'

const TRANSITIONS: Record<AppointmentStatus, AppointmentStatus[]> = {
  scheduled: ['confirmed', 'completed', 'no_show', 'cancelled'],
  confirmed: ['completed', 'no_show', 'cancelled'],
  completed: [],
  cancelled: [],
  no_show: [],
}

export default function AppointmentDetailPage() {
  const id = Number(useParams().id)
  const { hasRole } = useAuth()
  const appt = useAsync(() => api.appointment(id), [id])
  const [updated, setDetail] = useState<AppointmentDetail | null>(null)
  const [prediction, setPrediction] = useState<Prediction | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notes, setNotes] = useState('')

  useEffect(() => {
    api.latestPrediction(id).then(setPrediction).catch((e) => { if (!(e instanceof ApiError && e.status === 404)) setError(e.message) })
  }, [id])

  const detail = updated?.id === id ? updated : appt.data
  if (appt.loading && !detail) return <Spinner />
  if (appt.error) return <ErrorNote message={appt.error} onRetry={appt.reload} />
  if (!detail) return null

  const today = todayIso()
  const isDoctor = hasRole('DOCTOR')
  const allowed = TRANSITIONS[detail.status].filter((s) => {
    if ((s === 'completed' || s === 'no_show') && detail.appointment_date > today) return false
    return !isDoctor || s === 'completed' || s === 'no_show'
  })

  async function changeStatus(status: AppointmentStatus) {
    setBusy(status); setError(null)
    try { setDetail(await api.changeStatus(id, status, notes || undefined)); setNotes('') } catch (e) { setError(e instanceof Error ? e.message : 'Update failed') } finally { setBusy(null) }
  }

  return (
    <>
      <Link to="/appointments" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink"><ArrowLeft size={15} /> Appointments</Link>
      <PageHeader title={`Appointment #${detail.id}`} description={`${detail.patient_name} · ${detail.department_name}`} actions={<StatusBadge status={detail.status} />} />
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <PredictionPanel appointmentId={id} prediction={prediction} canPredict={hasRole('ADMIN', 'STAFF')} onUpdated={setPrediction} />
          {hasRole('ADMIN', 'STAFF') && ['scheduled', 'confirmed'].includes(detail.status) && <ReminderPanel appointmentId={id} />}
        </div>

        <div className="space-y-6 lg:col-span-2">
          <Card title="Details">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <dt className="text-muted">Patient</dt><dd><Link className="text-brand-strong hover:underline" to={`/patients?open=${detail.patient_id}`}>{detail.patient_name}</Link></dd>
              <dt className="text-muted">Doctor</dt><dd>{detail.doctor_name}</dd>
              <dt className="text-muted">Department</dt><dd>{detail.department_name}</dd>
              <dt className="text-muted">Date</dt><dd className="tabular">{formatDate(detail.appointment_date)}</dd>
              <dt className="text-muted">Time</dt><dd className="tabular">{formatTime(detail.appointment_time)}</dd>
              <dt className="text-muted">Booked on</dt><dd className="tabular">{formatDate(detail.booking_date)}</dd>
            </dl>
          </Card>

          {allowed.length > 0 && (
            <Card title="Update status" subtitle="Every change is written to the audit trail.">
              <Field label="Notes (optional, stored with attendance)"><textarea className="input" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} /></Field>
              <div className="mt-3 flex flex-wrap gap-2">
                {allowed.map((s) => (
                  <button key={s} className={`btn ${s === 'cancelled' || s === 'no_show' ? 'btn-ghost' : 'btn-primary'}`} disabled={!!busy} onClick={() => changeStatus(s)}>
                    {busy === s && <Loader2 size={14} className="animate-spin" />} Mark {statusLabel(s).toLowerCase()}
                  </button>
                ))}
              </div>
              {detail.appointment_date > today && <p className="mt-2 text-xs text-muted">Attendance (completed / no-show) can be recorded from the appointment date onwards.</p>}
            </Card>
          )}

          <Card title="Status history">
            <ol className="relative space-y-3 border-l border-line pl-4">
              {detail.status_history.map((h) => (
                <li key={h.id} className="text-sm">
                  <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-brand" />
                  <p><span className="text-muted">{h.old_status ? statusLabel(h.old_status) : 'Created'} →</span> <span className="font-medium">{statusLabel(h.new_status)}</span></p>
                  <p className="text-xs text-muted">{formatDateTime(h.changed_at)} · {h.changed_by}</p>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>
    </>
  )
}
