import { useCallback, useEffect, useMemo, useReducer, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  sortRows, toggleSort, filterRows, paginateRows, pageRange,
  initColumnState, columnStateReducer, resolveColumns,
  toggleSelected, setAllSelected, selectionState, summarize,
} from './logic.js'
import { encodeState, decodeState } from './urlState.js'

/* ============================================================================
   H31/H33 — Hook d'orchestration du DataTable (état + persistance URL).
   ----------------------------------------------------------------------------
   - Tri / filtres / pagination 100 % côté client par défaut (logic.js).
   - SEAM SERVEUR : `manualSorting`/`manualFiltering`/`manualPagination` court-
     circuitent le calcul local et exposent les callbacks au consommateur, qui
     fournit alors `rows` déjà triées/filtrées + `rowCount`. Aucun endpoint
     n'est construit ici (Groupe J branchera de vrais services).
   - Persistance URL optionnelle (`persistToUrl` + `urlKey`) via useSearchParams.
   ========================================================================== */

const ACCESSOR = (row, id) => row?.[id]

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
    initColumnState,
  )

  // Colonnes balayées par la recherche globale (par défaut : toutes).
  const globalIds = useMemo(
    () => globalColumns ?? columns.map((c) => c.id),
    [globalColumns, columns],
  )

  /* ---- Pipeline de données : filtre → tri → page ---- */
  const filtered = useMemo(() => {
    if (manualFiltering) return data
    return filterRows(data, { query, columnFilters, globalColumns: globalIds }, accessor)
  }, [data, query, columnFilters, globalIds, accessor, manualFiltering])

  const sorted = useMemo(() => {
    if (manualSorting) return filtered
    return sortRows(filtered, sorting, accessor)
  }, [filtered, sorting, accessor, manualSorting])

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
  }
}

export default useDataTable
