/** T4-X8-011 — le geste du tiroir : un BALAYAGE vers le haut (≥ 40 px) l'ouvre, vers le bas le referme, un simple TOUCHER
    (< 10 px de course) le bascule. Entre les deux : rien (un défilement qui dérape ne change pas le tiroir).
    Rend 'ouvrir' | 'fermer' | 'basculer' | null — la décision, sans toucher au DOM. */
export const SEUIL_BALAYAGE_PX = 40
export const SEUIL_TOUCHER_PX = 10
export function decisionGesteTiroir({ dy, deplie }) {
  if (!Number.isFinite(dy)) return null
  if (Math.abs(dy) < SEUIL_TOUCHER_PX) return 'basculer'
  if (dy <= -SEUIL_BALAYAGE_PX) return deplie ? null : 'ouvrir'
  if (dy >= SEUIL_BALAYAGE_PX) return deplie ? 'fermer' : null
  return null
}
