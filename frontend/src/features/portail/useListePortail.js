// ENF28 (ENF19) — chargement partagé des listes des portails fournisseur et
// partenaire (« Mes bons de commande », « Mes soumissions ») : un seul
// exemplaire au lieu de deux copies. Ces deux points d'accès rendent la liste
// COMPLÈTE dans `results` (aucune pagination serveur, aucun `?page=` déclaré).
import { useCallback, useEffect, useState } from 'react'

/** `liste(params)` = appel API stable d'UNE page ; `charger()` recharge tout. */
export function useListePortail(liste) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  const charger = useCallback(() => {
    setLoading(true)
    return liste()
      .then((r) => (Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
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
