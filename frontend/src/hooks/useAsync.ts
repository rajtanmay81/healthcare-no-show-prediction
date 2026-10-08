import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'

export interface AsyncState<T> {
  data: T | undefined
  error: string | null
  loading: boolean
  reload: () => void
}

/** Run an async loader whenever `deps` change; ignores stale responses. */
export function useAsync<T>(loader: () => Promise<T>, deps: DependencyList): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const callId = useRef(0)

  useEffect(() => {
    const id = ++callId.current
    setLoading(true)
    setError(null)
    loader()
      .then((result) => { if (id === callId.current) setData(result) })
      .catch((err: unknown) => { if (id === callId.current) setError(err instanceof Error ? err.message : String(err)) })
      .finally(() => { if (id === callId.current) setLoading(false) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}
