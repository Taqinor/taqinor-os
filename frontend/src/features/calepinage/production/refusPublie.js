// ACAL1650 — les lignes du DERNIER refus 409 de la simulation (`manquants[]`, servies par le serveur), par calepinage.
// Le bouton de simulation les publie ; la liste « Ce qui manque encore » et la pastille de l'étape Résultats du rail les
// lisent : un seul compte, celui du refus. Aucun appel réseau ni recalcul ici ; sans refus, liste vide.
import { useSyncExternalStore } from 'react'

const parSource = new Map() // id → Map(source → lignes `{champ, motif, cible}`) : chaque éditeur n'efface que SA publication
const refus = new Map() // id → lignes fusionnées (référence stable tant que rien ne change)
const abonnes = new Set()
const AUCUN = []
const SOURCE_PAR_DEFAUT = 'calcul'

/** Publie (ou efface, avec `[]`) les lignes du refus d'un calepinage. `source` : qui publie (le bouton de calcul, la
 *  simulation automatique de l'étape Résultats…) — retirer la publication d'une source laisse celle des autres. */
export function publierRefus(calepinageId, manquants, source = SOURCE_PAR_DEFAUT) {
  if (calepinageId == null) return
  const cle = String(calepinageId)
  const lignes = Array.isArray(manquants) ? manquants : []
  const sources = parSource.get(cle) ?? new Map()
  const avantSource = sources.get(source) ?? AUCUN
  if (avantSource.length === lignes.length && lignes.every((l, i) => l === avantSource[i])) return
  if (lignes.length) sources.set(source, lignes)
  else sources.delete(source)
  if (sources.size) parSource.set(cle, sources)
  else parSource.delete(cle)
  const fusion = [...sources.values()].flat()
  if (fusion.length) refus.set(cle, fusion)
  else refus.delete(cle)
  abonnes.forEach((f) => f())
}

const abonner = (f) => { abonnes.add(f); return () => abonnes.delete(f) }

/** Les lignes du refus en cours (`[]` sans refus). */
export function useRefusPublie(calepinageId) {
  const cle = calepinageId == null ? null : String(calepinageId)
  return useSyncExternalStore(abonner, () => (cle ? refus.get(cle) ?? AUCUN : AUCUN), () => AUCUN)
}
