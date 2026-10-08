import { PERIODS } from '../services/periods'

export function PeriodFilter({ value, onChange }: { value: string; onChange: (key: string) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface p-0.5" role="group" aria-label="Period">
      {PERIODS.map((p) => (
        <button key={p.key} onClick={() => onChange(p.key)} className={`rounded-md px-3 py-1.5 text-xs font-medium ${value === p.key ? 'bg-brand text-white' : 'text-ink-2 hover:bg-surface-2'}`}>
          {p.label}
        </button>
      ))}
    </div>
  )
}
