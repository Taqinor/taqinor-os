/* VX43 — Maths PURES du geste pull-to-refresh (aucun React, aucune dépendance) :
   isolées ici pour rester testables sous `node --test` sans DOM ni React
   installés (même pattern que `lib/optimistic.js` pour useOptimisticSave.js).
   Consommées par `usePullToRefresh.js`, qui ne fait que les brancher aux
   évènements tactiles. */

/** Résistance non-linéaire : la distance affichée croît de moins en moins vite
    que la distance réellement tirée (sensation de « ressort sous le doigt »,
    jamais un défilement 1:1). `raw` et le résultat sont en pixels ≥ 0. */
export function dampenPull(raw, maxPull = 120) {
  if (raw <= 0) return 0
  // Amortissement classique « pull to refresh » : approche maxPull sans jamais
  // le dépasser, en restant quasi linéaire pour les petites distances.
  const damped = maxPull * (1 - Math.exp(-raw / (maxPull * 0.9)))
  return Math.min(damped, maxPull)
}

/** Le geste ne s'arme QUE si le conteneur est déjà tout en haut (sinon c'est un
    scroll normal, jamais un pull) et si le mouvement est bien vertical vers le
    bas (anti-scroll horizontal). */
export function shouldArmPull({ scrollTop, deltaX = 0, deltaY }) {
  if (scrollTop > 0) return false
  if (deltaY <= 0) return false
  return Math.abs(deltaY) > Math.abs(deltaX)
}

/** Un lâcher déclenche le rafraîchissement quand la distance amortie atteint le
    seuil (par défaut 64px, confortable au pouce sans déclenchement accidentel
    lors d'un simple petit rebond). */
export function shouldTriggerRefresh(pullDistance, threshold = 64) {
  return pullDistance >= threshold
}

export const DEFAULT_MAX_PULL = 120
export const DEFAULT_THRESHOLD = 64
