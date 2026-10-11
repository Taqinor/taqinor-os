// ENF28 (ENF19) — chargement d'un rapport en lecture seule au montage :
// `charger` = appel API stable ; l'état n'est plus posé après démontage.
import { useEffect, useState } from 'react'

export function useChargementRapport(charger) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let active = true
    charger()
      .then((r) => { if (active) { setData(r.data); setError(false) } })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [charger])

  return { data, loading, error }
}
