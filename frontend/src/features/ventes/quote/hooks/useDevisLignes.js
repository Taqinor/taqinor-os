// QJR90 — `useDevisLignes` : POSSÈDE les lignes du devis, le verrou
// `prixManuel`, la résolution de tarif (`refreshTarif`) et la suggestion de
// TVA — les quatre responsabilités aujourd'hui éparpillées dans
// `DevisGenerator.jsx` (`:1981-2073`).
//
// Patron maison : toute la logique est dans `useDevisLignesPur.js` (testée
// sous `node --test`) ; ce fichier ne fait que tenir l'état et l'appel réseau.
//
// Hook AJOUTÉ TESTÉ (via sa moitié pure), IMPORTÉ PAR PERSONNE (vague M4).
import { useCallback, useState } from 'react'
import ventesApi from '../../../../api/ventesApi'
import {
  ecrireChamp, changerProduit, appliquerTarif, suggestionTva, lignesUtilisables,
} from './useDevisLignesPur'

export {
  ecrireChamp, changerProduit, appliquerTarif, suggestionTva, lignesUtilisables,
} from './useDevisLignesPur'

export function useDevisLignes(lignesInitiales = [], { clientId = '' } = {}) {
  const [lignes, setLignes] = useState(lignesInitiales)
  const [badges, setBadges] = useState({})

  const setChamp = useCallback((key, champ, valeur) => {
    setLignes((ls) => ecrireChamp(ls, key, champ, valeur))
  }, [])

  const setProduit = useCallback((key, produit) => {
    setLignes((ls) => changerProduit(ls, key, produit))
  }, [])

  /**
   * Résolution de la liste de prix du client. La mise à jour est FONCTIONNELLE :
   * `prixManuel` est relu AU MOMENT DE L'ÉCRITURE, jamais sur un `lignes`
   * capturé au lancement de l'appel (qui serait périmé). Un échec ne bloque
   * jamais la saisie : le prix standard déjà posé reste.
   */
  const refreshTarif = useCallback(async (key, produitId, quantite) => {
    if (!produitId) {
      setBadges((b) => { const { [key]: _drop, ...reste } = b; return reste })
      return
    }
    try {
      const { data } = await ventesApi.getPrixApplicable({
        produit: produitId, client: clientId || undefined, quantite: quantite || 1,
      })
      let badge = null
      setLignes((ls) => {
        const r = appliquerTarif(ls, key, data)
        badge = r.badge
        return r.lignes
      })
      setBadges((b) => {
        if (badge) return { ...b, [key]: badge }
        const { [key]: _drop, ...reste } = b
        return reste
      })
    } catch {
      setBadges((b) => { const { [key]: _drop, ...reste } = b; return reste })
    }
  }, [clientId])

  return {
    lignes, setLignes, badges,
    setChamp, setProduit, refreshTarif,
    suggestionTva,
    utilisables: () => lignesUtilisables(lignes),
  }
}
