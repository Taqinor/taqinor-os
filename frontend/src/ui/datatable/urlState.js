/* ============================================================================
   H33 — Sérialisation de l'état DataTable dans l'URL (sort / filtre / page /
   vue). Logique PURE : prend/rend un objet « params plats » { clé: valeur }
   compatible URLSearchParams (le composant fait le pont avec useSearchParams).
   Survit au rafraîchissement et permet le partage de liens profonds.
   ----------------------------------------------------------------------------
   Encodage compact et lisible :
     sort   = "montant:desc,date:asc"
     q      = "kasri"                 (recherche globale)
     f      = "statut:signe;canal:meta"  (filtres par colonne, valeurs encodées)
     page   = "3"                     (1-based dans l'URL, 0-based en interne)
     size   = "25"
     view   = "a-relancer"
   `prefix` permet plusieurs tables sur la même page (ex. "leads.sort").
   ========================================================================== */

const KEYS = ['sort', 'q', 'f', 'page', 'size', 'view']

function k(prefix, key) {
  return prefix ? `${prefix}.${key}` : key
}

/* ---- Encodage d'une valeur de filtre (tableau ↔ "a|b|c") ---------------- */

function encodeFilterValue(value) {
  if (Array.isArray(value)) return value.map((v) => encodeURIComponent(v)).join('|')
  return encodeURIComponent(String(value))
}
function decodeFilterValue(raw) {
  if (raw.includes('|')) return raw.split('|').map((p) => decodeURIComponent(p))
  return decodeURIComponent(raw)
}

/* ---- sort -------------------------------------------------------------- */

export function encodeSort(sorting) {
  if (!Array.isArray(sorting) || sorting.length === 0) return ''
  return sorting.map((s) => `${s.id}:${s.desc ? 'desc' : 'asc'}`).join(',')
}
export function decodeSort(raw) {
  if (!raw) return []
  return raw
    .split(',')
    .map((part) => {
      const [id, dir] = part.split(':')
      if (!id) return null
      return { id, desc: dir === 'desc' }
    })
    .filter(Boolean)
}

/* ---- column filters ---------------------------------------------------- */

export function encodeFilters(columnFilters) {
  if (!columnFilters) return ''
  const parts = []
  for (const [id, value] of Object.entries(columnFilters)) {
    if (value === '' || value === null || value === undefined) continue
    if (Array.isArray(value) && value.length === 0) continue
    parts.push(`${id}:${encodeFilterValue(value)}`)
  }
  return parts.join(';')
}
export function decodeFilters(raw) {
  if (!raw) return {}
  const out = {}
  for (const part of raw.split(';')) {
    const idx = part.indexOf(':')
    if (idx === -1) continue
    const id = part.slice(0, idx)
    const val = part.slice(idx + 1)
    if (!id) continue
    out[id] = decodeFilterValue(val)
  }
  return out
}

/* ---- état complet ↔ params -------------------------------------------- */

/**
 * Construit un objet de params à fusionner dans l'URL. Les clés vides sont
 * ABSENTES (pour que l'URL reste propre), ce qui permet à l'appelant de les
 * supprimer. `state` = { sorting, query, columnFilters, pageIndex, pageSize,
 * view }.
 */
export function encodeState(state = {}, prefix = '') {
  const params = {}
  const sort = encodeSort(state.sorting)
  const f = encodeFilters(state.columnFilters)
  const q = (state.query || '').trim()

  params[k(prefix, 'sort')] = sort || null
  params[k(prefix, 'q')] = q || null
  params[k(prefix, 'f')] = f || null
  // Page 1 (index 0) est l'état par défaut → on l'omet de l'URL.
  const pageIndex = state.pageIndex | 0
  params[k(prefix, 'page')] = pageIndex > 0 ? String(pageIndex + 1) : null
  params[k(prefix, 'size')] =
    state.pageSize && state.pageSize > 0 ? String(state.pageSize) : null
  params[k(prefix, 'view')] = state.view || null
  return params
}

/**
 * Lit l'état depuis un lecteur de params (`get(key) -> string|null`), p.ex.
 * un URLSearchParams. Renvoie un état partiel — l'appelant fusionne avec ses
 * valeurs par défaut. `pageIndex` est 0-based.
 */
export function decodeState(get, prefix = '') {
  const read = typeof get === 'function' ? get : (key) => get?.get?.(key) ?? null
  const out = {}
  const sort = read(k(prefix, 'sort'))
  if (sort != null) out.sorting = decodeSort(sort)
  const q = read(k(prefix, 'q'))
  if (q != null) out.query = q
  const f = read(k(prefix, 'f'))
  if (f != null) out.columnFilters = decodeFilters(f)
  const page = read(k(prefix, 'page'))
  if (page != null) {
    const n = parseInt(page, 10)
    out.pageIndex = Number.isFinite(n) && n > 0 ? n - 1 : 0
  }
  const size = read(k(prefix, 'size'))
  if (size != null) {
    const n = parseInt(size, 10)
    if (Number.isFinite(n) && n > 0) out.pageSize = n
  }
  const view = read(k(prefix, 'view'))
  if (view != null) out.view = view
  return out
}

/** Liste des clés URL gérées (avec préfixe) — utile pour nettoyer l'URL. */
export function managedKeys(prefix = '') {
  return KEYS.map((key) => k(prefix, key))
}
