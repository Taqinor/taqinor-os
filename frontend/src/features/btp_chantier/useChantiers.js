import { useEffect, useState } from 'react'
import installationsApi from '../../api/installationsApi'

/* ============================================================================
   PACT62 — Liste des chantiers (`installations.Installation`), partagée par
   TOUS les écrans BTP/Chantier (réserves, RFI, visas, journal, avenants, DGD,
   diffusion de plans) : un seul chargement, jamais réinventé écran par écran.
   Cross-app en LECTURE (frontend → API `installations`), pas une frontière
   backend : les écrans du vertical BTP réfèrent au chantier comme le fait
   déjà `apps/btp_chantier/models.py` (FK réelle vers `installations.
   Installation`).
   ========================================================================== */

export function useChantiers() {
  const [chantiers, setChantiers] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    installationsApi.getInstallations()
      .then((res) => {
        if (cancelled) return
        const payload = res?.data
        const rows = Array.isArray(payload)
          ? payload
          : Array.isArray(payload?.results) ? payload.results : []
        setChantiers(rows)
      })
      .catch(() => { if (!cancelled) setChantiers([]) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return { chantiers, loading }
}

// Libellé lisible d'un chantier — jamais un champ inventé : `client_nom`/
// `site_ville` viennent tels quels d'`InstallationSerializer`.
export function chantierLabel(chantier) {
  if (!chantier) return ''
  const nom = chantier.client_nom || 'Chantier'
  return chantier.site_ville
    ? `${nom} — #${chantier.id} · ${chantier.site_ville}`
    : `${nom} — #${chantier.id}`
}

export default useChantiers
