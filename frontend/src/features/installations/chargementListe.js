import { useCallback, useEffect, useState } from 'react'

/* Chargement de liste PARTAGÉ des écrans Chantiers (kits, import, suivi GPS,
   approvisionnement) : un seul endroit, jamais recopié écran par écran. */

/** Corps de réponse API -> tableau (liste nue ou enveloppe paginée `results`). */
export function unwrap(res) {
  const p = res?.data
  return Array.isArray(p) ? p : (p?.results ?? [])
}

/** Charge `fetcher(params)` ; relance seulement si les `params` changent (clé JSON). */
export function useFilteredList(fetcher, params) {
  const key = JSON.stringify(params)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    let cancelled = false
    setLoading(true); setError(null)
    fetcher(params)
      .then((res) => { if (!cancelled) setRows(unwrap(res)) })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` encode les filtres : seul son changement relance le chargement (D-ENF22)
  }, [key])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage/changement de filtre (D-ENF22)
  useEffect(() => load(), [load])
  return { rows, loading, error, reload: load }
}
