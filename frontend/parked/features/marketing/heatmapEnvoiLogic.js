/* ============================================================================
   NTMKT24 — Logique pure de la heatmap d'engagement hebdomadaire par heure
   d'envoi, extraite de HeatmapEnvoi.jsx (react-refresh/only-export-components
   interdit à un fichier de composant d'exporter aussi des constantes/fonctions
   — même comportement, juste déplacé dans son propre module).
   ========================================================================== */

export const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi',
  'Samedi', 'Dimanche']

/** Libellé de suggestion, ou '' si l'historique ne permet rien d'affirmer. */
export function libelleMeilleurCreneau(meilleur) {
  if (!meilleur || !meilleur.envois) return ''
  const jour = JOURS[meilleur.jour] || ''
  const pct = Math.round((meilleur.taux_ouverture || 0) * 100)
  return `Vos contacts ouvrent le plus ${jour.toLowerCase()} ${meilleur.heure}h (${pct} % d'ouverture)`
}

/** Intensité 0-1 d'une case, relative au meilleur taux observé. */
export function intensite(cellule, maxTaux) {
  if (!maxTaux) return 0
  return Math.min(1, (cellule?.taux_ouverture || 0) / maxTaux)
}
