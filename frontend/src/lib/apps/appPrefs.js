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
