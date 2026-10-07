import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'

/**
 * Utilisateurs assignables (responsable d'un calepinage) — une seule lecture
 * partagée par l'écran Nouveau et la fiche. `actif` faux ⇒ aucun appel ;
 * `cle` relance la lecture quand le document change. Échec ⇒ liste vide.
 */
export default function useUtilisateursAssignables(actif = true, cle = null) {
  const [responsables, setResponsables] = useState([])
  useEffect(() => {
    if (!actif) return undefined
    let annule = false
    Promise.resolve()
      .then(() => crmApi.getAssignableUsers())
      .then((res) => {
        if (annule) return
        const brut = res?.data
        setResponsables(Array.isArray(brut) ? brut : (brut?.results ?? []))
      })
      .catch(() => { if (!annule) setResponsables([]) })
    return () => { annule = true }
  }, [actif, cle])
  return responsables
}
