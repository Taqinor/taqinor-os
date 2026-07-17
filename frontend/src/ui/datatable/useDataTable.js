import { useCallback, useEffect, useMemo, useReducer, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
} from '@tanstack/react-table'
import {
  compareValues, toggleSort,
  globalFilterPredicate, columnFilterPredicate, paginateRows, pageRange,
  initColumnState, columnStateReducer, resolveColumns,
  toggleSelected, setAllSelected, selectionState, summarize,
} from './logic.js'
import { encodeState, decodeState } from './urlState.js'

/* ============================================================================
   H31/H33 — Hook d'orchestration du DataTable (état + persistance URL).
   ----------------------------------------------------------------------------
   P171 — MOTEUR migré sur `@tanstack/react-table` : `useReactTable` détient
   désormais l'état (tri / filtres / sélection) et exécute le pipeline de lignes
   (cœur → filtre → tri) via son row-model. Le COMPORTEMENT reste byte-pour-byte
   identique parce que le tri et les filtres sont branchés sur les fonctions
   PURES de `logic.js` (`compareValues`, `globalFilterPredicate`,
   `columnFilterPredicate`) en `sortingFn`/`filterFn`/`globalFilterFn`. La
   pagination, les sous-totaux, l'état des colonnes et l'identité de ligne
   continuent d'utiliser les helpers purs de `logic.js`, si bien que l'API
   PUBLIQUE renvoyée par ce hook (clés + sémantique) est inchangée et que
   <DataTable> rend exactement le même markup.

   - Tri / filtres / pagination 100 % côté client par défaut.
   - SEAM SERVEUR : `manualSorting`/`manualFiltering`/`manualPagination` court-
     circuitent le calcul local et exposent les callbacks au consommateur, qui
     fournit alors `rows` déjà triées/filtrées + `rowCount`.
   - Persistance URL optionnelle (`persistToUrl` + `urlKey`) via useSearchParams.
   ========================================================================== */

const ACCESSOR = (row, id) => row?.[id]

/* Filtre par colonne au sens « ensemble » : `columnFilters` est un objet
   { [id]: valeur } côté API publique. On l'évalue ligne par ligne avec le
   prédicat pur, branché en `globalFilterFn` (une seule passe sur toutes les
   colonnes), afin de préserver exactement la sémantique de `columnFilterPredicate`
   (sous-chaîne repliée + appartenance multi-select). */

export function useDataTable({
  data = [],
  columns = [],
  getRowId = (row, i) => row?.id ?? i,
  globalColumns,
  initialSorting = [],
  initialColumnFilters = {},
  initialPageSize = 25,
  initialView = null,
  accessor = ACCESSOR,
  manualSorting = false,
  manualFiltering = false,
  manualPagination = false,
  rowCount: manualRowCount,
  summary = null, // { [colId]: 'sum'|'avg'|'count'|fn }
  persistToUrl = false,
  urlKey = '',
  // NTUX16 — état des colonnes initial injecté par l'appelant (ex.
  // `useColumnPrefs(ecran)`, localStorage) au lieu du défaut dérivé de
  // `columns` — lu UNE SEULE FOIS au montage (fonction d'init de useReducer,
  // comme avant). Non fourni (~79 écrans existants) → comportement
  // strictement inchangé. `onColumnStateChange` est notifié APRÈS chaque
  // changement d'état de colonnes (show/hide/reorder/resize/pin), pour la
  // persistance légère (indépendante des vues nommées NTUX1/2).
  initialColumnState,
  onColumnStateChange,
} = {}) {
  // useSearchParams est TOUJOURS appelé (règle des hooks) ; on n'écrit dans
  // l'URL que si `persistToUrl`. Nécessite un <Router> dans l'arbre ; le
  // showcase /ui en a un.
  const [searchParams, setSearchParams] = useSearchParams()

  // État initial : URL (si persistance) sinon valeurs fournies. Lu une seule
  // fois au montage : ensuite l'état local fait foi et écrit dans l'URL.
  const urlState = useMemo(
    () => (persistToUrl ? decodeState(searchParams, urlKey) : {}),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  const [sorting, setSorting] = useState(urlState.sorting ?? initialSorting)
  const [query, setQuery] = useState(urlState.query ?? '')
  const [columnFilters, setColumnFilters] = useState(urlState.columnFilters ?? initialColumnFilters)
  const [pageIndex, setPageIndex] = useState(urlState.pageIndex ?? 0)
  const [pageSize, setPageSize] = useState(urlState.pageSize ?? initialPageSize)
  const [view, setView] = useState(urlState.view ?? initialView)
  const [selected, setSelected] = useState({})

  const [columnState, dispatchColumns] = useReducer(
    columnStateReducer,
    columns,
    // NTUX16 — la fonction d'init ne s'exécute qu'UNE FOIS (montage) : un
    // `initialColumnState` fourni (préférences localStorage) prime sur le
    // défaut dérivé des colonnes ; les colonnes ajoutées après coup restent
    // fusionnées en fin de liste par `resolveColumns` (comportement déjà
    // en place, inchangé).
    (cols) => initialColumnState || initColumnState(cols),
  )

  // NTUX16 — notifie l'appelant après chaque changement d'état de colonnes
  // (show/hide/reorder/resize/pin), pour une auto-persistance légère par
  // écran (localStorage, `useColumnPrefs`). Non fourni → aucun effet.
  useEffect(() => {
    if (onColumnStateChange) onColumnStateChange(columnState)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne réagit qu'aux changements de columnState, pas à l'identité du callback
  }, [columnState])

  // Colonnes balayées par la recherche globale (par défaut : toutes).
  const globalIds = useMemo(
    () => globalColumns ?? columns.map((c) => c.id),
    [globalColumns, columns],
  )

  /* ---- Définitions de colonnes pour react-table ----
     Le moteur a besoin d'une définition d'accès par colonne. On mappe l'`id` et
     l'accessor de chaque colonne métier vers une `accessorFn` qui réutilise le
     même `accessor(row, id)` que la logique pure, afin que le tri et les filtres
     voient EXACTEMENT les mêmes valeurs de cellule qu'auparavant. */
  const tableColumns = useMemo(
    () =>
      columns.map((c) => ({
        id: c.id,
        accessorFn: (row) => accessor(row, c.id),
      })),
    [columns, accessor],
  )

  /* ---- Tri pur (parité) : comparateur stable basé sur `compareValues` ----
     react-table appelle `sortingFn(rowA, rowB, columnId)` puis applique le sens
     desc lui-même ; on renvoie donc toujours l'ordre ASCENDANT. La STABILITÉ et
     le rejet des vides en fin de liste sont garantis par `compareValues`
     (vides toujours « après ») et par le tri stable du moteur. */
  const sortingFns = useMemo(() => ({
    dtCompare: (rowA, rowB, columnId) =>
      compareValues(rowA.getValue(columnId), rowB.getValue(columnId)),
  }), [])

  /* ---- Filtre global pur (parité) ----
     Évalue le filtre global ET les filtres par colonne en une passe avec les
     prédicats purs, sur la LIGNE BRUTE (`row.original`) — identité parfaite avec
     l'ancien `filterRows`. */
  const globalFilterFn = useCallback(
    (row) =>
      globalFilterPredicate(row.original, query, globalIds, accessor) &&
      columnFilterPredicate(row.original, columnFilters, accessor),
    [query, globalIds, columnFilters, accessor],
  )

  // Identité stable du filtre global : ne change que quand `query` ou
  // `columnFilters` change, pour ne pas recalculer le modèle filtré à chaque
  // rendu (le moteur mémoïse sur cette valeur). Toujours TRUTHY afin que le
  // moteur exécute systématiquement `globalFilterFn` (qui décide réellement).
  const globalFilterValue = useMemo(
    () => ({ query, columnFilters }),
    [query, columnFilters],
  )

  // TanStack Table's `useReactTable()` returns functions the React Compiler
  // cannot safely memoize; this is inherent to the library, not fixable here.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns: tableColumns,
    state: {
      sorting,
      // On encode l'ensemble du filtrage (global + colonnes) dans `globalFilter`
      // pour le réévaluer dès que l'un ou l'autre change ; la vraie logique vit
      // dans `globalFilterFn`.
      globalFilter: globalFilterValue,
    },
    manualSorting,
    manualFiltering,
    enableSortingRemoval: true,
    sortDescFirst: false,
    getRowId: (row, index) => String(getRowId(row, index)),
    sortingFns,
    defaultColumn: { sortingFn: 'dtCompare' },
    globalFilterFn,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: manualSorting ? undefined : getSortedRowModel(),
    getFilteredRowModel: manualFiltering ? undefined : getFilteredRowModel(),
  })

  /* ---- Pipeline de données : filtre → tri (via react-table) → page ---- */
  // `filtered` : lignes après filtrage (ou `data` en filtrage manuel).
  const filtered = useMemo(() => {
    if (manualFiltering) return data
    return table.getFilteredRowModel().rows.map((r) => r.original)
    // dépendances réelles du modèle filtré :
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [table, data, query, columnFilters, globalIds, accessor, manualFiltering])

  // `sorted` : lignes après filtrage + tri (ou `filtered` en tri manuel).
  const sorted = useMemo(() => {
    if (manualSorting) return filtered
    return table.getSortedRowModel().rows.map((r) => r.original)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [table, filtered, sorting, manualSorting])

  const totalCount = manualPagination ? manualRowCount ?? data.length : sorted.length

  const paged = useMemo(() => {
    if (manualPagination) return sorted
    return paginateRows(sorted, pageIndex, pageSize)
  }, [sorted, pageIndex, pageSize, manualPagination])

  const range = useMemo(
    () => pageRange(pageIndex, pageSize, totalCount),
    [pageIndex, pageSize, totalCount],
  )

  // Sous-totaux calculés sur l'ensemble filtré (pas seulement la page).
  const summaryValues = useMemo(
    () => (summary ? summarize(manualPagination ? data : sorted, summary, accessor) : null),
    [summary, sorted, data, accessor, manualPagination],
  )

  const resolvedColumns = useMemo(
    () => resolveColumns(columns, columnState),
    [columns, columnState],
  )

  /* ---- Identité de ligne cohérente (ERR96) ----
     Le `getRowId` par défaut retombe sur l'INDEX quand la ligne n'a pas d'`id`.
     Cet index doit alors être le MÊME repère partout : sinon les clés de page
     (index local 0..pageSize) et la sélection (index global 0..total) divergent
     et une ligne sans id est sélectionnée à tort. On expose donc `keyOf(row,
     globalIndex)` et on fournit toujours l'index GLOBAL dans l'univers de lignes
     utilisé pour la sélection (`data` en pagination manuelle, sinon `sorted`),
     ce que la grille réutilise pour le rendu. */
  const selectionRows = manualPagination ? data : sorted
  // Décalage global de la page : en pagination cliente, paged = sorted.slice(...)
  // donc l'index global d'une ligne de page est pageIndex*pageSize + i ; en
  // pagination manuelle, paged === data, donc le décalage est nul.
  const pageOffset = manualPagination ? 0 : pageIndex * pageSize
  const keyOf = useCallback(
    (row, globalIndex) => String(getRowId(row, globalIndex)),
    [getRowId],
  )
  const pageKeys = useMemo(
    () => paged.map((row, i) => keyOf(row, pageOffset + i)),
    [paged, keyOf, pageOffset],
  )
  const pageSelectionState = useMemo(
    () => selectionState(selected, pageKeys),
    [selected, pageKeys],
  )
  const selectedKeys = useMemo(() => Object.keys(selected), [selected])
  const selectedRows = useMemo(
    () => selectionRows.filter((row, i) => selected[keyOf(row, i)]),
    [selected, selectionRows, keyOf],
  )

  /* ---- Actions de tri (avec seam serveur) ---- */
  const onSort = useCallback(
    (id, { multi = false } = {}) => {
      setSorting((prev) => toggleSort(prev, id, { multi }))
      setPageIndex(0)
    },
    [],
  )

  const onQueryChange = useCallback((value) => {
    setQuery(value)
    setPageIndex(0)
  }, [])

  const onColumnFilterChange = useCallback((id, value) => {
    setColumnFilters((prev) => {
      const next = { ...prev }
      if (value === '' || value === null || value === undefined || (Array.isArray(value) && value.length === 0)) {
        delete next[id]
      } else {
        next[id] = value
      }
      return next
    })
    setPageIndex(0)
  }, [])

  /* ---- Sélection ---- */
  const onToggleRow = useCallback((key) => setSelected((p) => toggleSelected(p, key)), [])
  const onToggleAllPage = useCallback(() => {
    setSelected((p) => setAllSelected(p, pageKeys, pageSelectionState !== 'all'))
  }, [pageKeys, pageSelectionState])
  const clearSelection = useCallback(() => setSelected({}), [])

  /* ---- Persistance URL (écriture via effect) ---- */
  useEffect(() => {
    if (!persistToUrl) return
    const params = encodeState(
      { sorting, query, columnFilters, pageIndex, pageSize, view },
      urlKey,
    )
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(params)) {
          if (v == null) next.delete(k)
          else next.set(k, v)
        }
        return next
      },
      { replace: true },
    )
  }, [persistToUrl, urlKey, sorting, query, columnFilters, pageIndex, pageSize, view, setSearchParams])

  return {
    // données
    rows: paged,
    allRows: sorted,
    totalCount,
    range,
    summaryValues,
    resolvedColumns,
    // tri
    sorting,
    onSort,
    setSorting,
    // filtres
    query,
    onQueryChange,
    columnFilters,
    onColumnFilterChange,
    setColumnFilters,
    // pagination
    pageIndex,
    setPageIndex,
    pageSize,
    setPageSize,
    // colonnes
    columnState,
    dispatchColumns,
    // sélection
    selected,
    selectedKeys,
    selectedRows,
    pageKeys,
    pageSelectionState,
    onToggleRow,
    onToggleAllPage,
    clearSelection,
    // vues sauvegardées
    view,
    setView,
    // accès brut
    getRowId,
    keyOf,
    pageOffset,
    accessor,
    // moteur (P171) : instance react-table sous-jacente, pour usages avancés.
    table,
  }
}

export default useDataTable
