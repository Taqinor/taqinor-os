/* ============================================================================
   K147 — Thème partagé du kit graphique (tokens marque, pas de couleurs en dur).
   ----------------------------------------------------------------------------
   Toutes les couleurs sortent des tokens sémantiques (`var(--…)`) : elles
   suivent le thème clair/sombre. Les attributs SVG de recharts acceptent
   directement les `var(--…)`.
   ========================================================================== */

// Tons sémantiques utilisables comme `fill`/`stroke` recharts.
export const CHART_TOKENS = {
  primary: 'var(--primary)',
  info: 'var(--info)',
  success: 'var(--success)',
  warning: 'var(--warning)',
  danger: 'var(--destructive)',
  muted: 'var(--muted-foreground)',
  grid: 'var(--border)',
  axis: 'var(--muted-foreground)',
  surface: 'var(--popover)',
  surfaceText: 'var(--popover-foreground)',
}

/** Résout un nom de ton (`'primary'`…) ou une valeur CSS brute en couleur. */
export function resolveColor(tone) {
  if (!tone) return CHART_TOKENS.info
  return CHART_TOKENS[tone] ?? tone
}

// Durée d'animation marque (ease-out). Mise à 0 quand le système demande la
// réduction des animations (cf. prefersReducedMotion).
export const CHART_ANIM_DURATION = 600
export const CHART_ANIM_EASING = 'ease-out'

/** Détecte `prefers-reduced-motion: reduce` (sans plantage hors navigateur). */
export function prefersReducedMotion() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

/**
 * Durée d'animation effective : 0 si l'utilisateur a demandé la réduction des
 * animations, sinon la durée marque (ou une durée fournie).
 */
export function animationDuration(base = CHART_ANIM_DURATION) {
  return prefersReducedMotion() ? 0 : base
}

// Rayon de coin des barres (marque : coins hauts arrondis).
export const BAR_RADIUS = [4, 4, 0, 0]
// Rayon des barres horizontales (coins droits arrondis).
export const BAR_RADIUS_H = [0, 4, 4, 0]

// Style commun de l'infobulle (surface + bordure tokenisées).
export const TOOLTIP_STYLE = {
  borderRadius: 10,
  fontSize: 12,
  border: `1px solid ${CHART_TOKENS.grid}`,
  background: CHART_TOKENS.surface,
  color: CHART_TOKENS.surfaceText,
  boxShadow: 'var(--shadow-md)',
}

export default {
  CHART_TOKENS,
  resolveColor,
  prefersReducedMotion,
  animationDuration,
  CHART_ANIM_DURATION,
  CHART_ANIM_EASING,
  BAR_RADIUS,
  BAR_RADIUS_H,
  TOOLTIP_STYLE,
}
