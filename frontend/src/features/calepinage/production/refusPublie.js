// ACAL1650 — les lignes du DERNIER refus 409 de la simulation (`manquants[]`, servies par le serveur), par calepinage.
// Le bouton de simulation les publie ; la liste « Ce qui manque encore » et la pastille de l'étape Résultats du rail les
// lisent : un seul compte, celui du refus. Aucun appel réseau ni recalcul ici ; sans refus, liste vide.
import { useSyncExternalStore } from 'react'

const refus = new Map() // id → lignes `{champ, motif, cible}` du refus en cours
const abonnes = new Set()
const AUCUN = []

/** Publie (ou efface, avec `[]`) les lignes du refus d'un calepinage. */
export function publierRefus(calepinageId, manquants) {
  if (calepinageId == null) return
  const cle = String(calepinageId)
  const lignes = Array.isArray(manquants) ? manquants : []
  const avant = refus.get(cle) ?? AUCUN
  if (avant.length === lignes.length && lignes.every((l, i) => l === avant[i])) return
  if (lignes.length) refus.set(cle, lignes)
  else refus.delete(cle)
  abonnes.forEach((f) => f())
}

const abonner = (f) => { abonnes.add(f); return () => abonnes.delete(f) }

/** Les lignes du refus en cours (`[]` sans refus). */
export function useRefusPublie(calepinageId) {
  const cle = calepinageId == null ? null : String(calepinageId)
  return useSyncExternalStore(abonner, () => (cle ? refus.get(cle) ?? AUCUN : AUCUN), () => AUCUN)
}
