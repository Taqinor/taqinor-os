// VX46 — Logique PURE (aucun React) de « Mes préférences » : persistance
// localStorage par utilisateur, motif `COLLAPSE_KEY` (Layout.jsx:16) — lecture/
// écriture toujours défensives, jamais d'exception si le stockage est
// indisponible (mode privé, SSR, quota). AUCUN nouvel endpoint backend.
//
// Regroupe les préférences déjà éparpillées (thème/densité vivent dans
// design/theme.js — réutilisées telles quelles, PAS dupliquées ici) + les deux
// préférences qui n'avaient encore aucune surface :
//   • module d'atterrissage au login (`taqinor.landingModule`) — liste depuis
//     `moduleConfigs` (UX1), lu par Login.jsx à la connexion ; depuis ODY3 le
//     repli n'est plus `/dashboard` mais le Menu d'accueil `/apps` quand aucune
//     préférence n'est choisie ou que le module choisi n'existe plus.
//   • réduction de mouvement — override APP du media query OS
//     (`prefers-reduced-motion`), pour l'utilisateur qui veut le confort de
//     mouvement réduit sans changer son réglage système.
//   • NTMOB12 — qualité photo (Standard compressé / Original), propre à CET
//     APPAREIL (comme les autres réglages de ce fichier) : gouverne si les
//     écrans de capture terrain (checklist NTMOB11, GED NumeriserPage, SAV)
//     recompressent une photo avant envoi.

import { compressImage } from '../../ui/file-utils'

export const LANDING_KEY = 'taqinor.landingModule'
/** ODY3 — valeur sentinelle du choix EXPLICITE « dernier module visité » (VX11).
 *  Préférence absente ('') = Menu d'accueil `/apps`, le défaut du paradigme. */
export const LANDING_LAST_MODULE = '__dernier__'
export const REDUCED_MOTION_KEY = 'taqinor.reducedMotion'
export const PHOTO_QUALITY_KEY = 'taqinor.photoQuality'
/** ODY29 — « À l'ouverture d'une app » : que faire de la route mémorisée. */
export const APP_RESUME_KEY = 'taqinor.appResume'
/** Proposer « Reprendre » sur la tuile — DÉFAUT (absence de clé). */
export const APP_RESUME_ASK = ''
/** Entrer directement là où l'utilisateur s'était arrêté. */
export const APP_RESUME_ALWAYS = 'reprendre'
/** Toujours entrer par le cockpit de l'app (aucune proposition). */
export const APP_RESUME_NEVER = 'cockpit'
// EZ9 — mode « Plein soleil » (terrain). Même patron de persistance que les
// autres préférences : propre à CET appareil (le téléphone du technicien).
export const SUNLIGHT_KEY = 'taqinor.sunlight'
// NTMOB17 — mode « Économie de données ». Délibérément propre à CET APPAREIL
// (comme tous les réglages de ce fichier) et NON reflété sur le compte serveur :
// c'est une caractéristique du LIEN RÉSEAU du téléphone (forfait data en
// tournée), pas du compte — le même utilisateur sur son poste au bureau ne veut
// pas hériter du mode. Trois effets, tous portés par des consommateurs qui
// lisent cette préférence : vignettes photo chargées au tap (`DataSaverThumb`),
// sondage du chat ralenti (`useChatPolling` × `DATA_SAVER_POLL_FACTOR`) et
// compression photo maximale forcée (`compressPhotoForUpload` ci-dessous).
export const DATA_SAVER_KEY = 'taqinor.dataSaver'
/** Événement émis à chaque bascule : permet aux écrans montés de réagir sans
 *  remontage (localStorage seul n'émet `storage` que pour les AUTRES onglets). */
export const DATA_SAVER_EVENT = 'taqinor:data-saver'
/** Facteur de ralentissement des sondages réseau quand le mode est actif. */
export const DATA_SAVER_POLL_FACTOR = 4

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
 *   3. ODY3 — mono-app : si l'utilisateur ne voit QU'UNE app (`apps` injecté),
 *      on y entre directement — antidote au piège Odoo « la grille ajoute un
 *      clic » quand il n'y a rien à choisir ;
 *   4. ODY3 — repli : le Menu d'accueil `/apps` (« j'ouvre → MES apps »).
 *      C'était `/dashboard` avant le paradigme ODY ; `/dashboard` reste une
 *      route parfaitement valide (l'app « Tableau de bord »), simplement plus
 *      la porte d'entrée.
 * `configs` et `apps` sont injectés (jamais importés ici) pour que ce module
 * reste PUR, testable sans React ni bundler.
 */
export function resolveLandingPath(configs, lastModuleSegment, { apps } = {}) {
  const pref = getLandingModule()
  // ODY3 — « dernier module visité » (VX11) est désormais un choix EXPLICITE,
  // plus le défaut implicite. Avant, préférence vide == « dernier module », si
  // bien que tout utilisateur de retour atterrissait dans son dernier module :
  // le Menu d'accueil, cœur du paradigme ODY (« j'ouvre → MES apps »), n'aurait
  // été vu que par un compte tout neuf.
  if (pref === LANDING_LAST_MODULE) {
    const found = (configs || []).find((c) => c.key === lastModuleSegment)
    if (found?.nav?.items?.[0]?.to) return found.nav.items[0].to
    return '/apps'
  }
  if (pref) {
    const found = (configs || []).find((c) => c.key === pref)
    if (found?.nav?.items?.[0]?.to) return found.nav.items[0].to
  }
  if (apps?.length === 1 && apps[0]?.to) return apps[0].to
  return '/apps'
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

// ── ODY29 — À l'ouverture d'une app (proposer / toujours / jamais) ──────────
// La MÉMOIRE elle-même (quelle route pour quelle app) vit dans
// `lib/apps/appPrefs.js` (sessionStorage, clé par app+utilisateur) ; seule la
// PRÉFÉRENCE de comportement est ici, avec les autres réglages VX46.

/** '' (proposer, défaut) | 'reprendre' | 'cockpit'. */
export function getAppResumePref() {
  const s = storage()
  if (!s) return APP_RESUME_ASK
  try {
    const value = s.getItem(APP_RESUME_KEY)
    return value === APP_RESUME_ALWAYS || value === APP_RESUME_NEVER ? value : APP_RESUME_ASK
  } catch {
    return APP_RESUME_ASK
  }
}

export function setAppResumePref(value) {
  const s = storage()
  if (!s) return
  try {
    if (value === APP_RESUME_ALWAYS || value === APP_RESUME_NEVER) s.setItem(APP_RESUME_KEY, value)
    else s.removeItem(APP_RESUME_KEY) // retour au défaut : on efface la clé.
  } catch { /* stockage indisponible : réglage non persisté sur cet appareil */ }
}

// ── NTMOB12 — Qualité photo (Standard compressé / Original) ─────────────────

/** 'compressed' (défaut) ou 'original'. */
export function getPhotoQualityPref() {
  const s = storage()
  if (!s) return 'compressed'
  try {
    return s.getItem(PHOTO_QUALITY_KEY) === 'original' ? 'original' : 'compressed'
  } catch {
    return 'compressed'
  }
}

export function setPhotoQualityPref(value) {
  const s = storage()
  if (!s) return
  try {
    if (value === 'original') s.setItem(PHOTO_QUALITY_KEY, 'original')
    else s.removeItem(PHOTO_QUALITY_KEY)
  } catch { /* stockage indisponible : réglage non persisté sur cet appareil */ }
}

/**
 * compressPhotoForUpload — point d'entrée UNIQUE pour compresser une photo
 * avant envoi en respectant la préférence « Qualité photo ». Passthrough total
 * si l'utilisateur a choisi « Original » ; sinon délègue à `compressImage`
 * (bord long 1600px, JPEG q0.75 — déjà passthrough-safe pour un non-image).
 * Tous les écrans de capture terrain (checklist NTMOB11, GED NumeriserPage,
 * SAV) doivent passer par CE wrapper plutôt qu'appeler `compressImage`
 * directement, pour que le réglage utilisateur s'applique uniformément.
 */
export async function compressPhotoForUpload(file) {
  // NTMOB17 — le mode économie de données PRIME sur « Original » : sur un
  // forfait mobile, envoyer une photo de 8 Mo n'est jamais le bon choix.
  if (getDataSaverPref()) return compressImage(file)
  if (getPhotoQualityPref() === 'original') return file
  return compressImage(file)
}

// ── NTMOB17 — Mode économie de données ─────────────────────────────────────

export function getDataSaverPref() {
  const s = storage()
  if (!s) return false
  try {
    return s.getItem(DATA_SAVER_KEY) === '1'
  } catch {
    return false
  }
}

export function setDataSaverPref(enabled) {
  const s = storage()
  try {
    if (enabled) s?.setItem(DATA_SAVER_KEY, '1')
    else s?.removeItem(DATA_SAVER_KEY)
  } catch { /* stockage indisponible : appliqué quand même pour la session */ }
  try {
    window.dispatchEvent(new CustomEvent(DATA_SAVER_EVENT, { detail: !!enabled }))
  } catch { /* pas de window (SSR/test node pur) : rien à notifier */ }
  return !!enabled
}

/** Applique le facteur d'économie à une cadence de sondage (ms). */
export function dataSaverInterval(ms, enabled = getDataSaverPref()) {
  return enabled ? ms * DATA_SAVER_POLL_FACTOR : ms
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

// ── EZ9 — Mode « Plein soleil » (terrain) ──────────────────────────────────
// Aucune feuille de style injectée ici : tout le mode est UN attribut sur
// <html> et un bloc de tokens (`design/tokens.css`, patron `[data-density]`).

export function getSunlightPref() {
  const s = storage()
  if (!s) return false
  try {
    return s.getItem(SUNLIGHT_KEY) === '1'
  } catch {
    return false
  }
}

/** Pose (ou retire) l'attribut qui active le bloc de tokens « plein soleil ». */
export function applySunlight(enabled) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (enabled) root.setAttribute('data-sunlight', '1')
  else root.removeAttribute('data-sunlight')
}

export function setSunlightPref(enabled) {
  const s = storage()
  try {
    s?.setItem(SUNLIGHT_KEY, enabled ? '1' : '0')
  } catch { /* stockage indisponible : appliqué quand même pour la session */ }
  applySunlight(enabled)
  return enabled
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
  // EZ9 — le mode terrain survit au rechargement (un technicien qui rouvre
  // l'app au soleil ne doit pas le ré-activer à chaque fois).
  applySunlight(getSunlightPref())
}
