// NTUX1 — migration BEST-EFFORT des vues localStorage historiques
// (`hooks/useSavedViews.js`, FG11 : `{name, state}[]` sous la clé
// `taqinor.<ecran>.savedViews`) vers la couche serveur `uxviews.SavedView`
// (NTUX1), au premier chargement d'un écran qui adopte `useServerSavedViews`.
//
// NE BLOQUE JAMAIS : localStorage indisponible, JSON invalide, ou l'API qui
// échoue (réseau, doublon de nom…) n'empêchent jamais l'écran de fonctionner
// — l'échec est avalé et la migration réessaiera simplement au prochain
// montage (le drapeau « déjà migré » n'est posé qu'après un succès complet,
// jamais après une tentative partielle).
//
// Module PUR (aucun import d'`api/uxviewsApi` — l'appelant fournit `create`,
// cf. `useServerSavedViews.js`) : testable en `node --test` sans bundler ni
// node_modules, même patron que `providers/commandActions.js`.

const MIGRATED_FLAG_PREFIX = 'taqinor.uxviews.migrated.'
const LOCAL_KEY_PREFIX = 'taqinor.'
const LOCAL_KEY_SUFFIX = '.savedViews'

function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

// Clé localStorage historique pour un écran donné — miroir de la convention
// documentée par `hooks/useSavedViews.js` (ex. `'taqinor.crm.leads.savedViews'`).
export function localStorageKeyForEcran(ecran) {
  return `${LOCAL_KEY_PREFIX}${ecran}${LOCAL_KEY_SUFFIX}`
}

function readLocalViews(s, ecran) {
  try {
    const raw = s.getItem(localStorageKeyForEcran(ecran))
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

/**
 * migrateLocalSavedViewsForEcran(ecran) — migre UNE fois les vues locales de
 * CET écran vers l'API serveur (un `uxviews.SavedView` PERSONNEL par vue
 * locale — jamais partagée d'office : le partage à l'équipe reste un acte
 * explicite, cf. `views.py definir_par_defaut_role`), puis marque l'écran
 * comme migré pour ne jamais rejouer.
 *
 * @param {string} ecran
 * @param {{create: (payload: {ecran: string, nom: string, configuration: object}) => Promise}} deps
 *   — `create` fourni par l'appelant (`uxviewsApi.createSavedView` en
 *   production, cf. `useServerSavedViews.js`) : ce module reste PUR, sans
 *   import réseau.
 * @returns {Promise<{migrated: number, total?: number, skipped?: boolean}>}
 */
export async function migrateLocalSavedViewsForEcran(ecran, { create } = {}) {
  const s = storage()
  if (!ecran || !s || typeof create !== 'function') return { migrated: 0, skipped: true }

  const flagKey = `${MIGRATED_FLAG_PREFIX}${ecran}`
  let already = null
  try {
    already = s.getItem(flagKey)
  } catch {
    return { migrated: 0, skipped: true }
  }
  if (already) return { migrated: 0, skipped: true }

  const localViews = readLocalViews(s, ecran)
  if (!localViews.length) {
    try { s.setItem(flagKey, '1') } catch { /* best-effort */ }
    return { migrated: 0 }
  }

  let migrated = 0
  for (const view of localViews) {
    if (!view || !view.name) continue
    try {
      // eslint-disable-next-line no-await-in-loop -- migration séquentielle
      // ponctuelle (quelques vues au plus, une seule fois par écran) : la
      // parallélisation n'apporterait rien et compliquerait le rapport
      // migré/total en cas d'échec partiel.
      await create({
        ecran,
        nom: view.name,
        configuration: (view.state && typeof view.state === 'object') ? view.state : {},
      })
      migrated += 1
    } catch {
      // Best-effort — une vue en échec (réseau, doublon de nom…) ne bloque
      // jamais les autres : on continue la boucle.
    }
  }
  // Le drapeau n'est posé QUE si TOUTES les vues locales ont pu être migrées
  // — jamais après un échec partiel (une panne réseau ponctuelle ne doit pas
  // faire perdre silencieusement les vues restantes pour toujours).
  if (migrated === localViews.length) {
    try { s.setItem(flagKey, '1') } catch { /* best-effort */ }
  }
  return { migrated, total: localViews.length }
}
