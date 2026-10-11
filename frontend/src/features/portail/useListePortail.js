// ENF28 (ENF19) — chargement partagé des listes des portails fournisseur et
// partenaire (« Mes bons de commande », « Mes soumissions ») : un seul
// exemplaire au lieu de deux copies. Toutes les pages de l'enveloppe DRF sont
// lues (ADOC32), jamais la seule page 1.
import { useCallback, useEffect, useState } from 'react'
import { chargerToutesLesPages } from './admin/chargerToutesLesPages'

/** `liste(params)` = appel API stable d'UNE page ; `charger()` recharge tout. */
export function useListePortail(liste) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  const charger = useCallback(() => {
    setLoading(true)
    return chargerToutesLesPages((page) => liste({ page }))
      .then((lignes) => {
        setRows(lignes)
        setErreur(false)
      })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }, [liste])

  useEffect(() => {
    // Différé d'un microtask : `charger` pose l'état de chargement de façon
    // synchrone (react-hooks/set-state-in-effect).
    Promise.resolve().then(charger)
  }, [charger])

  return { rows, loading, erreur, charger }
}
