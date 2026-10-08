import { Loader2, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Card, ErrorNote, Field, Modal, PageHeader, Spinner } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { api } from '../services/api'
import { num, pct } from '../services/format'

export default function DepartmentsPage() {
  const { hasRole } = useAuth()
  const [creating, setCreating] = useState(false)
  const departments = useAsync(() => api.departments(), [])
  const stats = useAsync(() => api.departmentStats(), [])
  const byId = new Map(stats.data?.map((s) => [s.department_id, s]))

  return (
    <>
      <PageHeader title="Departments" description="Clinical departments with all-time attendance figures." actions={hasRole('ADMIN') && <button className="btn btn-primary" onClick={() => setCreating(true)}><Plus size={16} /> New department</button>} />
      {departments.error && <ErrorNote message={departments.error} onRetry={departments.reload} />}
      {departments.loading ? <Spinner /> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {departments.data?.map((d) => {
            const s = byId.get(d.id)
            return (
              <Card key={d.id} title={d.name} subtitle={d.description ?? undefined}>
                <dl className="grid grid-cols-2 gap-y-2 text-sm">
                  <dt className="text-muted">Doctors</dt><dd className="tabular text-right font-medium">{d.doctor_count}</dd>
                  <dt className="text-muted">Appointments</dt><dd className="tabular text-right font-medium">{num(s?.total_appointments)}</dd>
                  <dt className="text-muted">No-show rate</dt><dd className="tabular text-right font-medium">{pct(s?.no_show_rate)}</dd>
                  <dt className="text-muted">Upcoming</dt><dd className="tabular text-right font-medium">{num(s?.upcoming)}</dd>
                  <dt className="text-muted">High-risk upcoming</dt><dd className="tabular text-right font-medium text-critical-text">{num(s?.high_risk_upcoming)}</dd>
                </dl>
              </Card>
            )
          })}
        </div>
      )}
      {creating && <DepartmentForm onClose={() => setCreating(false)} onSaved={() => { setCreating(false); departments.reload(); stats.reload() }} />}
    </>
  )
}

function DepartmentForm({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try { await api.createDepartment({ name, description: description || undefined }); onSaved() } catch (err) { setError(err instanceof Error ? err.message : 'Save failed') } finally { setBusy(false) }
  }
  return (
    <Modal title="New department" open onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Name"><input className="input" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Description"><textarea className="input" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
        {error && <ErrorNote message={error} />}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy && <Loader2 size={15} className="animate-spin" />} Save</button>
        </div>
      </form>
    </Modal>
  )
}
