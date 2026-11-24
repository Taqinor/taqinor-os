import { useEffect, useMemo, useState } from 'react'
import crmApi from '../../../api/crmApi'

/**
 * useDeepLinkedLead — résout le lead du lien profond `?lead=<id>`.
 *
 * D'abord dans la liste CHARGÉE (cas courant, aucune requête). Incident
 * 02/10/2026 — un lead ARCHIVÉ n'est pas dans la liste par défaut
 * (« Actifs ») : le lien (recherche ⌘K, récents, ventes) n'ouvrait alors
 * RIEN et le lead semblait disparu. Repli : on charge la fiche elle-même
 * (le serveur sert un lead archivé en détail) ; la fiche montre « Archivé »
 * et propose « ⋯ → Restaurer ».
 */
// eslint-disable-next-line no-unused-vars -- `leadsLoading` reste dans la signature des appelants (T4-U3-014 : plus lu)
export default function useDeepLinkedLead(wantedLeadId, leads, leadsLoading) {
  const inList = useMemo(() => {
    if (!wantedLeadId) return null
    return (leads ?? []).find((l) => String(l.id) === String(wantedLeadId)) ?? null
  }, [wantedLeadId, leads])

  const [fetched, setFetched] = useState(null)
  const fetchedMatches = !!(wantedLeadId && fetched && String(fetched.id) === String(wantedLeadId))

  // T4-U3-014 — la fiche n'attend plus la liste (`leadsLoading` n'arrête plus la lecture) : une liste lente ou en
  // échec ne bloque jamais le lead demandé par son lien. Dès que la liste le contient, c'est elle qui sert.
  useEffect(() => {
    if (!wantedLeadId || inList || fetchedMatches) return undefined
    let vivant = true
    crmApi.getLead(wantedLeadId)
      .then((r) => { if (vivant && r?.data?.id != null) setFetched(r.data) })
      .catch(() => {})
    return () => { vivant = false }
  }, [wantedLeadId, inList, fetchedMatches])

  return inList ?? (fetchedMatches ? fetched : null)
}
