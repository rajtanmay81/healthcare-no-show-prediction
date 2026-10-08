import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { ErrorNote, Field } from '../components/ui'
import { useAuth } from '../hooks/useAuth'

export default function LoginPage() {
  const { user, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try { await login(email, password) } catch (err) { setError(err instanceof Error ? err.message : 'Login failed') } finally { setBusy(false) }
  }

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand text-2xl font-bold text-white">+</div>
          <h1 className="text-xl font-semibold">CareSight</h1>
          <p className="mt-1 text-sm text-ink-2">Appointment no-show prediction for hospital teams</p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-surface p-6">
          <Field label="Email"><input className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Field label="Password"><input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
          {error && <ErrorNote message={error} />}
          <button className="btn btn-primary w-full justify-center" disabled={busy}>{busy && <Loader2 size={15} className="animate-spin" />} Sign in</button>
          <p className="text-center text-xs text-muted">Accounts are created by the seed script from your .env settings.</p>
        </form>
      </div>
    </div>
  )
}
