// ENF28 (ENF19) — chargement partagé des tableaux de bord des portails
// fournisseur et partenaire (même résumé serveur scopé au compte connecté).
// Un seul exemplaire au lieu de deux copies ; l'affichage d'attente/erreur
// vit dans EtatTableauDeBordExterne.jsx.
import { useEffect, useState } from 'react'

/** Charge le résumé une fois au montage ; `charger` = appel API stable. */
export function useTableauDeBordExterne(charger) {
  const [resume, setResume] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    let annule = false
    charger()
      .then((r) => { if (!annule) setResume(r.data) })
      .catch(() => { if (!annule) setErreur(true) })
      .finally(() => { if (!annule) setLoading(false) })
    return () => { annule = true }
  }, [charger])

  return { resume, loading, erreur }
}
