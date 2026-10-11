// ENF22 — helpers extraits de PlanImporteCalage.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/**
 * CAL63 — l'ÉCHELLE, depuis deux points de référence et la distance RÉELLE
 * saisie entre eux. Rend `{ echelle, distancePlan, source: 'saisie' }`, ou
 * `null` si l'un des deux points manque, si les deux points sont confondus,
 * ou si la distance réelle n'est pas une longueur strictement positive.
 *
 * JAMAIS de repli sur 1 : une échelle inventée produit un plan faux qui a
 * l'air juste — exactement ce que la docstring de CAL62 interdit.
 */
export function echelleDepuisDeuxPoints(a, b, distanceReelleM) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length < 2 || b.length < 2) {
    return null
  }
  const reelle = Number(distanceReelleM)
  if (!Number.isFinite(reelle) || reelle <= 0) return null
  const dx = Number(b[0]) - Number(a[0])
  const dy = Number(b[1]) - Number(a[1])
  const distancePlan = Math.hypot(dx, dy)
  if (!Number.isFinite(distancePlan) || distancePlan === 0) return null
  return {
    echelle: reelle / distancePlan,
    distancePlan,
    source: 'saisie',
  }
}
