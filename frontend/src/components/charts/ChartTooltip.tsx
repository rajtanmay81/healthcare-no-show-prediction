import type { ReactNode } from 'react'

export function TooltipBox({ title, rows }: { title: ReactNode; rows: { label: string; value: ReactNode }[] }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-ink">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex justify-between gap-4 text-ink-2">
          <span>{r.label}</span>
          <span className="tabular font-medium text-ink">{r.value}</span>
        </p>
      ))}
    </div>
  )
}
