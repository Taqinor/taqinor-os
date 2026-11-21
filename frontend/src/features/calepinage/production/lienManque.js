import { PARAM_ONGLET } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'

/* Lien vers le champ exact d'une cible de parcours (ACAL397) : onglet +
   `champ`, ou l'écran des réglages. Partagé par « Ce qui manque encore »
   et l'état « résultat incomplet ». */
export function lienManque(calepinageId, cible) {
  const onglet = cible?.onglet || ''
  const champ = cible?.champ || ''
  if (onglet === 'reglages') {
    return champ ? `/calepinage/reglages#${champ}` : '/calepinage/reglages'
  }
  const p = new URLSearchParams()
  if (onglet) p.set(PARAM_ONGLET, onglet)
  if (champ) p.set(PARAM_CHAMP, champ)
  const q = p.toString()
  return `/calepinage/${calepinageId}${q ? `?${q}` : ''}`
}
