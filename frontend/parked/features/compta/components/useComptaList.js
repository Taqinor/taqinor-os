import { useCallback, useEffect, useState } from 'react'
import { toast } from '../../../ui'

/* ============================================================================
   Hook de liste réutilisable (module Comptabilité).
   ----------------------------------------------------------------------------
   Charge une ressource paginée/non paginée via un appel `fetcher(params)` et
   expose { rows, loading, error, reload }. Gère DRF paginé ({results}) ou liste
   brute. Aucune dépendance react-query (contrainte du module) : useState/useEffect.
   ========================================================================== */

export function unwrap(res) {
  const data = res?.data
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

export default function useComptaList(fetcher, params) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // Sérialise les params pour une dépendance stable.
  const key = JSON.stringify(params || {})

  const reload = useCallback(() => {
    let alive = true
    setLoading(true)
    setError(null)
    fetcher(params)
      .then((res) => { if (alive) setRows(unwrap(res)) })
      .catch(() => {
        if (!alive) return
        setError('Chargement impossible.')
        toast.error('Chargement impossible — réessayez.')
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher, key])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => reload(), [reload])

  return { rows, loading, error, reload }
}
