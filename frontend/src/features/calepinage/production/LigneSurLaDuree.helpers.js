/* ACAL1657 — « Année basse » nomme ce que le P90 compte. Les composantes d'incertitude SERVIES
   (`incertitude.composantes[].nom`) sont dites en mots de tous les jours ; sans autre composante que la
   variabilité météo (ou sans composante servie), la phrase dit « variabilité météo seule ». Aucun calcul. */
const LIBELLE_COMPOSANTE = {
  variabilite_interannuelle: 'variabilité météo',
  modele_simulation: 'modèle de simulation',
  biais_long_terme: 'biais à long terme',
  incertitude_fiche: 'incertitude de la fiche',
}

export function libelleAnneeBasse(incertitude) {
  const composantes = Array.isArray(incertitude?.composantes) ? incertitude.composantes : []
  const noms = composantes
    .map((c) => LIBELLE_COMPOSANTE[c?.nom])
    .filter((n, i, tous) => n && tous.indexOf(n) === i)
  const compte = noms.length <= 1
    ? 'variabilité météo seule'
    : `${noms.slice(0, -1).join(', ')} et ${noms[noms.length - 1]}`
  return `Année basse (${compte}, 9 années sur 10 au-dessus)`
}
