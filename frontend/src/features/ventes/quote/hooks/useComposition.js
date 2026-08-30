// QJR90 — `useComposition` : rend `{ lignes, source, raison }`. L'appelant
// DOIT rendre `raison` (elle n'est jamais vide) : c'est ce qui fait de la
// bannière QJR36 une propriété STRUCTURELLE et non un `if` à ne pas oublier.
//
// Patron maison : la résolution vit dans `useCompositionPur.js` (testée sous
// `node --test`) ; ce fichier n'enchaîne que le dry-run serveur et le repli.
// Le marché est un module de stratégie QJR89 : c'est LUI qui dit si sa
// composition passe par le serveur (`{ mode: 'serveur' }`, résidentiel) ou
// reste locale (industriel / commercial / agricole).
//
// Hook AJOUTÉ TESTÉ (via sa moitié pure), IMPORTÉ PAR PERSONNE (vague M4).
import { useCallback, useState } from 'react'
import ventesApi from '../../../../api/ventesApi'
import { resoudreComposition } from './useCompositionPur'

export {
  resoudreComposition, raisonRepli, RAISON_SERVEUR, RAISON_RIEN,
} from './useCompositionPur'

/**
 * @param marche  module de stratégie QJR89 (`residentiel`, `industriel`…).
 * @returns `{ lignes, source, raison, chargement, composer }`.
 */
export function useComposition(marche, deps = {}) {
  const [resultat, setResultat] = useState(
    () => resoudreComposition({ marche: marche?.cle }))
  const [chargement, setChargement] = useState(false)

  const composer = useCallback(async (etat) => {
    if (!marche) return resoudreComposition({})
    const plan = marche.composer(etat, deps)
    // Marchés SANS dry-run serveur : la sortie du module de marché EST la
    // composition, avec sa raison.
    if (plan.mode !== 'serveur') {
      const r = resoudreComposition({ local: plan, marche: marche.cle })
      setResultat(r)
      return r
    }
    setChargement(true)
    try {
      const { data } = await ventesApi.composerDevis(plan.corps)
      const r = resoudreComposition({ serveur: data, marche: marche.cle })
      setResultat(r)
      return r
    } catch (err) {
      // Repli local EXPLICITE : la cause est nommée dans `raison`, jamais tue.
      const local = typeof deps.composerLocalement === 'function'
        ? deps.composerLocalement(etat) : null
      const r = resoudreComposition({
        local,
        erreur: err?.response?.data?.detail || err?.message || 'erreur réseau',
        marche: marche.cle,
      })
      setResultat(r)
      return r
    } finally {
      setChargement(false)
    }
  }, [marche, deps])

  return { ...resultat, chargement, composer }
}
