import { todayIso } from './format'

export const PERIODS = [
  { key: 'all', label: 'All time', from: undefined },
  { key: '365', label: 'Last 12 months', from: todayIso(-364) },
  { key: '90', label: 'Last 90 days', from: todayIso(-89) },
  { key: '30', label: 'Last 30 days', from: todayIso(-29) },
] as const

export function periodRange(key: string): { date_from?: string; date_to?: string } {
  const from = PERIODS.find((p) => p.key === key)?.from
  return from ? { date_from: from, date_to: todayIso() } : {}
}
