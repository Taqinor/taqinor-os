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

// VX41 — Échelle catégorielle de marque pour les séries multiples (elles
// retombaient jusqu'ici sur un seul ton). Dérivée des accents de module (VX8)
// + tons sémantiques existants : déjà thémée clair/sombre, zéro teinte
// inventée. Ordre pensé pour un contraste maximal entre séries adjacentes.
export const CHART_CATEGORICAL = [
  'var(--module-accent-brass)',
  'var(--module-accent-azur)',
  'var(--color-encre-soft)',
  'var(--module-accent-lune)',
  'var(--success)',
  'var(--warning)',
]

/** Couleur catégorielle n° `index` (boucle si la série dépasse la palette). */
export function categoricalColor(index) {
  const n = CHART_CATEGORICAL.length
  return CHART_CATEGORICAL[((index % n) + n) % n]
}

// VX41 — Grille signature (data-ink minimal, façon Tufte) : pointillés très
// légers, lignes HORIZONTALES seules (jamais de verticales ni de ligne
// d'axe pleine). À passer directement aux props `<CartesianGrid {...}>`.
export const CHART_GRID_STYLE = {
  stroke: CHART_TOKENS.grid,
  strokeDasharray: '2 4',
  strokeOpacity: 0.6,
  horizontal: true,
  vertical: false,
}

// VX41 — Style de la série « période précédente » : même ton que la série
// courante mais en pointillé, plus fine, non remplie — pour une comparaison
// togglable superposée sans doubler le nombre de graphiques.
export const CHART_COMPARISON_STYLE = {
  strokeDasharray: '4 3',
  strokeWidth: 1.5,
  fillOpacity: 0,
}

// VX41 — Style d'annotation `ReferenceLine` pour les événements ponctuels
// (ex. marqueur de maintenance sur une courbe de production) : trait fin
// pointillé + étiquette discrète, ton sémantique par défaut = warning.
export const CHART_REFERENCE_LINE_STYLE = {
  stroke: CHART_TOKENS.warning,
  strokeDasharray: '3 3',
  strokeWidth: 1,
  labelStyle: { fontSize: 10, fill: CHART_TOKENS.muted },
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
  CHART_CATEGORICAL,
  categoricalColor,
  CHART_GRID_STYLE,
  CHART_COMPARISON_STYLE,
  CHART_REFERENCE_LINE_STYLE,
}
