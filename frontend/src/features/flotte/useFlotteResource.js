import { useCallback, useEffect, useState } from 'react'

/* ============================================================================
   FLOTTE — petit hook de chargement de liste (sans react-query).
   ----------------------------------------------------------------------------
   Charge un jeu de données via une fonction `fetcher(params)` renvoyant une
   promesse axios, gère `data/loading/error` et un `reload()`. Les listes DRF
   renvoient soit un tableau brut, soit `{results:[…]}` (pagination) — on
   normalise vers un tableau. `params` est stabilisé par sérialisation JSON pour
   éviter les rechargements en boucle.
   ========================================================================== */

export function useFlotteResource(fetcher, params = null, deps = []) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Clés stables (chaînes) : la sérialisation évite de recréer `load` à chaque
  // rendu à cause d'un nouvel objet `params`/tableau `deps`.
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
    // Ne se recrée que si les filtres (paramsKey) ou les deps explicites changent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, depsKey])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  return { data, loading, error, reload: load, setData }
}

export default useFlotteResource
