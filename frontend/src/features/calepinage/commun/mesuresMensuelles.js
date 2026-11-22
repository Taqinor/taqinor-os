/* Aides partagées des onglets « mesures » de l'étape Résultats (ACAL847, ACAL888) :
   les douze mois, l'écriture d'un nombre servi et la lecture d'une saisie. */

export const MOIS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août',
  'Septembre', 'Octobre', 'Novembre', 'Décembre']

/** Un nombre servi, ou « — » quand il est vide (jamais 0). */
export const nombre = (valeur, signe = false) => {
  if (valeur === null || valeur === undefined) return '—'
  const texte = String(valeur).replace('.', ',')
  return signe && valeur > 0 ? `+${texte}` : texte
}

/** Le texte saisi → ce qui part : vide ⇒ `null`, virgule décimale normalisée, le reste tel quel. */
export function valeurSaisie(texte) {
  const propre = String(texte ?? '').trim().replace(/\s/g, '').replace(',', '.')
  if (propre === '') return null
  const n = Number(propre)
  return Number.isFinite(n) ? n : propre
}
