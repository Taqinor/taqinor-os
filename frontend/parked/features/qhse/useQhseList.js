import { useCallback, useEffect, useRef, useState } from 'react'

/* ============================================================================
   UX29–UX33 — Petit hook de chargement de liste QHSE (useState + useEffect).
   Pas de react-query (règle de lane) : on appelle une fonction `fetcher` qui
   renvoie une promesse axios, on normalise la réponse DRF (tableau simple OU
   `{results:[…]}` paginé), et on expose { rows, loading, error, reload }.
   ========================================================================== */

/** Extrait un tableau de lignes d'une réponse axios DRF (list ou paginée). */
export function rowsFrom(res) {
  const data = res?.data
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data?.evenements)) return data.evenements
  if (Array.isArray(data?.items)) return data.items
  return []
}

export function useQhseList(fetcher, deps = []) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Le fetcher est recréé à chaque rendu (fermeture sur des filtres) ; on
  // resynchronise via une clé sérialisée des `deps` déclarées par l'appelant.
  const depsKey = JSON.stringify(deps)
  const fetcherRef = useRef(fetcher)

  // Garde la dernière fonction de chargement sans la lire pendant le rendu.
  useEffect(() => { fetcherRef.current = fetcher })

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetcherRef.current()
      setRows(rowsFrom(res))
    } catch (err) {
      setError(
        err?.response?.data?.detail
          ?? 'Chargement impossible — vérifiez votre connexion puis réessayez.',
      )
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(() => { load() }, [load, depsKey])

  return { rows, loading, error, reload: load }
}

export default useQhseList
