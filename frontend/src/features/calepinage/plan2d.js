import { formatNumber } from '../../lib/format'

/* CAL104 — helpers PURS de la vue 2D plan (aucun React) : mise en forme d'une cote et
   milieu d'un segment. Isolés pour que `Vue2DPlan.jsx` n'exporte que son composant. */

/** Cote lisible : mètres à 2 décimales, séparateur français. */
export function formatCote(m) {
  if (!Number.isFinite(m)) return '—'
  return `${formatNumber(m, { decimals: 2 })} m`
}

/** Milieu d'un segment, pour poser l'étiquette de cote. */
export function milieu(a, b) {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
}
