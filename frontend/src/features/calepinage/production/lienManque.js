import { PARAM_ONGLET } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'
import { premierOngletEtape } from '../atelier/parcoursGuide'
import { manqueClair } from './nomsPertes'

/* Lien vers le champ exact d'une cible de parcours (ACAL397) : onglet +
   `champ`, ou l'écran des réglages. Partagé par « Ce qui manque encore »
   et l'état « résultat incomplet ». */
export function lienManque(calepinageId, cible) {
  const onglet = cible?.onglet || ''
  const champ = cible?.champ || ''
  if (onglet === 'reglages') {
    // Le champ d'une clé de registre est monté sous `calx69-<clé>` (ReglagesSimulation) ; le serveur de
    // « à renseigner » (ACAL700) sert la clé nue, celui des refus de simulation l'id déjà préfixé. Les autres
    // ancres (`norme`, `lestage`, `lestage-<clé>`…) n'ont pas de « _ » et passent telles quelles.
    const id = champ && champ.includes('_') && !champ.startsWith('calx69-') ? `calx69-${champ}` : champ
    return id ? `/calepinage/reglages#${id}` : '/calepinage/reglages'
  }
  const p = new URLSearchParams()
  if (onglet) p.set(PARAM_ONGLET, onglet)
  if (champ) p.set(PARAM_CHAMP, champ)
  const q = p.toString()
  return `/calepinage/${calepinageId}${q ? `?${q}` : ''}`
}

/** R5B-N5 — LA destination d'une ligne de `parcours.manque`, pour TOUS ses lecteurs (« Pour un résultat complet » des
    Résultats, « Ce qui manque encore » du panneau Production) : une ligne dont le code nomme une ÉTAPE (`manqueClair` :
    les ombres → Panneaux, où l'ombre de chaque panneau se calcule) ouvre l'écran de cette étape (`state.etapeChoisie`,
    comme le clic sur l'étape, jamais la feuille « Avancé ») ; sinon la cible servie. `{ to, state }`. */
export function destinationManque(calepinageId, m) {
  const etape = manqueClair(m).etape
  return etape
    ? { to: lienManque(calepinageId, { onglet: premierOngletEtape(etape) }), state: { etapeChoisie: true } }
    : { to: lienManque(calepinageId, m?.cible), state: undefined }
}

/** ACAL1940 — le lien vers l'ÉCRAN d'une étape (son premier onglet), p. ex. « Désigner » l'onduleur → Électrique. */
export function lienEtape(calepinageId, etape) {
  return lienManque(calepinageId, { onglet: premierOngletEtape(etape) })
}
