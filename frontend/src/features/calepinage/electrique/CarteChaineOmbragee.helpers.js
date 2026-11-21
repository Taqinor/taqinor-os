import { formatPercent } from '../../../lib/format'

/* ACAL712 — lecture PURE de l'étape `mismatch_ombrage` du résultat (ACAL711).
   Aucun calcul : les nombres sont ceux du serveur, arrondis à l'affichage. */

/** La liste FIXE des parades : aucune ne porte un chiffre de gain. */
export const PARADES = [
  'mettre ces modules sur une chaîne à part',
  'poser un optimiseur sur ces modules',
  'déplacer ou retirer ces modules',
]

// Une décimale seulement quand elle dit quelque chose : « 50 % », « 33,3 % ».
const pct = (v, decimals) => formatPercent(v, {
  decimals: Number.isInteger(Math.round(v * 10) / 10) ? 0 : decimals,
})

/** `{ chaines, hypothese }` — seules les chaînes dont les deux bornes diffèrent. */
export function chainesTouchees(cascade) {
  const etape = (cascade?.etapes ?? []).find((e) => e?.etape === 'mismatch_ombrage')
  const entree = etape?.entree
  if (!entree || typeof entree !== 'object') return { chaines: [], hypothese: '' }
  const chaines = (Array.isArray(entree.chaines) ? entree.chaines : [])
    .filter((c) => typeof c?.ecart_bornes_pct === 'number' && c.ecart_bornes_pct > 0)
  return { chaines, hypothese: entree.hypothese_orientation?.texte ?? '' }
}

/** La phrase de la carte : modules ombrés, module le plus ombré, fourchette de perte. */
export function phraseChaine(chaine) {
  const n = chaine?.modules_ombres?.length ?? 0
  const basse = chaine?.bornes?.basse?.perte_chaine_pct
  const haute = chaine?.bornes?.haute?.perte_chaine_pct
  const parties = []
  if (n > 0) parties.push(`${n} module${n > 1 ? 's' : ''} sous le seuil de votre société`)
  const acces = chaine?.module_le_plus_ombre?.acces
  if (typeof acces === 'number') parties.push(`le module le plus ombré reçoit ${pct(acces * 100, 0)} du soleil`)
  if (typeof basse === 'number' && typeof haute === 'number') {
    parties.push(`perte de la chaîne entre ${pct(basse, 1)} et ${pct(haute, 1)}`)
  }
  return parties.join(' ; ')
}
