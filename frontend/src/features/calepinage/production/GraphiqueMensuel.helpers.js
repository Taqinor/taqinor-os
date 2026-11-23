/* Lecture des séries mensuelles SERVIES de l'étape Résultats (« Mois par mois » et mini-barres du héros) : aucune valeur
   calculée, un mois non servi vaut `null`. Fichier de fonctions pures (les composants sont dans GraphiqueMensuel.jsx). */

const nombreServi = (v) => typeof v === 'number' && Number.isFinite(v)

/** Les douze valeurs mensuelles SERVIES (null = non servi) : `{ prod, conso }`. Partagé avec le héros. */
export function lectureMensuelle(data) {
  const mensuel = Array.isArray(data?.production?.mensuel) ? data.production.mensuel : []
  const parMois = Array.isArray(data?.autoconsommation?.par_mois) ? data.autoconsommation.par_mois : []
  const prod = Array(12).fill(null)
  const conso = Array(12).fill(null)
  if (mensuel.length) {
    mensuel.forEach((m) => { if (m?.mois >= 1 && m.mois <= 12 && nombreServi(m.p50_kwh)) prod[m.mois - 1] = m.p50_kwh })
  } else {
    parMois.forEach((m) => { if (m?.mois >= 1 && m.mois <= 12 && nombreServi(m.production_kwh)) prod[m.mois - 1] = m.production_kwh })
  }
  parMois.forEach((m) => { if (m?.mois >= 1 && m.mois <= 12 && nombreServi(m.consommation_kwh)) conso[m.mois - 1] = m.consommation_kwh })
  return { prod, conso }
}

/** Trois repères ronds (pas de 1, 2 ou 5 × 10^n) dont le plus haut couvre `max` : `{ pas, haut }`. */
export function echelle(max) {
  const brut = max / 3
  const p = 10 ** Math.floor(Math.log10(brut))
  const pas = [1, 2, 5, 10].map((m) => m * p).find((s) => s >= brut) ?? 10 * p
  return { pas, haut: pas * 3 }
}

