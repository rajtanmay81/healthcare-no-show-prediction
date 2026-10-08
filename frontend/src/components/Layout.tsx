import { Activity, BarChart3, Bot, Building2, CalendarDays, LayoutDashboard, LogOut, Menu, Stethoscope, Users, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import type { Role } from '../types'

const NAV: { to: string; label: string; icon: typeof LayoutDashboard; roles?: Role[] }[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/doctors', label: 'Doctors', icon: Stethoscope },
  { to: '/departments', label: 'Departments', icon: Building2 },
  { to: '/predictions', label: 'Predictions', icon: Activity },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/assistant', label: 'AI Assistant', icon: Bot, roles: ['ADMIN', 'STAFF'] },
]

export function Layout() {
  const { user, logout, hasRole } = useAuth()
  const [open, setOpen] = useState(false)
  const items = NAV.filter((n) => !n.roles || hasRole(...n.roles))

  const nav = (
    <nav className="flex flex-col gap-0.5">
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-brand-soft text-brand-strong' : 'text-ink-2 hover:bg-surface-2 hover:text-ink'}`
          }
        >
          <Icon size={17} /> {label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex min-h-full">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-surface p-4 transition-transform lg:static lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="mb-6 flex items-center justify-between px-2">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-lg font-bold text-white">+</div>
            <div>
              <p className="text-sm font-semibold leading-tight">CareSight</p>
              <p className="text-[11px] text-muted">No-show prediction</p>
            </div>
          </div>
          <button className="lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        {nav}
        <div className="mt-auto rounded-lg border border-line p-3">
          <p className="truncate text-sm font-medium">{user?.full_name}</p>
          <p className="truncate text-xs text-muted">{user?.email}</p>
          <div className="mt-2 flex items-center justify-between">
            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] font-semibold text-ink-2">{user?.role}</span>
            <button onClick={logout} className="inline-flex items-center gap-1 text-xs text-ink-2 hover:text-ink"><LogOut size={13} /> Sign out</button>
          </div>
        </div>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3 lg:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open menu"><Menu size={20} /></button>
          <span className="font-semibold">CareSight</span>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
        <footer className="px-8 pb-6 text-center text-[11px] text-muted">Demo system · all patient data is synthetic · model outputs are risk estimates, not reasons.</footer>
      </div>
    </div>
  )
}
