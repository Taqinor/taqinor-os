import { forwardRef, useCallback, useEffect, useMemo, useRef, useState, Fragment } from 'react'
import {
  ArrowUp, ArrowDown, ChevronsUpDown, Search, MoreHorizontal,
  ChevronRight, Pin, PinOff, EyeOff, Download, ChevronLeft, Inbox, AlertTriangle,
} from 'lucide-react'
import { cn } from '../../lib/cn'
import { useDensity } from '../../design/theme-context'
import { Button } from '../Button'
import { IconButton } from '../IconButton'
import { Input } from '../Input'
import { Checkbox } from '../Checkbox'
import { Skeleton } from '../Skeleton'
import { EmptyState } from '../EmptyState'
import { Tabs, TabsList, TabsTrigger } from '../Tabs'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from '../DropdownMenu'
import { highlightSegments, computeWindow } from './logic.js'
import { debounce } from '../../lib/debounce.js'
import { rowsToCSV, exportFileName } from './csv.js'
import { useDataTable } from './useDataTable.js'
import { ColumnManager } from './ColumnManager.jsx'
import { BulkActionBar } from './BulkActionBar.jsx'

/* ============================================================================
   H31/H32/H33 — Moteur de tableau réutilisable (la grille derrière toutes les
   futures vues de liste). MOTEUR SEUL — démontré dans /ui ; non branché aux
   écrans réels (Groupe J). 100 % additif.

   Définition d'une colonne :
   { id, header, accessor?(row), cell?(value,row), align?, width?, minWidth?,
     hideable?, sortable?, filterable?, searchable?, pinned?, editable?,
     validate?(v,row), onSave?(v,row), summary?(label/value renderer) }
   ========================================================================== */

const HL = 'rounded-sm bg-warning/30 text-foreground'

/** Surligne un texte selon la requête de recherche (H31). */
function Highlighted({ text, query }) {
  if (!query) return <>{text}</>
  return (
    <>
      {highlightSegments(text, query).map((seg, i) =>
        seg.match ? (
          <mark key={i} className={HL}>{seg.text}</mark>
        ) : (
          <Fragment key={i}>{seg.text}</Fragment>
        ),
      )}
    </>
  )
}

function SortIcon({ dir }) {
  if (dir === 'asc') return <ArrowUp className="size-3.5" aria-hidden="true" />
  if (dir === 'desc') return <ArrowDown className="size-3.5" aria-hidden="true" />
  return <ChevronsUpDown className="size-3.5 opacity-40 group-hover:opacity-70" aria-hidden="true" />
}

export const DataTable = forwardRef(function DataTable(
  {
    data = [],
    columns = [],
    getRowId = (row, i) => row?.id ?? i,
    // états
    loading = false,
    error = null,
    // recherche / filtres
    searchable = true,
    searchPlaceholder = 'Rechercher…',
    globalColumns,
    // sélection / actions
    selectable = false,
    bulkActions, // (selectedRows, selectedKeys, clear) => [{ id,label,icon,onClick,... }]
    rowActions, // (row) => [{ id, label, icon, onClick, destructive }] (max 3 + overflow)
    onRowClick,
    renderExpanded, // (row) => ReactNode → ligne dépliable
    // pagination
    pageSize: initialPageSize = 25,
    pageSizeOptions = [10, 25, 50, 100],
    // vues sauvegardées (H33)
    savedViews, // [{ id, label, sorting?, columnFilters?, query? }]
    // virtualisation (H33)
    virtualize = false,
    rowHeight = 44,
    maxBodyHeight = 480,
    // export (H33)
    onExport, // (selectedRows|allRows, columns) => void  (si fourni, prioritaire)
    exportName = 'export',
    // seams serveur
    manualSorting = false,
    manualFiltering = false,
    manualPagination = false,
    rowCount,
    summary = null,
    summaryLabel = 'Total',
    // persistance URL (H33)
    persistToUrl = false,
    urlKey = '',
    className,
    emptyTitle = 'Aucune donnée',
    emptyDescription = 'La liste est vide pour le moment.',
    'aria-label': ariaLabel = 'Tableau de données',
  },
  ref,
) {
  const { density } = useDensity()
  const compact = density === 'compact'

  const table = useDataTable({
    data, columns, getRowId, globalColumns,
    initialPageSize, initialView: savedViews?.[0]?.id ?? null,
    manualSorting, manualFiltering, manualPagination, rowCount, summary,
    persistToUrl, urlKey,
  })

  const {
    rows, allRows, totalCount, range, summaryValues, resolvedColumns,
    sorting, onSort, setSorting, query, onQueryChange,
    setColumnFilters,
    pageIndex, setPageIndex, pageSize, setPageSize,
    columnState, dispatchColumns,
    selected, selectedKeys, selectedRows, pageSelectionState, onToggleRow, onToggleAllPage, clearSelection,
    view, setView,
    keyOf, pageOffset,
  } = table

  const [expanded, setExpanded] = useState({})
  const dragId = useRef(null)
  const scrollRef = useRef(null)
  const [scrollTop, setScrollTop] = useState(0)

  /* ---- Recherche globale anti-rebond (O66) ----
     La valeur AFFICHÉE dans le champ reste instantanée (`searchInput`) ; seul le
     filtre APPLIQUÉ (`onQueryChange`) est différé d'un court délai, pour ne pas
     refiltrer une grande liste à chaque frappe. Si `query` change de l'extérieur
     (ex. application d'une vue sauvegardée), on resynchronise l'affichage. */
  const [searchInput, setSearchInput] = useState(query)
  const lastTyped = useRef(query)
  const applyQueryDebounced = useMemo(
    () => debounce((value) => onQueryChange(value), 250),
    [onQueryChange],
  )
  useEffect(() => () => applyQueryDebounced.cancel(), [applyQueryDebounced])
  // Resynchronise le champ uniquement quand `query` change SANS venir d'une frappe
  // (vue sauvegardée, reset programmatique), sans écraser la saisie en cours.
  useEffect(() => {
    if (query !== lastTyped.current) {
      lastTyped.current = query
      setSearchInput(query)
    }
  }, [query])
  const onSearchInput = useCallback(
    (value) => {
      lastTyped.current = value
      setSearchInput(value)
      applyQueryDebounced(value)
    },
    [applyQueryDebounced],
  )

  /* ---- Tri : map id → direction ---- */
  const sortDir = useMemo(() => {
    const m = {}
    for (const s of sorting) m[s.id] = s.desc ? 'desc' : 'asc'
    return m
  }, [sorting])

  /* ---- Vues sauvegardées (H33) ---- */
  const applyView = useCallback(
    (id) => {
      setView(id)
      const v = savedViews?.find((sv) => sv.id === id)
      if (!v) return
      if (v.sorting !== undefined) setSorting(v.sorting)
      if (v.columnFilters !== undefined) setColumnFilters(v.columnFilters)
      if (v.query !== undefined) onQueryChange(v.query ?? '')
      setPageIndex(0)
    },
    [savedViews, setView, setSorting, setColumnFilters, onQueryChange, setPageIndex],
  )

  /* ---- Export (H33) : callback injecté sinon fallback CSV client ---- */
  const handleExport = useCallback(() => {
    const exportRows = selectedKeys.length ? selectedRows : allRows
    const exportCols = resolvedColumns.map((c) => ({
      id: c.id,
      header: c.header ?? c.id,
      exportValue: (row) => {
        if (c.exportValue) return c.exportValue(row)
        const raw = c.accessor ? c.accessor(row) : row?.[c.id]
        return raw
      },
    }))
    if (onExport) {
      onExport(exportRows, exportCols)
      return
    }
    // Fallback CSV côté client (aucun backend).
    const csv = rowsToCSV(exportRows, exportCols)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportFileName(exportName)
    a.click()
    URL.revokeObjectURL(url)
  }, [selectedKeys, selectedRows, allRows, resolvedColumns, onExport, exportName])

  /* ---- Réordonnancement par glisser-déposer (HTML5, sans dépendance) ---- */
  const onHeaderDrop = useCallback(
    (toId) => {
      const fromId = dragId.current
      if (fromId && fromId !== toId) {
        dispatchColumns({ type: 'reorder', fromId, toId })
      }
      dragId.current = null
    },
    [dispatchColumns],
  )

  /* ---- Largeurs / offsets des colonnes épinglées (gel) ---- */
  const pinOffsets = useMemo(() => {
    const offsets = {}
    let acc = selectable ? 44 : 0
    for (const c of resolvedColumns) {
      if (c.pinned === 'left') {
        offsets[c.id] = acc
        acc += c.width ?? 160
      }
    }
    return offsets
  }, [resolvedColumns, selectable])

  const toggleExpand = useCallback(
    (key) => setExpanded((p) => ({ ...p, [key]: !p[key] })),
    [],
  )

  /* ---- Virtualisation (H33) : fenêtre de lignes ---- */
  const win = virtualize
    ? computeWindow({ scrollTop, viewportHeight: maxBodyHeight, rowHeight, rowCount: rows.length, overscan: 8 })
    : { startIndex: 0, endIndex: rows.length, paddingTop: 0, paddingBottom: 0 }
  const visibleRows = virtualize ? rows.slice(win.startIndex, win.endIndex) : rows

  const colSpan = resolvedColumns.length + (selectable ? 1 : 0) + (rowActions ? 1 : 0) + (renderExpanded ? 1 : 0)
  const expandable = typeof renderExpanded === 'function'

  const cellPadY = compact ? 'py-1.5' : 'py-2.5'
  const cellPadX = 'px-3'

  /* ---- Cellule (avec surlignage + clic ligne) ---- */
  function renderCell(c, row) {
    const value = c.accessor ? c.accessor(row) : row?.[c.id]
    if (c.cell) return c.cell(value, row, { query })
    const text = value === null || value === undefined || value === '' ? '—' : String(value)
    return <Highlighted text={text} query={c.searchable === false ? '' : query} />
  }

  const hasToolbar = searchable || savedViews || columns.some((c) => c.hideable !== false) || onExport !== undefined

  return (
    <div ref={ref} className={cn('flex flex-col gap-3', className)}>
      {/* -------- Vues sauvegardées (onglets) -------- */}
      {savedViews && savedViews.length > 0 && (
        <Tabs value={view ?? savedViews[0].id} onValueChange={applyView}>
          <TabsList className="flex-wrap">
            {savedViews.map((v) => (
              <TabsTrigger key={v.id} value={v.id}>
                {v.label}
                {typeof v.count === 'number' && (
                  <span className="ml-1.5 rounded bg-muted px-1.5 text-xs text-muted-foreground">{v.count}</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}

      {/* -------- Barre d'outils -------- */}
      {hasToolbar && (
        <div className="flex flex-wrap items-center gap-2">
          {searchable && (
            <div className="w-full sm:w-72">
              <Input
                leading={<Search />}
                value={searchInput}
                onChange={(e) => onSearchInput(e.target.value)}
                placeholder={searchPlaceholder}
                aria-label="Recherche globale"
              />
            </div>
          )}
          <div className="ml-auto flex items-center gap-2">
            {columns.some((c) => c.hideable !== false) && (
              <ColumnManager columns={columns} columnState={columnState} dispatch={dispatchColumns} />
            )}
            <Button variant="outline" size="sm" onClick={handleExport}>
              <Download />
              <span className="hidden sm:inline">Exporter</span>
            </Button>
          </div>
        </div>
      )}

      {/* -------- Erreur -------- */}
      {error ? (
        <EmptyState
          icon={AlertTriangle}
          title="Erreur de chargement"
          description={typeof error === 'string' ? error : 'Impossible de charger les données.'}
          className="border-destructive/40"
        />
      ) : (
        <>
          {/* -------- DESKTOP : tableau -------- */}
          <div className="hidden overflow-hidden rounded-xl border border-border bg-card sm:block">
            <div
              ref={scrollRef}
              onScroll={virtualize ? (e) => setScrollTop(e.currentTarget.scrollTop) : undefined}
              className="overflow-auto"
              style={virtualize ? { maxHeight: maxBodyHeight } : undefined}
            >
              <table
                role="grid"
                aria-label={ariaLabel}
                aria-rowcount={totalCount}
                className="w-full border-collapse text-sm"
              >
                <thead className="sticky top-0 z-[var(--z-sticky)] bg-muted/95 backdrop-blur">
                  <tr>
                    {expandable && <th scope="col" className="w-9 px-2" aria-label="Déplier" />}
                    {selectable && (
                      <th
                        scope="col"
                        className="sticky left-0 z-[var(--z-sticky)] w-11 bg-muted/95 px-3 text-left"
                      >
                        <Checkbox
                          checked={pageSelectionState === 'all' ? true : pageSelectionState === 'some' ? 'indeterminate' : false}
                          onCheckedChange={onToggleAllPage}
                          aria-label="Tout sélectionner sur cette page"
                        />
                      </th>
                    )}
                    {resolvedColumns.map((c) => {
                      const dir = sortDir[c.id]
                      const sortable = c.sortable !== false && !manualSorting ? true : c.sortable
                      const pinnedLeft = c.pinned === 'left'
                      return (
                        <th
                          key={c.id}
                          scope="col"
                          aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : sortable ? 'none' : undefined}
                          draggable={c.reorderable !== false}
                          onDragStart={() => { dragId.current = c.id }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => onHeaderDrop(c.id)}
                          style={{
                            width: c.width ?? undefined,
                            minWidth: c.minWidth ?? undefined,
                            left: pinnedLeft ? pinOffsets[c.id] : undefined,
                          }}
                          className={cn(
                            'whitespace-nowrap px-3 text-left align-middle font-semibold text-muted-foreground',
                            compact ? 'py-2 text-xs' : 'py-2.5 text-xs',
                            c.align === 'right' && 'text-right',
                            c.align === 'center' && 'text-center',
                            pinnedLeft && 'sticky z-[var(--z-sticky)] bg-muted/95',
                          )}
                        >
                          <div className={cn('flex items-center gap-1.5', c.align === 'right' && 'justify-end', c.align === 'center' && 'justify-center')}>
                            {sortable ? (
                              <button
                                type="button"
                                onClick={(e) => onSort(c.id, { multi: e.shiftKey })}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' || e.key === ' ') {
                                    e.preventDefault()
                                    onSort(c.id, { multi: e.shiftKey })
                                  }
                                }}
                                className="group inline-flex items-center gap-1 rounded uppercase tracking-wide hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                aria-label={`Trier par ${c.header ?? c.id}`}
                              >
                                <span>{c.header ?? c.id}</span>
                                <SortIcon dir={dir} />
                              </button>
                            ) : (
                              <span className="uppercase tracking-wide">{c.header ?? c.id}</span>
                            )}
                            {/* Menu d'en-tête : épingler / masquer */}
                            <ColumnHeaderMenu column={c} dispatch={dispatchColumns} />
                          </div>
                        </th>
                      )
                    })}
                    {rowActions && <th scope="col" className="w-12 px-3" aria-label="Actions" />}
                  </tr>
                </thead>

                <tbody>
                  {loading ? (
                    Array.from({ length: 6 }).map((unused, i) => (
                      <tr key={i} className="border-t border-border">
                        {expandable && <td className="px-2 py-2.5" />}
                        {selectable && <td className="px-3 py-2.5"><Skeleton className="size-4" /></td>}
                        {resolvedColumns.map((c) => (
                          <td key={c.id} className="px-3 py-2.5"><Skeleton className="h-4 w-3/4" /></td>
                        ))}
                        {rowActions && <td className="px-3 py-2.5" />}
                      </tr>
                    ))
                  ) : rows.length === 0 ? (
                    <tr>
                      <td colSpan={colSpan} className="p-0">
                        <EmptyState icon={Inbox} title={emptyTitle} description={emptyDescription} className="m-3 border-0" />
                      </td>
                    </tr>
                  ) : (
                    <>
                      {virtualize && win.paddingTop > 0 && (
                        <tr aria-hidden="true" style={{ height: win.paddingTop }}>
                          <td colSpan={colSpan} className="p-0" />
                        </tr>
                      )}
                      {visibleRows.map((row, vi) => {
                        const i = (virtualize ? win.startIndex : 0) + vi
                        const rowKey = keyOf(row, pageOffset + i)
                        const isSelected = !!selected[rowKey]
                        const isExpanded = !!expanded[rowKey]
                        const actions = rowActions ? rowActions(row) : []
                        return (
                          <Fragment key={rowKey}>
                            <tr
                              className={cn(
                                'group border-t border-border transition-colors',
                                onRowClick && 'cursor-pointer',
                                isSelected ? 'bg-primary/5' : 'hover:bg-muted/40',
                              )}
                              onClick={onRowClick ? () => onRowClick(row) : undefined}
                              aria-selected={selectable ? isSelected : undefined}
                              style={virtualize ? { height: rowHeight } : undefined}
                            >
                              {expandable && (
                                <td className="w-9 px-2" onClick={(e) => e.stopPropagation()}>
                                  <IconButton
                                    label={isExpanded ? 'Replier' : 'Déplier'}
                                    variant="ghost"
                                    size="icon"
                                    className="size-7"
                                    aria-expanded={isExpanded}
                                    onClick={() => toggleExpand(rowKey)}
                                  >
                                    <ChevronRight className={cn('transition-transform', isExpanded && 'rotate-90')} />
                                  </IconButton>
                                </td>
                              )}
                              {selectable && (
                                <td
                                  className="sticky left-0 z-[1] w-11 bg-inherit px-3"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <span className={cn('inline-flex', !isSelected && 'opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 sm:opacity-0', isSelected && 'opacity-100')}>
                                    <Checkbox
                                      checked={isSelected}
                                      onCheckedChange={() => onToggleRow(rowKey)}
                                      aria-label={`Sélectionner la ligne ${i + 1}`}
                                    />
                                  </span>
                                </td>
                              )}
                              {resolvedColumns.map((c, ci) => {
                                const pinnedLeft = c.pinned === 'left'
                                const firstCol = ci === 0
                                return (
                                  <td
                                    key={c.id}
                                    role="gridcell"
                                    style={{
                                      width: c.width ?? undefined,
                                      left: pinnedLeft ? pinOffsets[c.id] : undefined,
                                    }}
                                    className={cn(
                                      cellPadX, cellPadY, 'align-middle',
                                      c.align === 'right' && 'text-right tabular-nums',
                                      c.align === 'center' && 'text-center',
                                      c.numeric && 'tabular-nums',
                                      (pinnedLeft || (firstCol && c.frozen)) && 'sticky z-[1] bg-inherit',
                                      firstCol && 'font-medium text-foreground',
                                    )}
                                  >
                                    {renderCell(c, row)}
                                  </td>
                                )
                              })}
                              {rowActions && (
                                <td className="px-2" onClick={(e) => e.stopPropagation()}>
                                  <RowActions actions={actions} />
                                </td>
                              )}
                            </tr>
                            {renderExpanded && isExpanded && (
                              <tr className="border-t border-border bg-muted/20">
                                <td colSpan={colSpan} className="px-4 py-3">
                                  {renderExpanded(row)}
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        )
                      })}
                      {virtualize && win.paddingBottom > 0 && (
                        <tr aria-hidden="true" style={{ height: win.paddingBottom }}>
                          <td colSpan={colSpan} className="p-0" />
                        </tr>
                      )}
                    </>
                  )}
                </tbody>

                {/* -------- Ligne de sous-totaux -------- */}
                {summary && summaryValues && rows.length > 0 && (
                  <tfoot className="sticky bottom-0 z-[1] border-t-2 border-border bg-muted/90 backdrop-blur">
                    <tr>
                      {expandable && <td className="px-2" />}
                      {selectable && <td className="px-3" />}
                      {resolvedColumns.map((c, ci) => (
                        <td
                          key={c.id}
                          className={cn('px-3 py-2 text-xs font-semibold', c.align === 'right' && 'text-right tabular-nums')}
                        >
                          {ci === 0
                            ? summaryLabel
                            : c.summaryRender
                              ? c.summaryRender(summaryValues[c.id], summaryValues)
                              : summaryValues[c.id] !== undefined && summaryValues[c.id] !== null
                                ? c.summaryFormat
                                  ? c.summaryFormat(summaryValues[c.id])
                                  : summaryValues[c.id]
                                : ''}
                        </td>
                      ))}
                      {rowActions && <td />}
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>

          {/* -------- MOBILE : cartes (H33) -------- */}
          <div className="flex flex-col gap-2 sm:hidden">
            {loading ? (
              Array.from({ length: 4 }).map((unused, i) => (
                <div key={i} className="rounded-xl border border-border bg-card p-3">
                  <Skeleton className="mb-2 h-5 w-1/2" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              ))
            ) : rows.length === 0 ? (
              <EmptyState icon={Inbox} title={emptyTitle} description={emptyDescription} />
            ) : (
              rows.map((row, i) => {
                const rowKey = keyOf(row, pageOffset + i)
                const isSelected = !!selected[rowKey]
                const actions = rowActions ? rowActions(row) : []
                const mobileCols = resolvedColumns.filter((c) => c.mobileHidden !== true)
                return (
                  <div
                    key={rowKey}
                    className={cn(
                      'rounded-xl border bg-card p-3 transition-colors',
                      isSelected ? 'border-primary bg-primary/5' : 'border-border',
                    )}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        {mobileCols.map((c, ci) => {
                          const value = c.accessor ? c.accessor(row) : row?.[c.id]
                          return (
                            <div key={c.id} className={cn('flex items-baseline justify-between gap-2', ci === 0 ? 'mb-1' : 'py-0.5')}>
                              {ci !== 0 && <span className="shrink-0 text-xs text-muted-foreground">{c.header ?? c.id}</span>}
                              <span className={cn('min-w-0 truncate', ci === 0 ? 'font-semibold text-foreground' : 'text-sm')}>
                                {c.cell ? c.cell(value, row, { query }) : <Highlighted text={String(value ?? '—')} query={query} />}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                      <div className="flex shrink-0 items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        {selectable && (
                          <Checkbox checked={isSelected} onCheckedChange={() => onToggleRow(rowKey)} aria-label={`Sélectionner la ligne ${i + 1}`} />
                        )}
                        {rowActions && <RowActions actions={actions} />}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* -------- Pagination -------- */}
          {!loading && rows.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <span aria-live="polite">{range.from === 0 ? '0 sur 0' : `${range.from}–${range.to} sur ${range.total}`}</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPageIndex(0) }}
                  aria-label="Lignes par page"
                  className="h-8 rounded-md border border-input bg-card px-2 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {pageSizeOptions.map((n) => (
                    <option key={n} value={n}>{n} / page</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-1">
                <IconButton
                  label="Page précédente"
                  variant="outline"
                  size="icon"
                  disabled={pageIndex <= 0}
                  onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                >
                  <ChevronLeft />
                </IconButton>
                <span className="px-2 text-xs text-muted-foreground">
                  Page {pageIndex + 1} / {Math.max(1, Math.ceil(totalCount / (pageSize || totalCount || 1)))}
                </span>
                <IconButton
                  label="Page suivante"
                  variant="outline"
                  size="icon"
                  disabled={(pageIndex + 1) * pageSize >= totalCount}
                  onClick={() => setPageIndex((p) => p + 1)}
                >
                  <ChevronRight />
                </IconButton>
              </div>
            </div>
          )}
        </>
      )}

      {/* -------- Barre d'actions groupées (H32) -------- */}
      {selectable && bulkActions && (
        <BulkActionBar
          count={selectedKeys.length}
          actions={bulkActions(selectedRows, selectedKeys, clearSelection)}
          onClear={clearSelection}
        />
      )}

    </div>
  )
})

/* ---- Sous-composants ---- */

/** Menu contextuel d'en-tête : épingler à gauche / dégingler / masquer (H31). */
function ColumnHeaderMenu({ column, dispatch }) {
  if (column.hideable === false && column.pinnable === false) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Options de la colonne ${column.header ?? column.id}`}
          className="rounded p-0.5 opacity-0 transition-opacity hover:bg-accent focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover:opacity-60 [tr:hover_&]:opacity-60"
          onClick={(e) => e.stopPropagation()}
        >
          <MoreHorizontal className="size-3.5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {column.pinned === 'left' ? (
          <DropdownMenuItem onSelect={() => dispatch({ type: 'pin', id: column.id, side: null })}>
            <PinOff /> Détacher
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onSelect={() => dispatch({ type: 'pin', id: column.id, side: 'left' })}>
            <Pin /> Épingler à gauche
          </DropdownMenuItem>
        )}
        {column.hideable !== false && (
          <DropdownMenuItem onSelect={() => dispatch({ type: 'setVisibility', id: column.id, visible: false })}>
            <EyeOff /> Masquer
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Jusqu'à 3 actions icône + menu overflow (H32). */
function RowActions({ actions = [] }) {
  if (!actions.length) return null
  const inline = actions.slice(0, 3)
  const overflow = actions.slice(3)
  return (
    <div className="flex items-center justify-end gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100">
      {inline.map((a) => {
        const Icon = a.icon ?? MoreHorizontal
        return (
          <IconButton
            key={a.id}
            label={a.label}
            variant="ghost"
            size="icon"
            onClick={() => a.onClick?.()}
            className={cn('size-8', a.destructive && 'text-destructive hover:text-destructive')}
          >
            <Icon />
          </IconButton>
        )
      })}
      {overflow.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <IconButton label="Plus d'actions" variant="ghost" size="icon" className="size-8">
              <MoreHorizontal />
            </IconButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            {overflow.map((a) => {
              const Icon = a.icon
              return (
                <Fragment key={a.id}>
                  {a.separatorBefore && <DropdownMenuSeparator />}
                  <DropdownMenuItem destructive={a.destructive} onSelect={() => a.onClick?.()}>
                    {Icon && <Icon />} {a.label}
                  </DropdownMenuItem>
                </Fragment>
              )
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  )
}

export default DataTable
