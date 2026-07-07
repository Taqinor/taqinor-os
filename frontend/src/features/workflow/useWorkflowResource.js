import { useCallback, useEffect, useState } from 'react'

/* ============================================================================
   XPLT8 — petit hook de chargement (même pattern que
   `features/flotte/useFlotteResource.js`, dupliqué localement pour garder le
   module `workflow` file-disjoint des autres lanes en cours).
   ----------------------------------------------------------------------------
   Charge un jeu de données via `fetcher()` renvoyant une promesse axios, gère
   `data/loading/error` et un `reload()`. Normalise les réponses tableau brut
   OU `{results:[…]}` (pagination DRF) vers un tableau — ne lève jamais sur une
   forme de réponse inattendue.
   ========================================================================== */
export function useWorkflowResource(fetcher, deps = []) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const depsKey = deps.length ? deps.join('|') : ''

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetcher()
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
  }, [depsKey])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  return { data, loading, error, reload: load, setData }
}

export default useWorkflowResource
