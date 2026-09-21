/* NTESG19 — pure helper extracted from WizardObjectifTrajectoire.jsx so the
 * component file only exports a component (react-refresh/only-export-components).
 */

/** Trajectoire linéaire théorique entre (annéeRef, valRef) et (annéeCible, valCible). */
export function trajectoireLineaire(
  { anneeReference, valeurReference, anneeCible, valeurCible }) {
  const a0 = Number(anneeReference)
  const a1 = Number(anneeCible)
  const v0 = Number(valeurReference)
  const v1 = Number(valeurCible)
  if (!Number.isFinite(a0) || !Number.isFinite(a1)
      || !Number.isFinite(v0) || !Number.isFinite(v1) || a1 <= a0) {
    return []
  }
  const points = []
  for (let annee = a0; annee <= a1; annee += 1) {
    const part = (annee - a0) / (a1 - a0)
    points.push({ annee, valeur: Number((v0 + (v1 - v0) * part).toFixed(4)) })
  }
  return points
}
