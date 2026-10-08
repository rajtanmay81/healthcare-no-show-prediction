export const pct = (v: number | null | undefined, digits = 1) => (v === null || v === undefined ? '–' : `${(v * 100).toFixed(digits)}%`)
export const num = (v: number | null | undefined) => (v === null || v === undefined ? '–' : v.toLocaleString())

export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
export function formatTime(t: string): string {
  const [h, m] = t.split(':').map(Number)
  return new Date(2000, 0, 1, h, m).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}
export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}
export function todayIso(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
export function ageFrom(dob: string): number {
  const b = new Date(dob)
  const now = new Date()
  let age = now.getFullYear() - b.getFullYear()
  if (now.getMonth() < b.getMonth() || (now.getMonth() === b.getMonth() && now.getDate() < b.getDate())) age -= 1
  return age
}
export const statusLabel = (s: string) => (s === 'no_show' ? 'No-show' : s.charAt(0).toUpperCase() + s.slice(1))

/** Round percentage axis ticks (0.05 / 0.1 steps) covering `max`, for 0..1 rate axes. */
export function rateTicks(max: number): number[] {
  const step = max > 0.5 ? 0.2 : max > 0.2 ? 0.1 : 0.05
  const top = Math.max(step, Math.ceil((max + 1e-9) / step) * step)
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => Number((i * step).toFixed(2)))
}
