// VX237 — Collage intelligent : le presse-papiers du monde réel entre
// proprement. 0 `onPaste` existait dans tout le frontend avant cette tâche —
// un numéro WhatsApp collé avec espaces/points/tirets, un montant copié
// d'Excel (espaces milliers, virgule décimale, suffixe « DH »), une carte de
// visite texte tombaient bruts dans l'`<input>`. Zéro dépendance, regex
// pures (les parseurs vivent dans `lib/paste.js`, sans React, pour rester
// testables tels quels). Un parser qui ne reconnaît RIEN retourne `null` : le
// collage natif du navigateur s'applique alors normalement (jamais un champ
// vidé en silence).
import { useCallback } from 'react'

export { parsePastedPhone, parsePastedAmount, parsePasteCard } from '../lib/paste'

/**
 * Hook générique : pose `onPaste` sur un champ contrôlé. `parser(text)`
 * reçoit le texte brut du presse-papiers ; s'il retourne une valeur
 * non-null, celle-ci remplace la valeur du champ (via `onClean`) et le
 * collage natif est annulé. S'il retourne `null`, le collage natif du
 * navigateur s'applique normalement (jamais de champ vidé en silence).
 */
export function usePasteClean(parser, onClean) {
  return useCallback((e) => {
    const text = e.clipboardData?.getData('text')
    if (!text) return
    const cleaned = parser(text)
    if (cleaned == null) return
    e.preventDefault()
    onClean(cleaned)
  }, [parser, onClean])
}

export default usePasteClean
