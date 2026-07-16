import { useCallback, useEffect, useState } from 'react'

/* ============================================================================
   AGRICULTURE — petit hook de chargement de liste (même patron que
   `features/flotte/useFlotteResource.js`, sans react-query).
   ========================================================================== */

export function useAgricultureResource(fetcher, params = null, deps = []) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const paramsKey = params ? JSON.stringify(params) : ''
  const depsKey = deps.length ? deps.join('|') : ''

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetcher(params || undefined)
      .then((res) => {
        if (cancelled) return
        const payload = res?.data
        const rows = Array.isArray(payload)
          ? payload
          : Array.isArray(payload?.results)
            ? payload.results
            : payload ?? []
        setData(rows)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, depsKey])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  return { data, loading, error, reload: load, setData }
}

export default useAgricultureResource
