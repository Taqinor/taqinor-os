// ODY2 — Préférences PERSONNELLES de la grille d'apps (favoris, récents,
// ordre), extraites en UN module partagé.
// ----------------------------------------------------------------------------
// Raison d'être : la contrainte du Groupe ODY interdit une 2ᵉ clé localStorage
// de favoris. `AppLauncher.jsx` (VX9) et `PinnedApps.jsx` (VX10) partagent déjà
// `taqinor.sidebar.pinned` en la redéclarant chacun de leur côté ; le Menu
// d'accueil (ODY2) étant la TROISIÈME surface, on centralise ici les CLÉS et
// leurs accès défensifs plutôt que de recopier une constante une fois de plus.
// Toute surface qui lit/écrit favoris, récents ou ordre passe par ce module.
//
// Accès toujours défensifs (motif `COLLAPSE_KEY` de Layout.jsx) : jamais
// d'exception si le stockage est indisponible (mode privé, SSR, quota).

/** Favoris d'apps — MÊME clé que VX9 (AppLauncher) et VX10 (PinnedApps). */
export const PINNED_KEY = 'taqinor.sidebar.pinned'
/** Apps récemment ouvertes (propre au lanceur/menu, distinct de `taqinor.cmdk.recent`). */
export const RECENT_KEY = 'taqinor.launcher.recent'
/** ODY13 — ordre personnel de la grille (liste de clés de module). */
export const ORDER_KEY = 'taqinor.apps.order'
/** ODY29 — préfixe des routes de REPRISE (une clé par app ET par utilisateur).
 *  Volontairement en sessionStorage, pas en localStorage : « reprendre où j'en
 *  étais » a du sens dans la session de travail en cours, pas trois jours plus
 *  tard sur un écran devenu périmé. */
export const RESUME_PREFIX = 'taqinor.apps.resume'
/** ODY32 — dernière app OUVERTE de la session : sert au retour de focus sur la
 *  tuile d'origine quand on ressort au Menu d'accueil. Ce n'est PAS une donnée
 *  métier (juste l'endroit où rendre le clavier), donc ni utilisateur ni
 *  persistance longue — une clé de session suffit. */
export const LAST_APP_KEY = 'taqinor.apps.derniere'

/** Nombre de « Récents » affichés (contrat ODY2 : 3). */
export const RECENT_MAX = 3

function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

export function readList(key) {
  const s = storage()
  if (!s) return []
  try {
    const raw = s.getItem(key)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr.filter((k) => typeof k === 'string') : []
  } catch {
    return []
  }
}

export function writeList(key, list) {
  const s = storage()
  if (!s) return
  try {
    s.setItem(key, JSON.stringify(list))
  } catch { /* stockage indisponible : état en mémoire seulement */ }
}

export function readPinned() {
  return readList(PINNED_KEY)
}

/** Écrit les favoris ET notifie les autres surfaces montées (PinnedApps écoute
 *  déjà `taqinor:pinned-changed` — même événement, jamais un second canal). */
export function writePinned(list) {
  writeList(PINNED_KEY, list)
  try {
    window.dispatchEvent(new CustomEvent('taqinor:pinned-changed'))
  } catch { /* environnement sans window : silencieux */ }
}

export function readRecent() {
  return readList(RECENT_KEY)
}

/** Place `key` en tête des récents (dédoublonné), tronqué à RECENT_MAX. */
export function pushRecent(key) {
  if (!key) return readRecent()
  const next = [key, ...readRecent().filter((k) => k !== key)].slice(0, RECENT_MAX)
  writeList(RECENT_KEY, next)
  return next
}

export function readOrder() {
  return readList(ORDER_KEY)
}

export function writeOrder(list) {
  writeList(ORDER_KEY, list)
  try {
    window.dispatchEvent(new CustomEvent('taqinor:apps-order-changed'))
  } catch { /* environnement sans window : silencieux */ }
}

// ── ODY29 — mémoire de reprise, par app ET par utilisateur ─────────────────
// Odoo perd l'endroit où vous étiez dès que vous changez d'app. Ici, chaque app
// se souvient de sa dernière route DE LA SESSION ; la grille peut alors
// proposer « Reprendre ». Deux comptes qui se succèdent sur le même poste ne
// se marchent jamais dessus : l'identifiant utilisateur fait partie de la clé.
// Accès défensifs identiques au reste du fichier (mode privé, quota, SSR).

function sessionStore() {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null
  } catch {
    return null
  }
}

/** Clé de reprise d'une app pour un utilisateur donné (`anon` si non résolu). */
export function resumeKey(appKey, userId) {
  return `${RESUME_PREFIX}:${userId ?? 'anon'}:${appKey}`
}

/** Dernière route connue de `appKey` pour cet utilisateur, ou '' si aucune. */
export function readResume(appKey, userId) {
  const s = sessionStore()
  if (!s || !appKey) return ''
  try {
    const value = s.getItem(resumeKey(appKey, userId))
    // Une valeur qui n'est pas un chemin absolu est ignorée : on ne navigue
    // jamais vers ce qu'on n'a pas écrit soi-même.
    return typeof value === 'string' && value.startsWith('/') ? value : ''
  } catch {
    return ''
  }
}

/** Mémorise `path` comme dernière route de `appKey`. */
export function writeResume(appKey, userId, path) {
  const s = sessionStore()
  if (!s || !appKey || typeof path !== 'string' || !path.startsWith('/')) return
  try {
    s.setItem(resumeKey(appKey, userId), path)
  } catch { /* stockage indisponible : pas de reprise, jamais d'exception */ }
}

/** ODY32 — clé de la dernière app ouverte ('' si aucune dans cette session). */
export function readLastApp() {
  const s = sessionStore()
  if (!s) return ''
  try {
    return s.getItem(LAST_APP_KEY) || ''
  } catch {
    return ''
  }
}

export function writeLastApp(appKey) {
  const s = sessionStore()
  if (!s || !appKey) return
  try {
    s.setItem(LAST_APP_KEY, appKey)
  } catch { /* stockage indisponible : pas de retour de focus, jamais d'erreur */ }
}

/**
 * resumeTarget — destination de reprise UTILISABLE : la route mémorisée, ou ''
 * si elle est absente ou identique au cockpit (proposer « Reprendre » vers
 * l'écran où le clic mène déjà serait un faux choix).
 */
export function resumeTarget(appKey, userId, cockpit) {
  const memoire = readResume(appKey, userId)
  return memoire && memoire !== cockpit ? memoire : ''
}

/**
 * applyOrder — réordonne `apps` selon `order` (liste de clés). Les apps
 * absentes de `order` gardent leur position relative d'origine, À LA FIN :
 * une app nouvellement installée apparaît toujours, jamais perdue parce
 * qu'elle manque à un ordre enregistré il y a six mois.
 */
export function applyOrder(apps, order) {
  if (!order?.length) return apps
  const byKey = new Map(apps.map((a) => [a.key, a]))
  const ordered = order.map((k) => byKey.get(k)).filter(Boolean)
  const seen = new Set(ordered.map((a) => a.key))
  return [...ordered, ...apps.filter((a) => !seen.has(a.key))]
}
