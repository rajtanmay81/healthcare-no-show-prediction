import { CalendarPlus, Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Empty, ErrorNote, Field, Modal, PageHeader, Pagination, RiskBadge, Spinner, StatusBadge, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { api, type AppointmentFilters } from '../services/api'
import { formatDate, formatTime, statusLabel, todayIso } from '../services/format'
import type { AppointmentStatus, Patient } from '../types'

const STATUSES: AppointmentStatus[] = ['scheduled', 'confirmed', 'completed', 'cancelled', 'no_show']
const LIMIT = 25

export default function AppointmentsPage() {
  const navigate = useNavigate()
  const { hasRole } = useAuth()
  const [filters, setFilters] = useState<AppointmentFilters>({ sort: 'newest' })
  const [offset, setOffset] = useState(0)
  const [booking, setBooking] = useState(false)
  const departments = useAsync(() => api.departments(), [])
  const list = useAsync(() => api.appointments({ ...filters, limit: LIMIT, offset }), [JSON.stringify(filters), offset])

  const update = (patch: Partial<AppointmentFilters>) => { setOffset(0); setFilters((f) => ({ ...f, ...patch })) }

  return (
    <>
      <PageHeader
        title="Appointments"
        description="Book, reschedule and track attendance. New bookings are scored by the no-show model automatically."
        actions={hasRole('ADMIN', 'STAFF') && <button className="btn btn-primary" onClick={() => setBooking(true)}><CalendarPlus size={16} /> Book appointment</button>}
      />
      <Card>
        <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <input className="input lg:col-span-2" placeholder="Search patient name…" value={filters.search ?? ''} onChange={(e) => update({ search: e.target.value })} aria-label="Search patient" />
          <select className="input" value={filters.status ?? ''} onChange={(e) => update({ status: e.target.value as AppointmentStatus | '' })} aria-label="Status">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
          </select>
          <select className="input" value={filters.department_id ?? ''} onChange={(e) => update({ department_id: e.target.value ? Number(e.target.value) : '' })} aria-label="Department">
            <option value="">All departments</option>
            {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <input className="input" type="date" value={filters.date_from ?? ''} onChange={(e) => update({ date_from: e.target.value || undefined })} aria-label="From date" />
          <input className="input" type="date" value={filters.date_to ?? ''} onChange={(e) => update({ date_to: e.target.value || undefined })} aria-label="To date" />
        </div>
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          <button className="btn btn-ghost py-1 text-xs" onClick={() => update({ date_from: todayIso(), date_to: todayIso(14), sort: 'oldest', status: '' })}>Next 14 days</button>
          <button className="btn btn-ghost py-1 text-xs" onClick={() => update({ date_from: todayIso(), date_to: todayIso(), sort: 'oldest' })}>Today</button>
          <button className="btn btn-ghost py-1 text-xs" onClick={() => { setOffset(0); setFilters({ sort: 'newest' }) }}>Clear filters</button>
        </div>

        {list.error && <ErrorNote message={list.error} onRetry={list.reload} />}
        {list.loading && !list.data ? <Spinner /> : list.data && list.data.items.length === 0 ? <Empty>No appointments match these filters.</Empty> : list.data && (
          <>
            <Table head={['#', 'Patient', 'Department / doctor', 'Date & time', 'Status', 'No-show risk']}>
              {list.data.items.map((a) => (
                <tr key={a.id} className="cursor-pointer hover:bg-surface-2" onClick={() => navigate(`/appointments/${a.id}`)}>
                  <td className="tabular px-3 py-2.5 text-muted">{a.id}</td>
                  <td className="px-3 py-2.5 font-medium">{a.patient_name}</td>
                  <td className="px-3 py-2.5"><p>{a.department_name}</p><p className="text-xs text-muted">{a.doctor_name}</p></td>
                  <td className="tabular whitespace-nowrap px-3 py-2.5 text-ink-2">{formatDate(a.appointment_date)} · {formatTime(a.appointment_time)}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={a.status} /></td>
                  <td className="px-3 py-2.5">{a.latest_prediction ? <RiskBadge level={a.latest_prediction.risk_level} probability={a.latest_prediction.no_show_probability} /> : <span className="text-xs text-muted">Not scored</span>}</td>
                </tr>
              ))}
            </Table>
            <Pagination total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      <BookingModal open={booking} onClose={() => setBooking(false)} onBooked={(id) => navigate(`/appointments/${id}`)} />
    </>
  )
}

function BookingModal({ open, onClose, onBooked }: { open: boolean; onClose: () => void; onBooked: (id: number) => void }) {
  const [patientQuery, setPatientQuery] = useState('')
  const [patient, setPatient] = useState<Patient | null>(null)
  const [departmentId, setDepartmentId] = useState<number | ''>('')
  const [doctorId, setDoctorId] = useState<number | ''>('')
  const [date, setDate] = useState(todayIso(1))
  const [time, setTime] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [now] = useState(() => new Date())

  const departments = useAsync(() => api.departments(), [])
  const patients = useAsync(() => (patientQuery.length >= 2 ? api.patients(patientQuery, 6) : Promise.resolve(null)), [patientQuery])
  const doctors = useAsync(() => (departmentId ? api.doctors({ department_id: departmentId }) : Promise.resolve(null)), [departmentId])
  const schedule = useAsync(() => (doctorId && date ? api.doctorSchedule(doctorId, date) : Promise.resolve(null)), [doctorId, date])

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!patient || !doctorId || !time) return
    setBusy(true)
    setError(null)
    try {
      const appt = await api.bookAppointment({ patient_id: patient.id, doctor_id: doctorId, appointment_date: date, appointment_time: time })
      onBooked(appt.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Booking failed')
    } finally {
      setBusy(false)
    }
  }

  const isPast = (slot: string) => date === todayIso() && slot.slice(0, 5) <= `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`

  return (
    <Modal title="Book appointment" open={open} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Patient">
          {patient ? (
            <div className="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-sm">
              <span><span className="font-medium">{patient.name}</span> <span className="text-muted">· #{patient.id} · DOB {formatDate(patient.date_of_birth)}</span></span>
              <button type="button" className="text-xs text-brand-strong" onClick={() => setPatient(null)}>Change</button>
            </div>
          ) : (
            <>
              <input className="input" placeholder="Type at least 2 letters of the name…" value={patientQuery} onChange={(e) => setPatientQuery(e.target.value)} />
              {patients.data && (
                <ul className="mt-1 max-h-40 overflow-y-auto rounded-lg border border-line">
                  {patients.data.items.length === 0 && <li className="px-3 py-2 text-sm text-muted">No patients found</li>}
                  {patients.data.items.map((p) => (
                    <li key={p.id}><button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-surface-2" onClick={() => setPatient(p)}>{p.name} <span className="text-muted">· #{p.id} · {formatDate(p.date_of_birth)}</span></button></li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Department">
            <select className="input" required value={departmentId} onChange={(e) => { setDepartmentId(e.target.value ? Number(e.target.value) : ''); setDoctorId(''); setTime('') }}>
              <option value="">Select…</option>
              {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Doctor">
            <select className="input" required value={doctorId} disabled={!departmentId} onChange={(e) => { setDoctorId(e.target.value ? Number(e.target.value) : ''); setTime('') }}>
              <option value="">Select…</option>
              {doctors.data?.items.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Date"><input className="input" type="date" min={todayIso()} required value={date} onChange={(e) => { setDate(e.target.value); setTime('') }} /></Field>
        {doctorId !== '' && (
          <Field label="Available slots">
            {schedule.loading ? <Spinner label="Loading schedule…" /> : (
              <div className="grid grid-cols-4 gap-2">
                {schedule.data?.slots.map((s) => {
                  const disabled = !s.available || isPast(s.time)
                  const selected = time === s.time.slice(0, 5)
                  return (
                    <button key={s.time} type="button" disabled={disabled} onClick={() => setTime(s.time.slice(0, 5))}
                      className={`tabular rounded-md border px-2 py-1.5 text-xs ${selected ? 'border-brand bg-brand text-white' : disabled ? 'border-line text-muted line-through opacity-60' : 'border-line hover:border-brand'}`}>
                      {formatTime(s.time)}
                    </button>
                  )
                })}
              </div>
            )}
          </Field>
        )}
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !patient || !doctorId || !time}>{busy && <Loader2 size={15} className="animate-spin" />} Book & predict</button>
        </div>
      </form>
    </Modal>
  )
}
