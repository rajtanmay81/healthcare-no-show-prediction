import { Loader2, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Card, Empty, ErrorNote, Field, Modal, PageHeader, Spinner, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { api } from '../services/api'
import { formatTime, todayIso } from '../services/format'
import type { Doctor } from '../types'

export default function DoctorsPage() {
  const { hasRole } = useAuth()
  const [departmentId, setDepartmentId] = useState<number | ''>('')
  const [search, setSearch] = useState('')
  const [creating, setCreating] = useState(false)
  const [scheduleFor, setScheduleFor] = useState<Doctor | null>(null)
  const departments = useAsync(() => api.departments(), [])
  const doctors = useAsync(() => api.doctors({ department_id: departmentId, search }), [departmentId, search])

  return (
    <>
      <PageHeader title="Doctors" description="Clinicians and their daily slot availability." actions={hasRole('ADMIN') && <button className="btn btn-primary" onClick={() => setCreating(true)}><Plus size={16} /> New doctor</button>} />
      <Card>
        <div className="mb-4 flex flex-wrap gap-3">
          <input className="input max-w-xs" placeholder="Search doctors…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search doctors" />
          <select className="input max-w-xs" value={departmentId} onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : '')} aria-label="Department">
            <option value="">All departments</option>
            {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        {doctors.error && <ErrorNote message={doctors.error} onRetry={doctors.reload} />}
        {doctors.loading && !doctors.data ? <Spinner /> : doctors.data?.items.length === 0 ? <Empty>No doctors found.</Empty> : (
          <Table head={['Name', 'Department', 'Specialization', 'Email', 'Phone', '']}>
            {doctors.data?.items.map((d) => (
              <tr key={d.id} className="hover:bg-surface-2">
                <td className="px-3 py-2.5 font-medium">{d.name}</td>
                <td className="px-3 py-2.5">{d.department_name}</td>
                <td className="px-3 py-2.5 text-ink-2">{d.specialization ?? '–'}</td>
                <td className="px-3 py-2.5 text-ink-2">{d.email}</td>
                <td className="tabular px-3 py-2.5 text-ink-2">{d.phone ?? '–'}</td>
                <td className="px-3 py-2.5 text-right"><button className="btn btn-ghost py-1 text-xs" onClick={() => setScheduleFor(d)}>Schedule</button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {creating && <DoctorForm onClose={() => setCreating(false)} onSaved={() => { setCreating(false); doctors.reload() }} />}
      {scheduleFor && <ScheduleModal doctor={scheduleFor} onClose={() => setScheduleFor(null)} />}
    </>
  )
}

function DoctorForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const departments = useAsync(() => api.departments(), [])
  const [form, setForm] = useState({ name: '', department_id: '', specialization: '', email: '', phone: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api.createDoctor({ name: form.name, department_id: Number(form.department_id), specialization: form.specialization || null, email: form.email, phone: form.phone || null })
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Save failed') } finally { setBusy(false) }
  }
  return (
    <Modal title="New doctor" open onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Full name"><input className="input" required minLength={2} value={form.name} onChange={set('name')} placeholder="Dr. …" /></Field>
        <Field label="Department">
          <select className="input" required value={form.department_id} onChange={set('department_id')}>
            <option value="">Select…</option>
            {departments.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Specialization"><input className="input" value={form.specialization} onChange={set('specialization')} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Email"><input className="input" type="email" required value={form.email} onChange={set('email')} /></Field>
          <Field label="Phone"><input className="input" value={form.phone} onChange={set('phone')} /></Field>
        </div>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy && <Loader2 size={15} className="animate-spin" />} Save</button>
        </div>
      </form>
    </Modal>
  )
}

function ScheduleModal({ doctor, onClose }: { doctor: Doctor; onClose: () => void }) {
  const [date, setDate] = useState(todayIso())
  const schedule = useAsync(() => api.doctorSchedule(doctor.id, date), [doctor.id, date])
  const booked = schedule.data?.slots.filter((s) => !s.available).length ?? 0
  return (
    <Modal title={`${doctor.name} · schedule`} open onClose={onClose}>
      <input className="input mb-3" type="date" value={date} onChange={(e) => setDate(e.target.value)} aria-label="Date" />
      {schedule.loading ? <Spinner /> : schedule.error ? <ErrorNote message={schedule.error} /> : (
        <>
          <p className="mb-3 text-sm text-ink-2">{booked} of {schedule.data?.slots.length} slots booked</p>
          <div className="grid grid-cols-4 gap-2">
            {schedule.data?.slots.map((s) => (
              <div key={s.time} className={`tabular rounded-md border px-2 py-1.5 text-center text-xs ${s.available ? 'border-line text-ink-2' : 'border-brand bg-brand-soft font-medium text-brand-strong'}`}>
                {formatTime(s.time)}<br /><span className="text-[10px]">{s.available ? 'Free' : `Appt #${s.appointment_id}`}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </Modal>
  )
}
