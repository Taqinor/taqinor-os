import { useEffect, useState } from 'react'
import parametresApi from '../../api/parametresApi'
import { applyStatutConfig } from '../installations/statuses'
import { applyTicketStatutConfig } from '../sav/ticketStatuses'

// APAR54 — applique aux écrans chantier et SAV les libellés réglés dans
// Paramètres › Statuts (N58). Couche d'AFFICHAGE seulement : clés canoniques
// et machine à états intactes. Lit `getStatutsEffective(domaine)` puis appelle
// la fonction d'application du domaine ; sans réglage (ou erreur réseau) les
// libellés par défaut restent en place. Retourne un compteur de version : le
// changer force le re-rendu de l'écran qui monte le hook (les tables de
// libellés sont des variables de module, hors état React).
const APPLIERS = {
  chantier: applyStatutConfig,
  sav: applyTicketStatutConfig,
}

export default function useStatutConfig(domaine) {
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const apply = APPLIERS[domaine]
    if (!apply) return undefined
    let active = true
    parametresApi.getStatutsEffective(domaine)
      .then((res) => {
        if (!active) return
        apply(res?.data?.results ?? [])
        setVersion((v) => v + 1)
      })
      .catch(() => {
        // Libellés par défaut conservés : écran utilisable sans la config.
        if (active) apply(null)
      })
    return () => { active = false }
  }, [domaine])

  return version
}
