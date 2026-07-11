/* ============================================================================
   SCA24 — Application du thème white-label par société (TenantTheme, FG392).
   ----------------------------------------------------------------------------
   Logique pure + application DOM gardée (typeof document), même convention que
   `theme.js` (clair/sombre). Consomme `GET /api/django/core/theme/courant/`
   (endpoint EXISTANT, zéro modification backend — voir SCA24 dans PLAN.md) et
   pose `logo_url`/`couleur_primaire`/`couleur_secondaire`/`nom_affichage` en
   variables CSS sur <html>, lues par le shell (Header) pour le logo et par les
   composants qui veulent la couleur de marque. Repli NEUTRE si le thème est
   absent/vide : on efface simplement les variables (les couleurs par défaut de
   tokens.css reprennent la main) — jamais de flash de couleur ni d'exception.
   ========================================================================== */

export const TENANT_THEME_VARS = {
  primary: '--brand-primary',
  secondary: '--brand-secondary',
  logo: '--brand-logo-url',
}

/** Normalise la réponse API (objet potentiellement partiel/vide) en forme sûre. */
export function normalizeTenantTheme(raw) {
  const t = raw && typeof raw === 'object' ? raw : {}
  return {
    logoUrl: typeof t.logo_url === 'string' ? t.logo_url : '',
    couleurPrimaire: typeof t.couleur_primaire === 'string' ? t.couleur_primaire : '',
    couleurSecondaire: typeof t.couleur_secondaire === 'string' ? t.couleur_secondaire : '',
    nomAffichage: typeof t.nom_affichage === 'string' ? t.nom_affichage : '',
  }
}

/**
 * Applique le thème de la société sur <html> via des variables CSS.
 * Toute valeur vide efface la variable correspondante (repli neutre — les
 * couleurs par défaut de tokens.css/-index.css reprennent la main).
 * No-op hors DOM (SSR / tests sans jsdom).
 */
export function applyTenantTheme(theme) {
  if (typeof document === 'undefined') return normalizeTenantTheme(theme)
  const t = normalizeTenantTheme(theme)
  const root = document.documentElement
  if (t.couleurPrimaire) {
    root.style.setProperty(TENANT_THEME_VARS.primary, t.couleurPrimaire)
  } else {
    root.style.removeProperty(TENANT_THEME_VARS.primary)
  }
  if (t.couleurSecondaire) {
    root.style.setProperty(TENANT_THEME_VARS.secondary, t.couleurSecondaire)
  } else {
    root.style.removeProperty(TENANT_THEME_VARS.secondary)
  }
  if (t.logoUrl) {
    root.style.setProperty(TENANT_THEME_VARS.logo, `url("${t.logoUrl}")`)
  } else {
    root.style.removeProperty(TENANT_THEME_VARS.logo)
  }
  return t
}

/** Efface toute variable de thème posée — repli neutre explicite. */
export function clearTenantTheme() {
  return applyTenantTheme(null)
}

/* ── Petit pub/sub en mémoire ────────────────────────────────────────────────
   Le shell (Header) affiche le logo/nom de marque SANS re-fetcher — Layout est
   l'unique lecteur réseau (SCA24) et republie ici après chaque
   `applyTenantTheme`/`clearTenantTheme`. Pas de Redux : un thème de société est
   un détail d'affichage du shell, pas un état métier partagé. */
let _current = normalizeTenantTheme(null)
const _listeners = new Set()

export function getCurrentTenantTheme() {
  return _current
}

export function subscribeTenantTheme(listener) {
  _listeners.add(listener)
  return () => _listeners.delete(listener)
}

function _publish(theme) {
  _current = theme
  _listeners.forEach((fn) => fn(theme))
}

const _applyTenantTheme = applyTenantTheme
export function setTenantTheme(theme) {
  const applied = _applyTenantTheme(theme)
  _publish(applied)
  return applied
}
export function resetTenantTheme() {
  return setTenantTheme(null)
}
