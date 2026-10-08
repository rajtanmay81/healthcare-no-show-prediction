import { useEffect, useState } from 'react'

const TOKENS = ['--series-1', '--series-2', '--grid', '--axis', '--ink', '--ink-2', '--ink-muted', '--chart-surface', '--surface', '--border', '--good', '--warning', '--critical'] as const
export type ChartColors = Record<(typeof TOKENS)[number], string>

function read(): ChartColors {
  const style = getComputedStyle(document.documentElement)
  return Object.fromEntries(TOKENS.map((t) => [t, style.getPropertyValue(t).trim()])) as ChartColors
}

/** SVG attributes cannot use CSS variables reliably, so resolve tokens and re-read on theme change. */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(read)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setColors(read())
    mq.addEventListener('change', update)
    const observer = new MutationObserver(update)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => { mq.removeEventListener('change', update); observer.disconnect() }
  }, [])
  return colors
}
