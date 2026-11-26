import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'

/**
 * Utilisateurs assignables (responsable d'un calepinage) — une seule lecture
 * partagée par l'écran Nouveau et la fiche. `actif` faux ⇒ aucun appel ;
 * `cle` relance la lecture quand le document change. Échec ⇒ liste vide.
 */
export default function useUtilisateursAssignables(actif = true, cle = null, leadId = null) {
  const [responsables, setResponsables] = useState([])
  useEffect(() => {
    if (!actif) return undefined
    let annule = false
    Promise.resolve()
      // T4-X3-016 — seulement ceux qui peuvent OUVRIR un calepinage (même droit que le serveur du module).
      // `lead` : le serveur y ajoute un compte qui n'a de visite que sur CE lead (rien ne change sans lead).
      .then(() => crmApi.getAssignableUsers(leadId
        ? { permission: 'calepinage_voir', lead: leadId } : { permission: 'calepinage_voir' }))
      .then((res) => {
        if (annule) return
        const brut = res?.data
        setResponsables(Array.isArray(brut) ? brut : (brut?.results ?? []))
      })
      .catch(() => { if (!annule) setResponsables([]) })
    return () => { annule = true }
  }, [actif, cle, leadId])
  return responsables
}
