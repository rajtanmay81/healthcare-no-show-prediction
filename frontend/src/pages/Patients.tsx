import { Loader2, Pencil, Trash2, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Card, Empty, ErrorNote, Field, Modal, PageHeader, Pagination, RiskBadge, Spinner, StatusBadge, Table } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { api } from '../services/api'
import { ageFrom, formatDate, formatTime, num } from '../services/format'
import type { Patient, PatientInput } from '../types'

const LIMIT = 20

export default function PatientsPage() {
  const { hasRole } = useAuth()
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<Patient | 'new' | null>(null)
  const list = useAsync(() => api.patients(search, LIMIT, offset), [search, offset])
  const openId = params.get('open') ? Number(params.get('open')) : null

  async function remove(p: Patient) {
    if (!window.confirm(`Delete ${p.name}? Patients with appointment history cannot be deleted.`)) return
    try { await api.deletePatient(p.id); list.reload() } catch (e) { window.alert(e instanceof Error ? e.message : 'Delete failed') }
  }

  return (
    <>
      <PageHeader
        title="Patients"
        description="Only scheduling essentials are stored - no clinical records."
        actions={hasRole('ADMIN', 'STAFF') && <button className="btn btn-primary" onClick={() => setEditing('new')}><UserPlus size={16} /> New patient</button>}
      />
      <Card>
        <input className="input mb-4 max-w-sm" placeholder="Search by name, email or phone…" value={search} onChange={(e) => { setOffset(0); setSearch(e.target.value) }} aria-label="Search patients" />
        {list.error && <ErrorNote message={list.error} onRetry={list.reload} />}
        {list.loading && !list.data ? <Spinner /> : list.data?.items.length === 0 ? <Empty>No patients found.</Empty> : list.data && (
          <>
            <Table head={['#', 'Name', 'Age', 'Gender', 'Phone', 'Email', '']}>
              {list.data.items.map((p) => (
                <tr key={p.id} className="hover:bg-surface-2">
                  <td className="tabular px-3 py-2.5 text-muted">{p.id}</td>
                  <td className="px-3 py-2.5"><button className="font-medium text-brand-strong hover:underline" onClick={() => setParams({ open: String(p.id) })}>{p.name}</button></td>
                  <td className="tabular px-3 py-2.5">{ageFrom(p.date_of_birth)}</td>
                  <td className="px-3 py-2.5 capitalize text-ink-2">{p.gender}</td>
                  <td className="tabular px-3 py-2.5 text-ink-2">{p.phone ?? '–'}</td>
                  <td className="px-3 py-2.5 text-ink-2">{p.email ?? '–'}</td>
                  <td className="px-3 py-2.5 text-right">
                    {hasRole('ADMIN', 'STAFF') && <button className="rounded p-1.5 text-muted hover:bg-surface-2 hover:text-ink" onClick={() => setEditing(p)} aria-label={`Edit ${p.name}`}><Pencil size={15} /></button>}
                    {hasRole('ADMIN') && <button className="rounded p-1.5 text-muted hover:bg-surface-2 hover:text-critical-text" onClick={() => remove(p)} aria-label={`Delete ${p.name}`}><Trash2 size={15} /></button>}
                  </td>
                </tr>
              ))}
            </Table>
            <Pagination total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      {editing && <PatientForm patient={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); list.reload() }} />}
      {openId && <PatientDetailModal id={openId} onClose={() => setParams({})} />}
    </>
  )
}

function PatientForm({ patient, onClose, onSaved }: { patient: Patient | null; onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState<PatientInput>({
    name: patient?.name ?? '', date_of_birth: patient?.date_of_birth ?? '', gender: patient?.gender ?? 'undisclosed',
    phone: patient?.phone ?? '', email: patient?.email ?? '',
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (k: keyof PatientInput) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    const payload = { ...form, phone: form.phone || null, email: form.email || null }
    try {
      if (patient) await api.updatePatient(patient.id, payload)
      else await api.createPatient(payload)
      onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : 'Save failed') } finally { setBusy(false) }
  }

  return (
    <Modal title={patient ? 'Edit patient' : 'New patient'} open onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Full name"><input className="input" required minLength={2} value={form.name} onChange={set('name')} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date of birth"><input className="input" type="date" required value={form.date_of_birth} onChange={set('date_of_birth')} /></Field>
          <Field label="Gender">
            <select className="input" value={form.gender} onChange={set('gender')}>
              <option value="female">Female</option><option value="male">Male</option><option value="other">Other</option><option value="undisclosed">Prefer not to say</option>
            </select>
          </Field>
        </div>
        <Field label="Phone"><input className="input" value={form.phone ?? ''} onChange={set('phone')} placeholder="+1 555 0100" /></Field>
        <Field label="Email"><input className="input" type="email" value={form.email ?? ''} onChange={set('email')} /></Field>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy && <Loader2 size={15} className="animate-spin" />} Save</button>
        </div>
      </form>
    </Modal>
  )
}

function PatientDetailModal({ id, onClose }: { id: number; onClose: () => void }) {
  const patient = useAsync(() => api.patient(id), [id])
  const history = useAsync(() => api.appointments({ patient_id: id, limit: 10 }), [id])
  const p = patient.data
  return (
    <Modal title={p?.name ?? 'Patient'} open onClose={onClose}>
      {patient.loading ? <Spinner /> : patient.error ? <ErrorNote message={patient.error} /> : p && (
        <>
          <p className="text-sm text-ink-2">#{p.id} · {ageFrom(p.date_of_birth)} years · born {formatDate(p.date_of_birth)} · <span className="capitalize">{p.gender}</span></p>
          <div className="mt-4 grid grid-cols-5 gap-2 text-center">
            {([['Total', p.stats.total_appointments], ['Completed', p.stats.completed], ['No-shows', p.stats.no_shows], ['Cancelled', p.stats.cancellations], ['Upcoming', p.stats.upcoming]] as const).map(([label, v]) => (
              <div key={label} className="rounded-lg bg-surface-2 p-2"><p className="text-lg font-semibold">{num(v)}</p><p className="text-[11px] text-muted">{label}</p></div>
            ))}
          </div>
          <h4 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wide text-muted">Recent appointments</h4>
          {history.data?.items.length ? (
            <ul className="divide-y divide-[var(--border)] text-sm">
              {history.data.items.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-2 py-2">
                  <Link to={`/appointments/${a.id}`} className="hover:underline">{formatDate(a.appointment_date)} · {formatTime(a.appointment_time)} · {a.department_name}</Link>
                  <span className="flex items-center gap-2"><StatusBadge status={a.status} />{a.latest_prediction && <RiskBadge level={a.latest_prediction.risk_level} />}</span>
                </li>
              ))}
            </ul>
          ) : <Empty>No appointments yet.</Empty>}
        </>
      )}
    </Modal>
  )
}
