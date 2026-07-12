/* ============================================================================
   F18 — Infrastructure de thème (clair / sombre / système) + densité (F20)
   ----------------------------------------------------------------------------
   Logique pure + application DOM gardée (typeof document). Défaut = « système »
   (suit la préférence de l'OS), conformément au plan. Les écrans existants ont
   des couleurs en dur : passer en sombre ne les modifie PAS — seules les
   surfaces tokenisées (/src/ui) réagissent. Aucune régression visuelle.
   ========================================================================== */

export const THEME_KEY = 'taqinor-theme'
export const DENSITY_KEY = 'taqinor-density'

export const THEMES = ['light', 'dark', 'system']
export const DENSITIES = ['comfortable', 'compact']

/** Couleur de la barre (meta theme-color / iOS) par thème résolu. */
const THEME_COLOR = { light: '#f6f8fc', dark: '#070b1d' }

export function normalizeTheme(value) {
  return THEMES.includes(value) ? value : 'system'
}
export function normalizeDensity(value) {
  return DENSITIES.includes(value) ? value : 'comfortable'
}

function safeStorageGet(key) {
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem(key) : null
  } catch {
    return null
  }
}
function safeStorageSet(key, value) {
  try {
    if (typeof localStorage !== 'undefined') localStorage.setItem(key, value)
  } catch {
    /* mode privé / quota : on ignore */
  }
}

export function getStoredTheme() {
  return normalizeTheme(safeStorageGet(THEME_KEY))
}
export function getStoredDensity() {
  return normalizeDensity(safeStorageGet(DENSITY_KEY))
}

export function prefersDark() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )
}

/** 'system' → 'light'|'dark' selon l'OS ; 'light'/'dark' → inchangé. */
export function resolveTheme(theme, isDark = prefersDark()) {
  const t = normalizeTheme(theme)
  if (t === 'system') return isDark ? 'dark' : 'light'
  return t
}

/** Applique le thème au <html> : classe .dark, color-scheme, meta theme-color. */
export function applyTheme(theme) {
  if (typeof document === 'undefined') return
  const resolved = resolveTheme(theme)
  const root = document.documentElement
  root.classList.toggle('dark', resolved === 'dark')
  root.style.colorScheme = resolved
  root.setAttribute('data-theme', resolved)
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', THEME_COLOR[resolved])
}

const THEME_TRANSITION_CLASS = 'theme-transitioning'
const THEME_TRANSITION_MS = 200

/**
 * VX134(e) — `applyTheme` bascule `.dark` d'un coup (couleurs OKLCH en cut
 * sec). Ici : pose une classe TRANSITOIRE (index.css l'anime en ≤200ms),
 * applique le thème, puis retire la classe après coup — jamais permanente
 * (pas de transition parasite sur un changement d'état non lié au thème).
 * `applyTheme()` lui-même reste instantané (appelé par `initTheme()` au
 * premier paint) : aucun FOUC n'est introduit par cette fonction séparée.
 */
export function applyThemeWithTransition(theme) {
  if (typeof document === 'undefined') { applyTheme(theme); return }
  const root = document.documentElement
  root.classList.add(THEME_TRANSITION_CLASS)
  applyTheme(theme)
  setTimeout(() => root.classList.remove(THEME_TRANSITION_CLASS), THEME_TRANSITION_MS)
}

export function applyDensity(density) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-density', normalizeDensity(density))
}

export function setStoredTheme(theme) {
  const t = normalizeTheme(theme)
  safeStorageSet(THEME_KEY, t)
  // VX134(e) — bascule explicite (toggle utilisateur) : transition douce.
  applyThemeWithTransition(t)
  return t
}
export function setStoredDensity(density) {
  const d = normalizeDensity(density)
  safeStorageSet(DENSITY_KEY, d)
  applyDensity(d)
  return d
}

/** Réapplique le thème quand l'OS bascule clair/sombre (si thème = système). */
export function subscribeSystemTheme(onChange) {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return () => {}
  }
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  const handler = () => onChange(mq.matches)
  mq.addEventListener('change', handler)
  return () => mq.removeEventListener('change', handler)
}

/** Au démarrage : applique la préférence stockée (thème + densité). */
export function initTheme() {
  applyTheme(getStoredTheme())
  applyDensity(getStoredDensity())
}

/* ============================================================================
   F121 — Échelle typographique + chiffres tabulaires (zéro barré)
   ----------------------------------------------------------------------------
   Miroir JS des tokens `--text-*` de tokens.css : sept paliers documentés
   (taille rem / interligne / letter-spacing négatif croissant). Sert de source
   unique aux composants qui veulent l'échelle en JS et est vérifié par le test
   contre tokens.css. `FORMAT_FEATURES` regroupe les réglages OpenType utilisés
   sur tout contexte monétaire / quantité / référence (tabular + zéro barré).
   ========================================================================== */

/** Paliers de l'échelle typographique (rem, interligne sans unité, em). */
export const TEXT_SCALE = {
  display: { size: '3rem', lineHeight: '1.05', letterSpacing: '-0.03em' },
  h1: { size: '2.25rem', lineHeight: '1.1', letterSpacing: '-0.025em' },
  h2: { size: '1.75rem', lineHeight: '1.2', letterSpacing: '-0.02em' },
  h3: { size: '1.375rem', lineHeight: '1.3', letterSpacing: '-0.015em' },
  body: { size: '1rem', lineHeight: '1.55', letterSpacing: '0em' },
  small: { size: '0.875rem', lineHeight: '1.45', letterSpacing: '0.005em' },
  caption: { size: '0.75rem', lineHeight: '1.4', letterSpacing: '0.02em' },
}

/** Réglages OpenType pour montants/quantités/références (= `.tabular-nums`). */
export const FORMAT_FEATURES = Object.freeze({
  fontVariantNumeric: 'tabular-nums slashed-zero',
  fontFeatureSettings: "'tnum' 1, 'zero' 1",
})

/**
 * Style en ligne React pour tout nombre tabulaire (montant, quantité,
 * référence) : chiffres à chasse fixe + zéro barré. À étaler sur un <td>,
 * une cellule de KPI ou un total. Renvoie une copie de FORMAT_FEATURES.
 */
export function tabularNumStyle() {
  return { ...FORMAT_FEATURES }
}
