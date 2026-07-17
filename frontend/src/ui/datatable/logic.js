/* ============================================================================
   H31/H32/H33 — Logique PURE du moteur DataTable (aucune dépendance React/DOM)
   ----------------------------------------------------------------------------
   Tri, filtres (global + par colonne), pagination, réducteur d'état des
   colonnes, mise en évidence des correspondances et calcul des sous-totaux.
   Tout ici est testable au node:test (voir logic.test.mjs). Le composant
   <DataTable> consomme ces fonctions ; il ne réimplémente jamais cette logique.
   100 % additif — aucun écran existant n'est modifié.
   ========================================================================== */

import { toNumber } from '../../lib/format.js'

/* ---------------------------------------------------------------- Tri ---- */

/** Normalise une valeur de cellule pour comparaison (nombre, date, texte). */
export function normalizeForSort(value) {
  if (value === null || value === undefined || value === '') {
    return { kind: 'empty', v: null }
  }
  if (value instanceof Date) return { kind: 'number', v: value.getTime() }
  if (typeof value === 'boolean') return { kind: 'number', v: value ? 1 : 0 }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? { kind: 'number', v: value } : { kind: 'empty', v: null }
  }
  const n = toNumber(value)
  // Chaîne purement numérique (« 1 234,56 ») → tri numérique
  if (n !== null && /^[\s\d.,%+-]+$/.test(String(value))) {
    return { kind: 'number', v: n }
  }
  return { kind: 'text', v: String(value).toLocaleLowerCase('fr') }
}

/**
 * Compare deux valeurs brutes. Les vides sont toujours rejetés en fin de liste
 * (quel que soit le sens). Renvoie un entier < 0 / 0 / > 0.
 */
export function compareValues(a, b) {
  const na = normalizeForSort(a)
  const nb = normalizeForSort(b)
  if (na.kind === 'empty' && nb.kind === 'empty') return 0
  if (na.kind === 'empty') return 1 // a vide → après
  if (nb.kind === 'empty') return -1
  if (na.kind === 'number' && nb.kind === 'number') {
    return na.v < nb.v ? -1 : na.v > nb.v ? 1 : 0
  }
  return String(na.v).localeCompare(String(nb.v), 'fr', { numeric: true, sensitivity: 'base' })
}

/**
 * Tri multi-colonnes stable. `sorting` = [{ id, desc }] (ordre = priorité).
 * `accessor(row, id)` extrait la valeur d'une cellule. Ne mute pas l'entrée.
 */
export function sortRows(rows, sorting, accessor) {
  if (!Array.isArray(rows) || !sorting || sorting.length === 0) return rows ? [...rows] : []
  const get = accessor || ((row, id) => row?.[id])
  // Décoration index pour stabilité explicite face aux égalités multi-clés.
  return rows
    .map((row, index) => ({ row, index }))
    .sort((x, y) => {
      for (const { id, desc } of sorting) {
        const c = compareValues(get(x.row, id), get(y.row, id))
        if (c !== 0) return desc ? -c : c
      }
      return x.index - y.index
    })
    .map((d) => d.row)
}

/** Bascule le tri d'une colonne (clic en-tête) : asc → desc → aucun. */
export function toggleSort(sorting, id, { multi = false } = {}) {
  const list = Array.isArray(sorting) ? sorting : []
  const existing = list.find((s) => s.id === id)
  if (!multi) {
    if (!existing) return [{ id, desc: false }]
    if (!existing.desc) return [{ id, desc: true }]
    return []
  }
  // Mode multi (Maj+clic) : ajoute / cycle sans toucher aux autres colonnes.
  if (!existing) return [...list, { id, desc: false }]
  if (!existing.desc) return list.map((s) => (s.id === id ? { id, desc: true } : s))
  return list.filter((s) => s.id !== id)
}

/* ------------------------------------------------------------ Filtres ---- */

/** Normalise une chaîne pour recherche : minuscule + sans accents. */
export function foldText(value) {
  return String(value ?? '')
    .toLocaleLowerCase('fr')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}

/** Vrai si `foldedNeedle` (déjà replié) est présent dans la valeur de cellule. */
export function matchesText(cellValue, foldedNeedle) {
  if (!foldedNeedle) return true
  return foldText(cellValue).includes(foldedNeedle)
}

/**
 * Prédicat de filtre global : la ligne passe si l'un de ses champs `columnIds`
 * contient la recherche. `accessor(row, id)` extrait la valeur.
 */
export function globalFilterPredicate(row, query, columnIds, accessor) {
  const needle = foldText(query).trim()
  if (!needle) return true
  const get = accessor || ((r, id) => r?.[id])
  return columnIds.some((id) => matchesText(get(row, id), needle))
}

/**
 * Prédicat de filtre par colonne. `columnFilters` = { [id]: value }.
 * Valeur tableau → appartenance (multi-select) ; sinon → sous-chaîne.
 */
export function columnFilterPredicate(row, columnFilters, accessor) {
  if (!columnFilters) return true
  const get = accessor || ((r, id) => r?.[id])
  return Object.entries(columnFilters).every(([id, filter]) => {
    if (filter === '' || filter === null || filter === undefined) return true
    const cell = get(row, id)
    if (Array.isArray(filter)) {
      if (filter.length === 0) return true
      const cellFolded = foldText(cell)
      return filter.some((f) => foldText(f) === cellFolded)
    }
    return matchesText(cell, foldText(filter).trim())
  })
}

/** Applique global + par-colonne en une passe. Ne mute pas l'entrée. */
export function filterRows(rows, { query = '', columnFilters = {}, globalColumns = [] } = {}, accessor) {
  if (!Array.isArray(rows)) return []
  return rows.filter(
    (row) =>
      globalFilterPredicate(row, query, globalColumns, accessor) &&
      columnFilterPredicate(row, columnFilters, accessor),
  )
}

/* ----------------------------------------------- Surlignage recherche ---- */

/**
 * Découpe `text` en segments {text, match} selon `query` (insensible
 * accents/casse). Utilisé pour le rendu surligné. Sans correspondance →
 * un seul segment non surligné.
 */
export function highlightSegments(text, query) {
  const str = String(text ?? '')
  const needle = foldText(query).trim()
  if (!needle || !str) return [{ text: str, match: false }]
  const foldedStr = foldText(str)
  const segments = []
  let i = 0
  while (i < str.length) {
    const found = foldedStr.indexOf(needle, i)
    if (found === -1) {
      segments.push({ text: str.slice(i), match: false })
      break
    }
    if (found > i) segments.push({ text: str.slice(i, found), match: false })
    segments.push({ text: str.slice(found, found + needle.length), match: true })
    i = found + needle.length
  }
  return segments.length ? segments : [{ text: str, match: false }]
}

/* --------------------------------------------------------- Pagination ---- */

/** Nombre total de pages (>= 1). pageSize <= 0 → tout sur une page. */
export function pageCount(total, pageSize) {
  if (!pageSize || pageSize <= 0) return 1
  return Math.max(1, Math.ceil((total || 0) / pageSize))
}

/** Borne un index de page dans [0, pageCount-1]. */
export function clampPageIndex(pageIndex, total, pageSize) {
  const last = pageCount(total, pageSize) - 1
  return Math.min(Math.max(0, pageIndex | 0), last)
}

/**
 * Métadonnées d'une page : indices 1-based de la tranche affichée + total.
 * `from`/`to` sont 0 quand la liste est vide (libellé « 0 sur 0 »).
 */
export function pageRange(pageIndex, pageSize, total) {
  const t = total || 0
  if (t === 0) return { from: 0, to: 0, total: 0 }
  if (!pageSize || pageSize <= 0) return { from: 1, to: t, total: t }
  const idx = clampPageIndex(pageIndex, t, pageSize)
  const from = idx * pageSize + 1
  const to = Math.min(t, from + pageSize - 1)
  return { from, to, total: t }
}

/** Libellé français « X–Y sur N » (tiret demi-cadratin). */
export function frenchPageLabel(pageIndex, pageSize, total) {
  const { from, to, total: t } = pageRange(pageIndex, pageSize, total)
  if (t === 0) return '0 sur 0'
  return `${from}–${to} sur ${t}`
}

/** Tranche de lignes pour la page courante (client-side). */
export function paginateRows(rows, pageIndex, pageSize) {
  if (!Array.isArray(rows)) return []
  if (!pageSize || pageSize <= 0) return rows
  const idx = clampPageIndex(pageIndex, rows.length, pageSize)
  const start = idx * pageSize
  return rows.slice(start, start + pageSize)
}

/* --------------------------------------- Réducteur d'état des colonnes ---- */

/**
 * État des colonnes : ordre, visibilité, épinglage, largeurs.
 * `columns` = [{ id, ... }] (définitions). Renvoie un état initial dérivé.
 */
export function initColumnState(columns = []) {
  return {
    order: columns.map((c) => c.id),
    hidden: {},
    pinned: {},
    widths: {},
  }
}

/** Déplace `fromId` juste avant `toId` dans l'ordre (réorganisation colonnes). */
export function moveItem(order, fromId, toId) {
  if (fromId === toId) return [...order]
  const next = order.filter((id) => id !== fromId)
  const at = next.indexOf(toId)
  if (at === -1) return [...next, fromId]
  next.splice(at, 0, fromId)
  return next
}

/** Réducteur pur de l'état des colonnes (show/hide, reorder, resize, pin). */
export function columnStateReducer(state, action) {
  switch (action.type) {
    case 'toggleVisibility': {
      const hidden = { ...state.hidden }
      if (hidden[action.id]) delete hidden[action.id]
      else hidden[action.id] = true
      return { ...state, hidden }
    }
    case 'setVisibility': {
      const hidden = { ...state.hidden }
      if (action.visible) delete hidden[action.id]
      else hidden[action.id] = true
      return { ...state, hidden }
    }
    case 'reorder': {
      const order = moveItem(state.order, action.fromId, action.toId)
      return { ...state, order }
    }
    case 'resize': {
      const w = Math.max(action.min ?? 60, action.width | 0)
      return { ...state, widths: { ...state.widths, [action.id]: w } }
    }
    case 'pin': {
      const pinned = { ...state.pinned }
      if (action.side) pinned[action.id] = action.side // 'left' | 'right'
      else delete pinned[action.id]
      return { ...state, pinned }
    }
    case 'reset':
      return initColumnState(action.columns || [])
    default:
      return state
  }
}

/**
 * Colonnes visibles dans l'ordre courant, épinglées à gauche d'abord.
 * `columns` = définitions ; renvoie les définitions ordonnées + augmentées
 * de { pinned, width } d'après l'état.
 */
export function resolveColumns(columns, state) {
  const byId = new Map(columns.map((c) => [c.id, c]))
  const ordered = state.order.map((id) => byId.get(id)).filter(Boolean)
  // Colonnes ajoutées après l'init et absentes de l'ordre → en fin.
  for (const c of columns) if (!state.order.includes(c.id)) ordered.push(c)
  const visible = ordered.filter((c) => !state.hidden[c.id])
  const decorated = visible.map((c) => ({
    ...c,
    pinned: state.pinned[c.id] || c.pinned || null,
    width: state.widths[c.id] ?? c.width ?? null,
  }))
  // Épinglées à gauche en tête, à droite en queue, le reste au milieu.
  const left = decorated.filter((c) => c.pinned === 'left')
  const right = decorated.filter((c) => c.pinned === 'right')
  const mid = decorated.filter((c) => c.pinned !== 'left' && c.pinned !== 'right')
  return [...left, ...mid, ...right]
}

/* --------------------------------------------- Sous-totaux / résumé ------ */

/**
 * Agrège des colonnes numériques sur un ensemble de lignes.
 * `aggregations` = { [id]: 'sum' | 'avg' | 'count' | fn(values,rows)->number }.
 * Renvoie { [id]: number|null }. Utilise toNumber pour parser MAD/fr-FR.
 */
export function summarize(rows, aggregations, accessor) {
  const get = accessor || ((r, id) => r?.[id])
  const out = {}
  if (!Array.isArray(rows) || !aggregations) return out
  for (const [id, agg] of Object.entries(aggregations)) {
    const values = rows.map((r) => toNumber(get(r, id))).filter((n) => n !== null)
    if (typeof agg === 'function') {
      out[id] = agg(values, rows)
    } else if (agg === 'count') {
      out[id] = rows.length
    } else if (agg === 'avg') {
      out[id] = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
    } else {
      // 'sum' par défaut
      out[id] = values.reduce((a, b) => a + b, 0)
    }
  }
  return out
}

/** Décompose un total TTC en HT + TVA au taux donné (défaut 20 %). */
export function splitTVA(totalTTC, taux = 20) {
  const ttc = toNumber(totalTTC)
  if (ttc === null) return { ht: null, tva: null, ttc: null }
  const ht = ttc / (1 + taux / 100)
  return { ht, tva: ttc - ht, ttc }
}

/* ------------------------------------------------ Sélection (bulk) ------- */

/** Bascule la sélection d'une ligne (par clé). */
export function toggleSelected(selected, key) {
  const next = { ...selected }
  if (next[key]) delete next[key]
  else next[key] = true
  return next
}

/** Sélectionne / désélectionne toutes les clés fournies. */
export function setAllSelected(selected, keys, value) {
  const next = { ...selected }
  for (const k of keys) {
    if (value) next[k] = true
    else delete next[k]
  }
  return next
}

/** 'all' | 'some' | 'none' selon les clés visibles sélectionnées. */
export function selectionState(selected, keys) {
  if (!keys.length) return 'none'
  let count = 0
  for (const k of keys) if (selected[k]) count++
  if (count === 0) return 'none'
  if (count === keys.length) return 'all'
  return 'some'
}

/* ------------------------------------- Épinglage / largeurs colonnes ----- */

/**
 * H130 — Décalages CUMULÉS (px) des colonnes épinglées, depuis chaque bord.
 * Renvoie { left: { [id]: px }, right: { [id]: px } } où chaque valeur est la
 * distance du bord (left/right) à laquelle figer la colonne, pour que plusieurs
 * colonnes épinglées du même côté se collent l'une à l'autre sans chevauchement.
 * `resolvedColumns` est déjà ordonné (gauche → milieu → droite via resolveColumns).
 * `leadOffset` = largeur de la gouttière de sélection à gauche (case à cocher).
 * `fallbackWidth` = largeur par défaut d'une colonne sans `width` explicite.
 * `actionsWidth` = largeur réservée à la colonne actions épinglée à droite.
 */
export function pinnedEdgeOffsets(
  resolvedColumns = [],
  { leadOffset = 0, fallbackWidth = 160, actionsWidth = 0 } = {},
) {
  const left = {}
  const right = {}
  let accLeft = leadOffset
  for (const c of resolvedColumns) {
    if (c.pinned === 'left') {
      left[c.id] = accLeft
      accLeft += c.width ?? fallbackWidth
    }
  }
  // Côté droit : on cumule de la droite vers la gauche (la colonne actions, si
  // épinglée, occupe le tout premier cran à droite).
  let accRight = actionsWidth
  for (let i = resolvedColumns.length - 1; i >= 0; i--) {
    const c = resolvedColumns[i]
    if (c.pinned === 'right') {
      right[c.id] = accRight
      accRight += c.width ?? fallbackWidth
    }
  }
  return { left, right }
}

/**
 * O166 — Variables CSS de largeur de colonne, calculées UNE fois par rendu.
 * Renvoie { vars, get } : `vars` = objet style (`--dt-col-<id>: 200px`) à poser
 * sur le conteneur ; `get(id)` = `var(--dt-col-<id>)` pour la cellule. Pousser la
 * largeur via variable évite de relire/recalculer la taille par cellule à chaque
 * rendu (redimensionnement fluide ~60 fps). Les colonnes sans largeur explicite
 * n'émettent pas de variable (largeur auto par le navigateur).
 */
export function columnWidthVars(resolvedColumns = []) {
  const vars = {}
  for (const c of resolvedColumns) {
    if (c.width != null) vars[`--dt-col-${c.id}`] = typeof c.width === 'number' ? `${c.width}px` : c.width
  }
  const get = (id) => (vars[`--dt-col-${id}`] !== undefined ? `var(--dt-col-${id})` : undefined)
  return { vars, get }
}

/* --------------------------------------------- Groupement (NTUX19) ------- */

/**
 * NTUX19 — Regroupe des lignes par la valeur d'une colonne. Conserve l'ordre
 * de PREMIÈRE APPARITION des groupes (pas un tri alphabétique — stable et
 * prévisible vis-à-vis du tri déjà appliqué en amont). `accessor(row, id)`
 * extrait la valeur de regroupement ; une valeur vide/null/undefined
 * regroupe sous la clé `''` (rendue « Non renseigné » côté composant).
 * Renvoie `[{ key, rows }]`. Ne mute pas l'entrée.
 */
export function groupRows(rows, groupById, accessor) {
  const get = accessor || ((r, id) => r?.[id])
  const groups = []
  const byKey = new Map()
  for (const row of rows || []) {
    const raw = get(row, groupById)
    const key = raw === null || raw === undefined || raw === '' ? '' : String(raw)
    let g = byKey.get(key)
    if (!g) {
      g = { key, rows: [] }
      byKey.set(key, g)
      groups.push(g)
    }
    g.rows.push(row)
  }
  return groups
}

/* ----------------------------------------- Virtualisation (windowing) ---- */

/**
 * Fenêtre de lignes à rendre pour une liste virtualisée (hauteur de ligne
 * fixe). Renvoie { startIndex, endIndex, paddingTop, paddingBottom }.
 * `overscan` = lignes hors écran rendues de part et d'autre (anti-flash).
 */
export function computeWindow({ scrollTop, viewportHeight, rowHeight, rowCount, overscan = 6 }) {
  const h = rowHeight > 0 ? rowHeight : 1
  const total = Math.max(0, rowCount | 0)
  if (total === 0) {
    return { startIndex: 0, endIndex: 0, paddingTop: 0, paddingBottom: 0 }
  }
  const first = Math.floor((scrollTop || 0) / h)
  const visibleCount = Math.ceil((viewportHeight || 0) / h)
  const startIndex = Math.max(0, first - overscan)
  const endIndex = Math.min(total, first + visibleCount + overscan)
  return {
    startIndex,
    endIndex,
    paddingTop: startIndex * h,
    paddingBottom: Math.max(0, (total - endIndex) * h),
  }
}
