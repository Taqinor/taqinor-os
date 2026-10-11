// Briques communes aux sections du suivi SAV (abonnements, SLA, certificats) :
// lecture de toutes les pages d'une liste, chargement/rechargement et
// libellé d'un système.
import { useEffect, useState } from 'react'
import { fetchAllPages } from '../../../utils/fetchAllPages'

// `lire` = méthode de monitoringApi prenant { page, page_size }.
export const lireToutesLesPages = (lire) => fetchAllPages(
  (page) => lire({ page, page_size: 200 }).then((r) => r.data),
).then((res) => (Array.isArray(res) ? res : (res?.results ?? [])))

export function useListeServeur(lire) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    lireToutesLesPages(lire).then(setRows).catch(() => setRows([])).finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
  useEffect(() => { load() }, [])

  return { rows, loading, load }
}

export const libelleSysteme = (systems, installationId) => systems
  .find((s) => s.installation === installationId)?.label ?? `Système #${installationId}`

