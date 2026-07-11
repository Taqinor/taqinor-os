// VX58 — Préchargement au survol/focus des destinations chaudes de la Sidebar.
//
// Constat : zéro prefetch aujourd'hui — chaque clic Sidebar paie le chunk lazy
// PUIS le fetch de données, EN SÉRIE. En déclenchant le MÊME import dynamique
// que le routeur dès le survol/focus du lien (avant le clic), le chunk est
// déjà en cache navigateur quand React Router le demande réellement.
//
// Source unique : ces imports dynamiques sont des COPIES EXACTES de ceux déjà
// déclarés dans `router/index.jsx` / `features/<module>/module.config.jsx`
// (Vite déduplique le module au bundling — un seul chunk produit, importé par
// deux points d'entrée). Ne JAMAIS diverger de ces chemins : si une page
// bouge de dossier, mettre à jour les DEUX endroits.
//
// Garde adaptative : sur connexion contrainte (Data Saver ou 2G/slow-2G), le
// prefetch ne coûte rien à l'utilisateur qui en a le plus besoin — no-op sur
// Safari/navigateurs sans Network Information API (feature-detect).
export function shouldSkipPrefetch(nav = (typeof navigator !== 'undefined' ? navigator.connection : undefined)) {
  if (!nav) return false
  if (nav.saveData) return true
  if (nav.effectiveType === '2g' || nav.effectiveType === 'slow-2g') return true
  return false
}

// path Sidebar (`item.to`) → chargeur de chunk (identique à l'import lazy du
// routeur). 8 destinations les plus fréquentes du menu de tête.
export const PREFETCH_MAP = {
  '/dashboard': () => import('../pages/Dashboard'),
  '/activites': () => import('../pages/activities/MesActivitesPage'),
  '/crm': () => import('../pages/crm/ClientList'),
  '/crm/leads': () => import('../pages/crm/leads/LeadsPage'),
  '/ventes/devis': () => import('../pages/ventes/DevisList'),
  '/ventes/factures': () => import('../pages/ventes/FactureList'),
  '/stock': () => import('../pages/stock/StockList'),
  '/chantiers': () => import('../pages/installations/InstallationsPage'),
}

// Chaque destination n'est chargée qu'UNE fois (le navigateur cache déjà le
// chunk, mais on évite aussi de ré-invoquer inutilement la fonction import()).
const prefetched = new Set()

/**
 * Déclenche le prefetch du chunk associé à `to`, si connu et pas déjà fait.
 * No-op silencieux : mauvais chemin, garde adaptative active, ou import déjà
 * en cache — jamais d'exception remontée à l'appelant (un survol ne doit
 * jamais casser la navigation).
 */
export function prefetchRoute(to, { connection } = {}) {
  if (prefetched.has(to)) return
  const loader = PREFETCH_MAP[to]
  if (!loader) return
  if (shouldSkipPrefetch(connection)) return
  prefetched.add(to)
  // Erreur réseau/chunk absent : ignorée, le clic réel refera la tentative
  // normale via React Router (comportement inchangé en cas d'échec ici).
  loader().catch(() => {})
}

// Exposé pour les tests (réinitialise l'état "déjà préchargé").
export function _resetPrefetchCacheForTests() {
  prefetched.clear()
}
