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

export function applyDensity(density) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-density', normalizeDensity(density))
}

export function setStoredTheme(theme) {
  const t = normalizeTheme(theme)
  safeStorageSet(THEME_KEY, t)
  applyTheme(t)
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
