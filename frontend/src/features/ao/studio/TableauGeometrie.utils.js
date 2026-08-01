import { appliquerSiValide } from './snap'

/* ============================================================================
   AOF77 — Fonctions pures du tableau de géométrie, isolées du composant.
   ----------------------------------------------------------------------------
   Extrait de `TableauGeometrie.jsx` (react-refresh/only-export-components) :
   un fichier de composant ne doit exporter QUE des composants pour que le
   Fast Refresh de Vite reste fiable en dev — ces fonctions/constantes, elles,
   n'en sont pas et vivent donc ici, ré-importées par le composant.
   ========================================================================== */

export const MIN_SOMMETS_PUBLIABLE = 3

export function versNombre(valeur) {
  if (valeur === '' || valeur == null) return null
  const n = Number(String(valeur).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

export function lettreDe(index) {
  const i = Math.max(0, Math.trunc(Number(index) || 0))
  return String.fromCharCode(65 + (i % 26)) + (i >= 26 ? String(Math.floor(i / 26)) : '')
}

/**
 * Garde d'ÉDITION/SUPPRESSION d'un sommet EXISTANT. En dessous de 3 sommets,
 * le contour est un brouillon (aucune aire ni auto-intersection à défendre) :
 * on laisse passer. À partir de 3, c'est EXACTEMENT `appliquerSiValide` de
 * `Selection.jsx` — la même porte, quelle que soit la voie.
 */
export function appliquerEditionGeometrie(avant, apres) {
  if (!Array.isArray(apres) || apres.length < MIN_SOMMETS_PUBLIABLE) {
    return { points: apres, valide: true, raison: null, message: null }
  }
  return appliquerSiValide(avant, apres)
}

/** Validité d'un obstacle rectangle — `null` si conforme, message FR sinon. */
export function verifierObstacleRectangle(obstacle) {
  const x0 = versNombre(obstacle?.rectX0M)
  const x1 = versNombre(obstacle?.rectX1M)
  const y0 = versNombre(obstacle?.rectY0M)
  const y1 = versNombre(obstacle?.rectY1M)
  if (x0 != null && x1 != null && x1 <= x0) {
    return 'x1 doit être strictement supérieur à x0.'
  }
  if (y0 != null && y1 != null && y1 <= y0) {
    return 'y1 doit être strictement supérieur à y0.'
  }
  const degagement = versNombre(obstacle?.degagementM)
  if (degagement != null && degagement < 0) {
    return 'Le dégagement ne peut pas être négatif.'
  }
  return null
}
