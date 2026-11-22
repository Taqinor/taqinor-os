import { PARAM_ONGLET } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'

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
