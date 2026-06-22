// GED13 — logique pure des filtres & recherche avancée de la GED.
// Isolée du composant pour être testable sans rendu : construction des
// paramètres d'API, normalisation des réponses paginées, et filtrage
// client complémentaire (tags + métadonnées custom_data) appliqué par-dessus
// le résultat serveur. Tout le texte UI vit dans le composant ; ici, du data.

// Le backend pagine certains endpoints (DRF) : on accepte `results` OU le
// tableau brut. L'endpoint /semantique renvoie { mode, results }.
export function rows(resp) {
  const d = resp?.data
  if (Array.isArray(d)) return d
  if (Array.isArray(d?.results)) return d.results
  return []
}

// Construit les query-params de l'appel documents selon les filtres actifs.
// - `folder` / `coffre` / `tag` ciblent les filtres serveur (GED8/GED9).
// - `coffre: 'null'` restreint aux documents hors coffre.
// Retourne un objet sans clés vides (axios n'envoie alors rien).
export function buildDocumentParams(filters = {}) {
  const p = {}
  if (filters.folder != null && filters.folder !== '') p.folder = filters.folder
  if (filters.tag != null && filters.tag !== '') p.tag = filters.tag
  if (filters.coffre != null && filters.coffre !== '') p.coffre = filters.coffre
  return p
}

// Normalise la requête de recherche : trim + bornage de longueur. Renvoie ''
// pour une requête vide/espaces (le composant n'appelle alors pas l'API).
export function normalizeQuery(q) {
  if (q == null) return ''
  return String(q).trim().slice(0, 200)
}

// True si au moins un filtre/recherche est actif (sert à basculer entre la vue
// navigateur par défaut et la vue résultats de recherche).
export function hasActiveSearch(state = {}) {
  return Boolean(
    normalizeQuery(state.query)
    || (state.tag != null && state.tag !== '')
    || (state.coffre != null && state.coffre !== '')
  )
}

// Filtrage client complémentaire : restreint une liste de documents à ceux qui
// portent TOUS les tags requis (`tagIds`) et dont les métadonnées custom_data
// matchent les paires `meta` ({ code: valeur }). Le filtre serveur reste la
// source principale ; ceci affine sans nouvel appel (ex. multi-tags).
export function filterDocuments(documents, { tagIds = [], meta = {} } = {}) {
  const list = Array.isArray(documents) ? documents : []
  const wantTags = (tagIds || []).map(Number).filter((n) => !Number.isNaN(n))
  const metaEntries = Object.entries(meta || {}).filter(([, v]) => v !== '' && v != null)
  return list.filter((doc) => {
    if (wantTags.length) {
      const docTagIds = new Set((doc.tags || []).map((t) => Number(t.id)))
      if (!wantTags.every((id) => docTagIds.has(id))) return false
    }
    if (metaEntries.length) {
      const cd = doc.custom_data || {}
      for (const [code, val] of metaEntries) {
        const got = cd[code]
        if (String(got ?? '').toLowerCase() !== String(val).toLowerCase()) {
          return false
        }
      }
    }
    return true
  })
}
