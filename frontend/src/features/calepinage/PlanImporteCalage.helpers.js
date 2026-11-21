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

const nombreFr = (n) => String(Math.round(Number(n) * 100) / 100).replace('.', ',')

/**
 * ACAL513 — la phrase du contrôle d'échelle rendu par le serveur (`controle_echelle`,
 * ACAL512) : la distance A–B selon l'unité DÉCLARÉE du fichier face à la distance tapée.
 * Rien n'est corrigé ni bloqué ; unité inconnue ⇒ aucun contrôle ; réponse sans la clé ⇒ `null`.
 */
export function phraseControleEchelle(controle) {
  if (!controle || typeof controle !== 'object') return null
  const selon = Number(controle.distance_selon_unite_m)
  const rapport = Number(controle.rapport)
  if (controle.distance_selon_unite_m == null || controle.rapport == null
    || !Number.isFinite(selon) || !Number.isFinite(rapport)) {
    return controle.motif || 'Le fichier ne déclare pas son unité : aucun contrôle possible.'
  }
  const debut = `Selon l’unité du fichier (${controle.unite}), A–B mesure ${nombreFr(selon)} m`
  const saisi = `${nombreFr(controle.distance_saisie_m)} m`
  if (nombreFr(rapport) === '1') return `${debut} — vous avez tapé ${saisi} : les deux concordent.`
  return `${debut} — vous avez tapé ${saisi} (×${nombreFr(rapport)}).`
}
