// VX46 — Logique PURE (aucun React) de « Mes préférences » : persistance
// localStorage par utilisateur, motif `COLLAPSE_KEY` (Layout.jsx:16) — lecture/
// écriture toujours défensives, jamais d'exception si le stockage est
// indisponible (mode privé, SSR, quota). AUCUN nouvel endpoint backend.
//
// Regroupe les préférences déjà éparpillées (thème/densité vivent dans
// design/theme.js — réutilisées telles quelles, PAS dupliquées ici) + les deux
// préférences qui n'avaient encore aucune surface :
//   • module d'atterrissage au login (`taqinor.landingModule`) — liste depuis
//     `moduleConfigs` (UX1), lu par Login.jsx à la connexion ; repli `/dashboard`
//     inchangé quand aucune préférence n'est choisie ou que le module choisi
//     n'existe plus.
//   • réduction de mouvement — override APP du media query OS
//     (`prefers-reduced-motion`), pour l'utilisateur qui veut le confort de
//     mouvement réduit sans changer son réglage système.

export const LANDING_KEY = 'taqinor.landingModule'
export const REDUCED_MOTION_KEY = 'taqinor.reducedMotion'

function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

// ── Module d'atterrissage au login ──────────────────────────────────────────

/** Lit la préférence brute (chaîne vide = « dernier module visité », VX11). */
export function getLandingModule() {
  const s = storage()
  if (!s) return ''
  try {
    return s.getItem(LANDING_KEY) || ''
  } catch {
    return ''
  }
}

export function setLandingModule(value) {
  const s = storage()
  if (!s) return
  try {
    if (value) s.setItem(LANDING_KEY, value)
    else s.removeItem(LANDING_KEY)
  } catch { /* stockage indisponible : on ignore, état non persisté */ }
}

/**
 * resolveLandingPath — route de destination post-login, à partir de la
 * préférence + de `moduleConfigs` (UX1) + du dernier module visité (VX11,
 * `taqinor.lastModule`). Résolution, du plus spécifique au repli :
 *   1. préférence explicite ('' = "dernier module visité") → cockpit du module
 *      choisi, si ce module existe TOUJOURS dans `moduleConfigs` ;
 *   2. préférence = '' (ou module disparu) + un dernier module visité connu ;
 *   3. repli historique inchangé : `/dashboard`.
 * `configs` est injecté (jamais importé ici) pour rester un module PUR,
 * testable sous `node --test` sans React ni bundler.
 */
export function resolveLandingPath(configs, lastModuleSegment) {
  const pref = getLandingModule()
  if (pref) {
    const found = (configs || []).find((c) => c.key === pref)
    if (found?.nav?.items?.[0]?.to) return found.nav.items[0].to
  }
  if (lastModuleSegment) {
    const found = (configs || []).find((c) => c.key === lastModuleSegment)
    if (found?.nav?.items?.[0]?.to) return found.nav.items[0].to
  }
  return '/dashboard'
}

export function getLastModuleSegment() {
  const s = storage()
  if (!s) return ''
  try {
    return s.getItem('taqinor.lastModule') || ''
  } catch {
    return ''
  }
}

// ── Réduction de mouvement (override app) ───────────────────────────────────

export function getReducedMotionPref() {
  const s = storage()
  if (!s) return false
  try {
    return s.getItem(REDUCED_MOTION_KEY) === '1'
  } catch {
    return false
  }
}

// Feuille de style singleton posée UNE fois dans <head> : mêmes règles que le
// bloc `@media (prefers-reduced-motion: reduce)` existant (index.css), mais
// déclenchées par l'attribut `data-reduced-motion="true"` plutôt que par la
// préférence OS — permet à un utilisateur de réduire le mouvement dans TAQINOR
// sans changer son réglage système. Coupe MOUVEMENT + ÉCHELLE, garde les
// transitions d'opacité/couleur (même choix que la règle OS, WCAG 2.3.3).
const OVERRIDE_STYLE_ID = 'taqinor-reduced-motion-override'
const OVERRIDE_CSS = `
[data-reduced-motion="true"] *, [data-reduced-motion="true"] *::before, [data-reduced-motion="true"] *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  scroll-behavior: auto !important;
  transition-property: opacity, color, background-color, border-color, box-shadow, fill, stroke !important;
  transition-duration: 120ms !important;
}
`

function ensureOverrideStyleTag() {
  if (typeof document === 'undefined') return
  if (document.getElementById(OVERRIDE_STYLE_ID)) return
  const style = document.createElement('style')
  style.id = OVERRIDE_STYLE_ID
  style.textContent = OVERRIDE_CSS
  document.head.appendChild(style)
}

/** Applique (ou retire) l'attribut qui active la feuille ci-dessus. */
export function applyReducedMotion(enabled) {
  if (typeof document === 'undefined') return
  ensureOverrideStyleTag()
  document.documentElement.setAttribute('data-reduced-motion', enabled ? 'true' : 'false')
}

export function setReducedMotionPref(enabled) {
  const s = storage()
  try {
    s?.setItem(REDUCED_MOTION_KEY, enabled ? '1' : '0')
  } catch { /* stockage indisponible : préférence non persistée, appliquée quand même */ }
  applyReducedMotion(enabled)
}

/**
 * initPreferences — à appeler UNE fois au démarrage de la coquille (Header,
 * monté sur tout écran authentifié) : applique la préférence de réduction de
 * mouvement déjà stockée. Thème/densité sont déjà initialisés par
 * `design/theme.js` (`initTheme()`, appelé par `<ThemeProvider>`) — non
 * dupliqué ici.
 */
export function initPreferences() {
  applyReducedMotion(getReducedMotionPref())
}
