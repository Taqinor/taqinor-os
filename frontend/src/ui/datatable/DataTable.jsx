import {
  forwardRef, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, Fragment,
} from 'react'
import {
  ArrowUp, ArrowDown, ChevronsUpDown, Search, MoreHorizontal, MoreVertical,
  ChevronRight, Pin, PinOff, EyeOff, Download, ChevronLeft, Inbox, AlertTriangle,
  ArrowLeft, ArrowRight,
} from 'lucide-react'
import { cn } from '../../lib/cn'
import { useDensity } from '../../design/theme-context'
import { Button } from '../Button'
import { IconButton } from '../IconButton'
import { Input } from '../Input'
import { Checkbox } from '../Checkbox'
import { Skeleton } from '../Skeleton'
import { EmptyState } from '../EmptyState'
// VX249(a) — première intégration réelle de `col.editable`/`col.onSave`
// (documenté dans le contrat de colonne depuis H31/H32 mais jamais câblé :
// « moteur seul, non branché aux écrans réels »). Réutilise EditableCell
// (H32, patron double-clic/Entrée déjà démontré ailleurs) + FieldSavedPulse
// (pulse vert sur LA cellule à la sauvegarde, jamais un toast pour ça).
import { EditableCell } from './EditableCell'
import { FieldSavedPulse } from '../FieldSavedPulse'
import { Tabs, TabsList, TabsTrigger } from '../Tabs'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from '../DropdownMenu'
import { highlightSegments, computeWindow, pinnedEdgeOffsets, columnWidthVars } from './logic.js'
import { debounce } from '../../lib/debounce.js'
import { rowsToCSV, exportFileName } from './csv.js'
import { useDataTable } from './useDataTable.js'
import { ColumnManager } from './ColumnManager.jsx'
import { BulkActionBar } from './BulkActionBar.jsx'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

// VX135 — AUCUNE liste de l'app n'animait tri/filtre/ajout (téléportation des
// lignes) : FLIP minimal (First-Last-Invert-Play), zéro dépendance. Mesure
// `getBoundingClientRect` AVANT/APRÈS via un effet de LAYOUT (avant peinture) :
// quand l'ORDRE des clés change (tri, filtre), chaque ligne encore présente
// est réinjectée à son ANCIENNE position (transform, transition coupée) puis
// relâchée vers sa position finale avec une transition — elle glisse au lieu
// de téléporter. Plafonné (coût de mesure) et désactivé par le hook
// reduced-motion (le garde CSS global ne peut pas neutraliser un transform
// posé impérativement en JS).
const ROW_FLIP_MAX_ROWS = 200

function useRowFlip(rowKeys, disabled) {
  const nodeMap = useRef(new Map())
  const prevTops = useRef(new Map())
  const prevOrderKey = useRef(null)

  const registerRow = useCallback((key) => (el) => {
    if (el) nodeMap.current.set(key, el)
    else nodeMap.current.delete(key)
  }, [])

  useLayoutEffect(() => {
    if (disabled || rowKeys.length === 0 || rowKeys.length > ROW_FLIP_MAX_ROWS) {
      prevTops.current = new Map()
      prevOrderKey.current = null
      return
    }
    const orderKey = rowKeys.join(String.fromCharCode(31))
    const nextTops = new Map()
    for (const key of rowKeys) {
      const el = nodeMap.current.get(key)
      if (el) nextTops.set(key, el.getBoundingClientRect().top)
    }
    if (prevOrderKey.current !== null && prevOrderKey.current !== orderKey) {
      for (const [key, prevTop] of prevTops.current) {
        const nextTop = nextTops.get(key)
        if (nextTop == null) continue
        const delta = prevTop - nextTop
        if (Math.abs(delta) < 1) continue
        const el = nodeMap.current.get(key)
        if (!el) continue
        // Invert : replace la ligne à son ancienne position, sans transition.
        el.style.transition = 'none'
        el.style.transform = `translateY(${delta}px)`
        // Force un reflow pour que le navigateur applique l'état de départ
        // avant qu'on n'engage la transition vers l'état final (sinon les
        // deux changements de style sont regroupés en une seule frame).
        el.offsetHeight
        // Play : relâche vers la position finale, transitionnée.
        el.style.transition = 'transform var(--motion-base) var(--ease-standard)'
        el.style.transform = ''
      }
    }
    prevTops.current = nextTops
    prevOrderKey.current = orderKey
  }, [rowKeys, disabled])

  return registerRow
}

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

/* VX43 — Swipe-to-action horizontal maison sur les cartes mobiles
   (`data-dt-cards`), même geste/maths que LeadCard.jsx (touchstart/move/end,
   seuil de distance anti-scroll, zéro dépendance). 100 % opt-in via la prop
   `swipeActions` : non fournie, le rendu carte reste identique à avant. */
const SWIPE_REVEAL_PX = 96
function shouldArmSwipe(deltaX, deltaY) {
  if (Math.abs(deltaX) < 5) return false
  return Math.abs(deltaX) > Math.abs(deltaY)
}
function clampSwipeOffset(deltaX, maxReveal = SWIPE_REVEAL_PX) {
  return Math.max(-maxReveal, Math.min(0, deltaX))
}
function resolveSwipeSnap(offset, maxReveal = SWIPE_REVEAL_PX) {
  return Math.abs(offset) >= maxReveal / 2 ? -maxReveal : 0
}

function useSwipeReveal(enabled) {
  const [offset, setOffset] = useState(0)
  const start = useRef(null)
  const armed = useRef(false)

  const onTouchStart = (e) => {
    if (!enabled) return
    const t = e.touches?.[0]
    if (!t) return
    start.current = { x: t.clientX, y: t.clientY }
    armed.current = false
  }
  const onTouchMove = (e) => {
    if (!enabled || !start.current) return
    const t = e.touches?.[0]
    if (!t) return
    const deltaX = t.clientX - start.current.x
    const deltaY = t.clientY - start.current.y
    if (!armed.current) {
      if (!shouldArmSwipe(deltaX, deltaY)) return
      armed.current = true
    }
    setOffset(clampSwipeOffset(deltaX))
  }
  const onTouchEnd = () => {
    if (!enabled) return
    start.current = null
    if (armed.current) {
      armed.current = false
      setOffset((prev) => resolveSwipeSnap(prev))
    }
  }
  const close = () => setOffset(0)

  return {
    offset,
    close,
    handlers: { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel: onTouchEnd },
  }
}

/** Carte mobile swipeable : enveloppe une carte `data-dt-cards` existante avec
    le panneau d'actions révélé derrière elle. Rendu neutre (juste `children`)
    quand aucune action n'est fournie pour cette ligne. */
function SwipeableCard({ actions, children }) {
  const list = (actions ?? []).slice(0, 2)
  const swipe = useSwipeReveal(list.length > 0)
  if (!list.length) return children
  return (
    <div style={{ position: 'relative' }}>
      <div
        aria-hidden={swipe.offset === 0}
        style={{
          position: 'absolute', inset: 0, display: 'flex',
          justifyContent: 'flex-end', alignItems: 'stretch',
          overflow: 'hidden', borderRadius: '0.75rem',
        }}
      >
        {list.map((a) => {
          const Icon = a.icon
          return (
            <button
              key={a.id}
              type="button"
              title={a.label}
              aria-label={a.label}
              onClick={(e) => { e.stopPropagation(); swipe.close(); a.onClick?.() }}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                justifyContent: 'center', gap: '2px', border: 'none',
                width: `${SWIPE_REVEAL_PX / list.length}px`, minHeight: '44px',
                background: a.background ?? (a.destructive ? 'var(--color-destructive, #dc2626)' : 'var(--color-primary, #2563eb)'),
                color: '#fff', fontSize: '11px',
              }}
            >
              {Icon && <Icon className="size-4" aria-hidden="true" />}
            </button>
          )
        })}
      </div>
      <div
        {...swipe.handlers}
        style={{
          transform: swipe.offset ? `translateX(${swipe.offset}px)` : undefined,
          transition: 'transform 150ms ease',
          position: 'relative',
        }}
      >
        {children}
      </div>
    </div>
  )
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
    // VX43 — swipe-to-action sur les cartes mobiles (data-dt-cards) : maison,
    // touchstart/move/end, zéro dépendance. 100 % opt-in / rétrocompatible :
    // non fourni, le rendu des cartes reste STRICTEMENT identique à avant.
    // (row) => [{ id, label, icon, onClick, destructive, background? }]
    // (max 2 actions révélées, comme rowActions révèle ses 2 actions rapides).
    swipeActions,
    onRowClick,
    onRowPrefetch, // (row) => void — H133 : préchargement au survol/intention
    renderExpanded, // (row) => ReactNode → ligne dépliable
    /* ---- ARC49/ARC53 — Échappatoires ADDITIVES (100 % opt-in) ------------
       Le moteur est consommé par ~79 écrans ; TOUTES les propriétés ci-dessous
       sont opt-in et, non fournies, laissent le rendu STRICTEMENT identique à
       avant. Elles permettent de porter les écrans « chemin de l'argent »
       (DevisList/FactureList) — dont chaque ligne est un <tr> riche avec
       boutons à état de chargement, AlertDialog, deux panneaux dépliables
       indépendants — sur le frame du moteur sans casser leur contrat de test.

       - renderRow(row, api) : rend une LIGNE ENTIÈRE personnalisée (remplace le
         pipeline de cellules + RowActions intégrés). `api` = { rowKey, index,
         isSelected, toggleSelect, isPanelOpen(id), togglePanel(id),
         setPanel(id, open), query }. Quand fourni, le moteur n'émet ni la
         cellule sélection, ni la cellule actions, ni le chevron `renderExpanded`
         intégrés — la ligne custom en a la pleine maîtrise (panneaux multiples
         inclus, cf. `expandedPanels`).
       - renderHeaderRow(api) : rend le CONTENU de la rangée d'en-tête (<th>…</th>)
         à la place de l'en-tête intégré. `api` = { pageSelectionState,
         onToggleAllPage, allSelected }.
       - tableClassName : classes ajoutées à la <table> desktop (ex. 'data-table').
       - tableRole : rôle ARIA de la <table> (défaut 'grid' — inchangé ; passer
         'table' pour les écrans testés via getByRole('table')).
       - hideToolbar / hideMobileCards / hidePagination : masquent les chromes
         intégrés quand l'écran fournit les siens (opt-in, défaut = comportement
         historique inchangé). `renderRow` implique hideMobileCards par défaut
         (une ligne custom ne se replie pas automatiquement en carte).
       - expandedPanels : liste d'identifiants de panneaux dépliables nommés dont
         l'état d'ouverture est suivi indépendamment PAR LIGNE (ex. ['versions',
         'roof']). Déclaratif/documentaire : `renderRow` lit/écrit via l'`api`. */
    renderRow,
    renderHeaderRow,
    tableClassName,
    tableRole,
    hideToolbar = false,
    hideMobileCards = false,
    hidePagination = false,
    // eslint-disable-next-line no-unused-vars
    expandedPanels,
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
    // VX40 — pictogramme solaire illustré au lieu de l'icône Inbox générique,
    // réservé aux écrans les plus vus (opt-in, jamais par défaut).
    emptyIllustrated = false,
    // VX131(b) — CTA optionnel sur l'état vide (ex. le même bouton « Nouveau »
    // que la toolbar) : ~207/267 poses d'EmptyState n'en avaient AUCUN, y
    // compris des listes qui EN ONT un dans leur toolbar.
    emptyAction = null,
    'aria-label': ariaLabel = 'Tableau de données',
  },
  ref,
) {
  const { density } = useDensity()
  const compact = density === 'compact'

  /* ---- H129 — Hauteur de ligne par densité ----
     Le moteur de thème stocke aujourd'hui 'compact' | 'comfortable' ; on prévoit
     déjà 'spacious' pour une future densité. Compact 32 / confort 40 / spacieux 48
     (px). Cette hauteur s'applique à TOUTES les lignes corps (pas seulement en
     virtualisation) pour un rythme vertical premium et régulier. */
  const densityRowHeight = density === 'compact' ? 32 : density === 'spacious' ? 48 : 40

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
    selected, selectedKeys, selectedRows, pageKeys, pageSelectionState, onToggleRow, onToggleAllPage, clearSelection,
    view, setView,
    keyOf, pageOffset,
  } = table

  // VX249(a) — compteur de pulse PAR CELLULE (`${rowKey}:${colId}`),
  // incrémenté à chaque sauvegarde `col.onSave` réussie d'une colonne
  // `editable`. Vide et inerte pour tout écran n'utilisant pas `editable`
  // (aucune régression sur les ~79 écrans existants).
  const [pulseMap, setPulseMap] = useState({})
  const [expanded, setExpanded] = useState({})
  // ARC49 — état d'ouverture des panneaux dépliables NOMMÉS, indépendant par
  // ligne : { [rowKey]: { [panelId]: bool } }. Utilisé UNIQUEMENT par le mode
  // `renderRow` (via l'`api`) ; sans lui, cet état reste vide et inerte, donc
  // les consommateurs historiques ne voient aucune différence.
  const [panelState, setPanelState] = useState({})
  const isPanelOpen = useCallback(
    (rowKey, panelId) => !!panelState[rowKey]?.[panelId],
    [panelState],
  )
  const setPanel = useCallback((rowKey, panelId, open) => {
    setPanelState((p) => ({ ...p, [rowKey]: { ...p[rowKey], [panelId]: open } }))
  }, [])
  const togglePanel = useCallback((rowKey, panelId) => {
    setPanelState((p) => ({
      ...p,
      [rowKey]: { ...p[rowKey], [panelId]: !p[rowKey]?.[panelId] },
    }))
  }, [])
  const dragId = useRef(null)
  const scrollRef = useRef(null)
  const [scrollTop, setScrollTop] = useState(0)
  // H130 — ombre de bord d'épinglage : marquée dès qu'on défile horizontalement.
  const [scrollLeft, setScrollLeft] = useState(0)
  // N160 — ligne active pour la navigation clavier (index dans la page courante).
  const [activeRow, setActiveRow] = useState(-1)
  // NTUX8 — curseur de CELLULE (édition inline type tableur), DISTINCT du
  // curseur de LIGNE ci-dessus (N160 navigue la grille au repos ; ceci ne
  // pilote QUE les cellules `editable` déjà en édition ou visées par un
  // Tab/Entrée). `null` = aucune navigation cellule en cours.
  const [activeCell, setActiveCell] = useState(null) // { rowKey, colId } | null
  // H131 — ancre de sélection par plage (dernier index basculé sans Maj).
  const rangeAnchor = useRef(null)

  /* ---- H131 — Sélection par plage au Shift-clic ----
     On bascule chaque clé entre l'ancre et l'index cliqué pour qu'elles soient
     toutes SÉLECTIONNÉES (jamais désélectionnées par mégarde). Sans Maj, on
     bascule simplement et on déplace l'ancre. `pageKeys` est l'univers de clés
     visibles de la page courante. */
  const onRowSelect = useCallback(
    (rowIndex, key, shiftKey) => {
      if (shiftKey && rangeAnchor.current !== null && pageKeys?.length) {
        const a = Math.min(rangeAnchor.current, rowIndex)
        const b = Math.max(rangeAnchor.current, rowIndex)
        for (let i = a; i <= b; i++) {
          const k = pageKeys[i]
          if (k != null && !selected[k]) onToggleRow(k)
        }
      } else {
        onToggleRow(key)
        rangeAnchor.current = rowIndex
      }
    },
    [pageKeys, selected, onToggleRow],
  )

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

  /* ---- H130 — Offsets cumulés des colonnes épinglées (gauche ET droite) ---- */
  const leadOffset = selectable ? 44 : 0
  const actionsWidth = rowActions ? 48 : 0
  const pinEdges = useMemo(
    () => pinnedEdgeOffsets(resolvedColumns, { leadOffset, fallbackWidth: 160, actionsWidth }),
    [resolvedColumns, leadOffset, actionsWidth],
  )

  /* ---- O166 — Variables CSS de largeur, calculées une fois par rendu ---- */
  const colWidths = useMemo(() => columnWidthVars(resolvedColumns), [resolvedColumns])

  const toggleExpand = useCallback(
    (key) => setExpanded((p) => ({ ...p, [key]: !p[key] })),
    [],
  )

  /* ---- NTUX8 — Navigation clavier type tableur entre cellules éditables ----
     `editableColIds` = colonnes `editable` dans leur ORDRE AFFICHÉ (celui de
     `resolvedColumns`, qui reflète déjà réordonnancement/masquage). Tab/Maj+Tab
     avance/recule d'une colonne éditable, en enjambant la fin de ligne vers la
     colonne éditable suivante de la ligne suivante ; Entrée (`'down'`) reste
     sur la MÊME colonne, ligne suivante. En bout de grille → referme le
     curseur (repli propre, jamais d'erreur). */
  const editableColIds = useMemo(
    () => resolvedColumns.filter((c) => c.editable).map((c) => c.id),
    [resolvedColumns],
  )
  const moveActiveCell = useCallback((fromRowKey, fromColId, direction) => {
    if (!editableColIds.length) return
    const rowIdx = rows.findIndex((r, i) => keyOf(r, pageOffset + i) === fromRowKey)
    if (rowIdx < 0) return
    if (direction === 'down') {
      const nextRowIdx = rowIdx + 1
      if (nextRowIdx >= rows.length) { setActiveCell(null); return }
      setActiveCell({ rowKey: keyOf(rows[nextRowIdx], pageOffset + nextRowIdx), colId: fromColId })
      return
    }
    const colIdx = editableColIds.indexOf(fromColId)
    let nextColIdx = colIdx + (direction === 'prev' ? -1 : 1)
    let nextRowIdx = rowIdx
    if (nextColIdx >= editableColIds.length) { nextColIdx = 0; nextRowIdx += 1 }
    else if (nextColIdx < 0) { nextColIdx = editableColIds.length - 1; nextRowIdx -= 1 }
    if (nextRowIdx < 0 || nextRowIdx >= rows.length) { setActiveCell(null); return }
    setActiveCell({ rowKey: keyOf(rows[nextRowIdx], pageOffset + nextRowIdx), colId: editableColIds[nextColIdx] })
  }, [editableColIds, rows, keyOf, pageOffset])

  /* ---- O164 — Virtualisation : explicite OU auto au-delà du seuil ----
     `virtualize` force la fenêtre ; sinon on l'active automatiquement quand la
     page dépasse ~100 lignes (catalogue stock, grosses listes de leads), avec
     une hauteur de ligne fixe = celle de la densité courante (calage parfait du
     windowing). En dessous du seuil, rendu intégral comme avant. */
  const VIRTUALIZE_THRESHOLD = 100
  const effectiveRowHeight = virtualize ? rowHeight : densityRowHeight
  const effectiveVirtualize = virtualize || rows.length > VIRTUALIZE_THRESHOLD
  const win = effectiveVirtualize
    ? computeWindow({ scrollTop, viewportHeight: maxBodyHeight, rowHeight: effectiveRowHeight, rowCount: rows.length, overscan: 8 })
    : { startIndex: 0, endIndex: rows.length, paddingTop: 0, paddingBottom: 0 }
  const visibleRows = effectiveVirtualize ? rows.slice(win.startIndex, win.endIndex) : rows

  // VX135 — FLIP minimal des lignes (tri/filtre) : plafonné, désactivé sous
  // reduced-motion, jamais en mode `renderRow` custom (l'écran maîtrise sa
  // propre structure de ligne — cf. commentaire ARC49 ci-dessous).
  const prefersReducedMotion = usePrefersReducedMotion()
  const rowFlipKeys = useMemo(() => (
    typeof renderRow === 'function'
      ? []
      : visibleRows.map((row, vi) => {
        const i = (effectiveVirtualize ? win.startIndex : 0) + vi
        return keyOf(row, pageOffset + i)
      })
  ), [visibleRows, effectiveVirtualize, win.startIndex, pageOffset, keyOf, renderRow])
  const registerRowFlip = useRowFlip(rowFlipKeys, prefersReducedMotion)

  // ARC49 — en mode `renderRow`, la ligne custom possède TOUTE sa structure de
  // cellules (sélection/actions/panneaux inclus) : le moteur n'ajoute aucune
  // colonne technique, et les cellules pleine largeur (vide/erreur) couvrent
  // simplement le nombre de colonnes métier.
  const customRow = typeof renderRow === 'function'
  const colSpan = customRow
    ? resolvedColumns.length
    : resolvedColumns.length + (selectable ? 1 : 0) + (rowActions ? 1 : 0) + (renderExpanded ? 1 : 0)
  const expandable = !customRow && typeof renderExpanded === 'function'

  const cellPadY = compact ? 'py-1.5' : 'py-2.5'
  const cellPadX = 'px-3'

  /* ---- Cellule (avec surlignage + clic ligne) ---- */
  function renderCell(c, row, rowKey) {
    const value = c.accessor ? c.accessor(row) : row?.[c.id]
    // VX249(a) — `editable`/`onSave`/`validate` documentés dans le contrat de
    // colonne (H31/H32) mais jamais consommés jusqu'ici : première
    // intégration réelle, EditableCell + pulse à la cellule sauvegardée
    // (jamais un toast pour ça). Prioritaire sur `c.cell` — une colonne
    // éditable définit sa propre présentation.
    if (c.editable) {
      const cellKey = `${getRowId(row)}:${c.id}`
      return (
        <FieldSavedPulse pulseKey={pulseMap[cellKey] ?? 0}>
          <EditableCell
            value={value}
            row={row}
            format={c.cell ? (v, r) => c.cell(v, r, { query }) : undefined}
            validate={c.validate}
            onSave={async (draft, r) => {
              await c.onSave?.(draft, r)
              setPulseMap((prev) => ({ ...prev, [cellKey]: (prev[cellKey] ?? 0) + 1 }))
            }}
            // NTUX8 — navigation clavier type tableur : la cellule visée par un
            // Tab/Entrée réussi s'ouvre automatiquement (`autoEdit`), et
            // remonte sa propre position pour calculer la SUIVANTE.
            autoEdit={!!rowKey && activeCell?.rowKey === rowKey && activeCell?.colId === c.id}
            onCommitNav={rowKey ? (direction) => moveActiveCell(rowKey, c.id, direction) : undefined}
          />
        </FieldSavedPulse>
      )
    }
    if (c.cell) return c.cell(value, row, { query })
    const text = value === null || value === undefined || value === '' ? '—' : String(value)
    return <Highlighted text={text} query={c.searchable === false ? '' : query} />
  }

  /* ---- N160 — Navigation clavier de la grille ----
     Flèches haut/bas déplacent la ligne active (bornée à la page), Home/End
     vont au début/fin, Entrée ouvre la ligne active (= clic). On ne capture les
     touches QUE si le focus est sur la grille elle-même (pas dans un champ/menu
     interne), pour ne jamais voler les raccourcis natifs. */
  const onGridKeyDown = useCallback(
    (e) => {
      if (e.target !== e.currentTarget) return // évènement venu d'un enfant interactif
      const last = rows.length - 1
      if (last < 0) return
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveRow((p) => Math.min(last, p + 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveRow((p) => Math.max(0, p < 0 ? 0 : p - 1))
      } else if (e.key === 'Home') {
        e.preventDefault()
        setActiveRow(0)
      } else if (e.key === 'End') {
        e.preventDefault()
        setActiveRow(last)
      } else if (e.key === 'Enter') {
        const idx = activeRow < 0 ? 0 : activeRow
        if (rows[idx] && onRowClick) {
          e.preventDefault()
          onRowClick(rows[idx])
        }
      }
    },
    [rows, activeRow, onRowClick],
  )

  const hasToolbar = !hideToolbar
    && (searchable || savedViews || columns.some((c) => c.hideable !== false) || onExport !== undefined)

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
          tone="error"
          title="Erreur de chargement"
          description={typeof error === 'string' ? error : 'Impossible de charger les données.'}
        />
      ) : (
        <>
          {/* -------- DESKTOP : tableau -------- */}
          <div
            data-dt-table
            data-pin-shadow-left={scrollLeft > 0 ? 'true' : undefined}
            className="hidden overflow-hidden rounded-xl border border-border bg-card dt-desktop:block"
          >
            <div
              ref={scrollRef}
              data-dt-scroll
              onScroll={(e) => {
                // H130 — ombre de bord à l'apparition du défilement horizontal.
                setScrollLeft(e.currentTarget.scrollLeft)
                // O164 — position verticale pour la fenêtre virtualisée.
                if (effectiveVirtualize) setScrollTop(e.currentTarget.scrollTop)
              }}
              className="overflow-auto"
              style={effectiveVirtualize ? { maxHeight: maxBodyHeight } : undefined}
            >
              <table
                role={tableRole ?? 'grid'}
                aria-label={ariaLabel}
                aria-rowcount={totalCount}
                tabIndex={0}
                onKeyDown={onGridKeyDown}
                className={cn(
                  'w-full border-collapse text-sm focus-ring',
                  tableClassName,
                )}
                style={colWidths.vars}
              >
                {/* O166 — <colgroup> dimensionne les colonnes UNE SEULE FOIS par rendu
                    (largeur résolue depuis la variable CSS du conteneur), au lieu de
                    recalculer/poser la largeur sur CHAQUE cellule à chaque rendu.
                    ARC49 — en mode `renderRow`, la ligne custom gère elle-même sa
                    structure : pas de <colgroup> technique injecté. */}
                {!customRow && (
                <colgroup>
                  {expandable && <col style={{ width: 36 }} />}
                  {selectable && <col style={{ width: leadOffset }} />}
                  {resolvedColumns.map((c) => (
                    <col
                      key={c.id}
                      style={{
                        width: c.width != null ? (typeof c.width === 'number' ? `${c.width}px` : c.width) : undefined,
                        minWidth: c.minWidth ?? undefined,
                      }}
                    />
                  ))}
                  {rowActions && <col style={{ width: actionsWidth }} />}
                </colgroup>
                )}
                {/* ARC49 — en-tête personnalisé (opt-in) : l'écran fournit ses
                    propres <th> (mêmes libellés/classes que l'écran historique)
                    et la case « tout sélectionner ». Sans lui, en-tête intégré. */}
                {renderHeaderRow ? (
                  <thead className="sticky top-0 z-[var(--z-sticky)] bg-muted">{/* VX178 — fond opaque, plus de backdrop-blur (jank WebKit du recompositing à chaque frame de scroll) */}
                    <tr>
                      {renderHeaderRow({
                        pageSelectionState,
                        onToggleAllPage,
                        allSelected: pageSelectionState === 'all',
                      })}
                    </tr>
                  </thead>
                ) : (
                <thead className="sticky top-0 z-[var(--z-sticky)] bg-muted">{/* VX178 — fond opaque, plus de backdrop-blur (jank WebKit du recompositing à chaque frame de scroll) */}
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
                    {resolvedColumns.map((c, hi) => {
                      const dir = sortDir[c.id]
                      const sortable = c.sortable !== false && !manualSorting ? true : c.sortable
                      const pinnedLeft = c.pinned === 'left'
                      const pinnedRight = c.pinned === 'right'
                      return (
                        <th
                          key={c.id}
                          scope="col"
                          data-pinned={pinnedLeft ? 'left' : pinnedRight ? 'right' : undefined}
                          aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : sortable ? 'none' : undefined}
                          draggable={c.reorderable !== false}
                          onDragStart={() => { dragId.current = c.id }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={() => onHeaderDrop(c.id)}
                          style={{
                            minWidth: c.minWidth ?? undefined,
                            left: pinnedLeft ? pinEdges.left[c.id] : undefined,
                            right: pinnedRight ? pinEdges.right[c.id] : undefined,
                          }}
                          className={cn(
                            'whitespace-nowrap px-3 text-left align-middle font-semibold text-muted-foreground',
                            compact ? 'py-2 text-xs' : 'py-2.5 text-xs',
                            c.align === 'right' && 'text-right',
                            c.align === 'center' && 'text-center',
                            (pinnedLeft || pinnedRight) && 'sticky z-[var(--z-sticky)] bg-muted/95',
                            pinnedLeft && scrollLeft > 0 && 'shadow-[2px_0_4px_-2px_rgb(12_19_53/0.25)]',
                            pinnedRight && 'shadow-[-2px_0_4px_-2px_rgb(12_19_53/0.25)]',
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
                                className="group inline-flex items-center gap-1 rounded uppercase tracking-wide hover:text-foreground focus-ring"
                                aria-label={`Trier par ${c.header ?? c.id}`}
                              >
                                <span>{c.header ?? c.id}</span>
                                <SortIcon dir={dir} />
                              </button>
                            ) : (
                              <span className="uppercase tracking-wide">{c.header ?? c.id}</span>
                            )}
                            {/* Menu d'en-tête : épingler / masquer / déplacer (N162) */}
                            <ColumnHeaderMenu
                              column={c}
                              dispatch={dispatchColumns}
                              canMoveLeft={hi > 0}
                              canMoveRight={hi < resolvedColumns.length - 1}
                              prevId={resolvedColumns[hi - 1]?.id}
                              nextId={resolvedColumns[hi + 1]?.id}
                            />
                          </div>
                        </th>
                      )
                    })}
                    {rowActions && (
                      <th
                        scope="col"
                        data-pinned="actions-right"
                        aria-label="Actions"
                        className="sticky right-0 z-[var(--z-sticky)] w-12 bg-muted/95 px-3 shadow-[-2px_0_4px_-2px_rgb(12_19_53/0.25)]"
                      />
                    )}
                  </tr>
                </thead>
                )}

                <tbody>
                  {loading ? (
                    /* H133 — lignes-squelettes calquées sur la VRAIE disposition
                       (une cellule par colonne, hauteur de densité). Jamais de
                       spinner en parallèle : le squelette EST l'indicateur.
                       VX132 — le nombre de lignes suit `pageSize` (borné à 12
                       pour rester léger) au lieu d'un compte FIXE à 6 : passer
                       de 6 squelettes à 50 vraies lignes provoquait un saut
                       brutal de la hauteur de la table (et donc du scroll). */
                    Array.from({ length: Math.min(pageSize || 6, 12) }).map((unused, i) => (
                      <tr key={i} data-skeleton-row className="border-t border-border" style={{ height: densityRowHeight }}>
                        {expandable && <td className="px-2 py-2.5" />}
                        {selectable && <td className="px-3 py-2.5"><Skeleton className="size-4" /></td>}
                        {resolvedColumns.map((c) => (
                          <td key={c.id} className={cn('px-3 py-2.5', c.align === 'right' && 'text-right')}>
                            <Skeleton className={cn('h-4', c.align === 'right' ? 'ml-auto w-1/2' : 'w-3/4')} />
                          </td>
                        ))}
                        {rowActions && <td className="px-3 py-2.5" />}
                      </tr>
                    ))
                  ) : rows.length === 0 ? (
                    <tr>
                      <td colSpan={colSpan} className="p-0">
                        <EmptyState
                          icon={emptyIllustrated ? undefined : Inbox}
                          illustrated={emptyIllustrated}
                          title={emptyTitle}
                          description={emptyDescription}
                          action={emptyAction}
                          className="m-3 border-0"
                        />
                      </td>
                    </tr>
                  ) : (
                    <>
                      {effectiveVirtualize && win.paddingTop > 0 && (
                        <tr aria-hidden="true" style={{ height: win.paddingTop }}>
                          <td colSpan={colSpan} className="p-0" />
                        </tr>
                      )}
                      {visibleRows.map((row, vi) => {
                        const i = (effectiveVirtualize ? win.startIndex : 0) + vi
                        const rowKey = keyOf(row, pageOffset + i)
                        const isSelected = !!selected[rowKey]
                        const isExpanded = !!expanded[rowKey]
                        const isActive = i === activeRow
                        const actions = rowActions ? rowActions(row) : []
                        // ARC49 — mode ligne personnalisée : l'écran rend TOUTE la
                        // ligne (et ses panneaux dépliables) via `renderRow`. Le
                        // moteur ne fournit que l'identité + l'API de sélection /
                        // panneaux ; il n'ajoute aucune cellule technique.
                        if (customRow) {
                          return (
                            <Fragment key={rowKey}>
                              {renderRow(row, {
                                rowKey,
                                index: i,
                                isSelected,
                                toggleSelect: () => onToggleRow(rowKey),
                                isPanelOpen: (panelId) => isPanelOpen(rowKey, panelId),
                                togglePanel: (panelId) => togglePanel(rowKey, panelId),
                                setPanel: (panelId, open) => setPanel(rowKey, panelId, open),
                                query,
                              })}
                            </Fragment>
                          )
                        }
                        return (
                          <Fragment key={rowKey}>
                            <tr
                              ref={registerRowFlip(rowKey)}
                              role="row"
                              aria-rowindex={pageOffset + i + 1}
                              className={cn(
                                'group border-t border-border transition-colors',
                                onRowClick && 'cursor-pointer',
                                // H129 — survol discret (~4 %), sélection légèrement plus marquée.
                                isSelected ? 'bg-primary/5' : 'hover:bg-muted/40',
                                isActive && 'bg-accent/40 ring-1 ring-inset ring-ring/30',
                              )}
                              onClick={onRowClick ? () => onRowClick(row) : undefined}
                              onMouseEnter={onRowPrefetch ? () => onRowPrefetch(row) : undefined}
                              onFocus={onRowPrefetch ? () => onRowPrefetch(row) : undefined}
                              aria-selected={selectable ? isSelected : undefined}
                              style={{ height: effectiveRowHeight }}
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
                                      onClick={(e) => onRowSelect(i, rowKey, e.shiftKey)}
                                      aria-label={`Sélectionner la ligne ${i + 1}`}
                                    />
                                  </span>
                                </td>
                              )}
                              {resolvedColumns.map((c, ci) => {
                                const pinnedLeft = c.pinned === 'left'
                                const pinnedRight = c.pinned === 'right'
                                const firstCol = ci === 0
                                return (
                                  <td
                                    key={c.id}
                                    role="gridcell"
                                    style={{
                                      left: pinnedLeft ? pinEdges.left[c.id] : undefined,
                                      right: pinnedRight ? pinEdges.right[c.id] : undefined,
                                    }}
                                    className={cn(
                                      cellPadX, cellPadY, 'align-middle',
                                      // H129 — colonnes numériques : chiffres tabulaires + alignés à droite.
                                      c.align === 'right' && 'text-right tabular-nums',
                                      c.align === 'center' && 'text-center',
                                      c.numeric && 'text-right tabular-nums',
                                      (pinnedLeft || pinnedRight || (firstCol && c.frozen)) && 'sticky z-[1] bg-inherit',
                                      pinnedLeft && scrollLeft > 0 && 'shadow-[2px_0_4px_-2px_rgb(12_19_53/0.18)]',
                                      pinnedRight && 'shadow-[-2px_0_4px_-2px_rgb(12_19_53/0.18)]',
                                      firstCol && 'font-medium text-foreground',
                                      // NTUX8 — curseur de cellule visible (bordure focus) sur la
                                      // colonne éditable actuellement ciblée par Tab/Entrée.
                                      c.editable && activeCell?.rowKey === rowKey && activeCell?.colId === c.id
                                        && 'ring-2 ring-inset ring-ring',
                                    )}
                                  >
                                    {renderCell(c, row, rowKey)}
                                  </td>
                                )
                              })}
                              {rowActions && (
                                <td
                                  className={cn(
                                    'sticky right-0 z-[1] bg-inherit px-2',
                                    'shadow-[-2px_0_4px_-2px_rgb(12_19_53/0.18)]',
                                  )}
                                  onClick={(e) => e.stopPropagation()}
                                >
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
                      {effectiveVirtualize && win.paddingBottom > 0 && (
                        <tr aria-hidden="true" style={{ height: win.paddingBottom }}>
                          <td colSpan={colSpan} className="p-0" />
                        </tr>
                      )}
                    </>
                  )}
                </tbody>

                {/* -------- Ligne de sous-totaux -------- */}
                {summary && summaryValues && rows.length > 0 && (
                  <tfoot className="sticky bottom-0 z-[1] border-t-2 border-border bg-muted">{/* VX178 — fond opaque, blur retiré (idem thead) */}
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

          {/* -------- M154 — MOBILE : repli en cartes (< 768px) --------
             Sous le point de rupture RÉEL (VX180 — `dt-desktop:` = 768px,
             PAS l'utilitaire `sm:` par défaut = 640px), chaque ligne devient
             une carte : titre (1re colonne) en haut, métrique clé en GRAND,
             le reste des champs en libellé/valeur, et un chevron vers le
             détail. L'en-tête de tableau est masqué (la table desktop est en
             `hidden dt-desktop:block`). */}
          {/* ARC49 — le mode `renderRow` (ou `hideMobileCards`) supprime le
              repli en cartes : l'écran conserve son unique table `data-table`
              responsive (CSS) comme aujourd'hui, sans DOM carte dupliqué. */}
          {!(customRow || hideMobileCards) && (
          <div data-dt-cards className="flex flex-col gap-2 dt-desktop:hidden">
            {loading ? (
              Array.from({ length: 4 }).map((unused, i) => (
                <div key={i} data-skeleton-card className="rounded-xl border border-border bg-card p-3">
                  <Skeleton className="mb-2 h-5 w-1/2" />
                  <Skeleton className="mb-3 h-8 w-1/3" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              ))
            ) : rows.length === 0 ? (
              <EmptyState
                icon={emptyIllustrated ? undefined : Inbox}
                illustrated={emptyIllustrated}
                title={emptyTitle}
                description={emptyDescription}
                action={emptyAction}
              />
            ) : (
              rows.map((row, i) => {
                const rowKey = keyOf(row, pageOffset + i)
                const isSelected = !!selected[rowKey]
                const actions = rowActions ? rowActions(row) : []
                const mobileCols = resolvedColumns.filter((c) => c.mobileHidden !== true)
                const titleCol = mobileCols[0]
                // Métrique clé : colonne marquée `mobileMetric`, sinon 1re colonne
                // numérique / alignée à droite (montant, kWc…), sinon aucune.
                const metricCol =
                  mobileCols.find((c) => c.mobileMetric) ||
                  mobileCols.find((c, ci) => ci !== 0 && (c.numeric || c.align === 'right'))
                const restCols = mobileCols.filter((c) => c !== titleCol && c !== metricCol)
                // VX249(a) — même câblage `editable` que la table desktop
                // (renderCell) : une colonne éditable doit rester éditable
                // sur le repli carte mobile, pas seulement au-dessus de sm.
                const cellOf = (c) => {
                  const value = c.accessor ? c.accessor(row) : row?.[c.id]
                  if (c.editable) {
                    const cellKey = `${rowKey}:${c.id}`
                    return (
                      <FieldSavedPulse pulseKey={pulseMap[cellKey] ?? 0}>
                        <EditableCell
                          value={value}
                          row={row}
                          format={c.cell ? (v, r) => c.cell(v, r, { query }) : undefined}
                          validate={c.validate}
                          onSave={async (draft, r) => {
                            await c.onSave?.(draft, r)
                            setPulseMap((prev) => ({ ...prev, [cellKey]: (prev[cellKey] ?? 0) + 1 }))
                          }}
                        />
                      </FieldSavedPulse>
                    )
                  }
                  return c.cell ? c.cell(value, row, { query }) : <Highlighted text={String(value ?? '—')} query={query} />
                }
                // VX43 — swipeActions est opt-in : non fourni, SwipeableCard
                // rend `children` tel quel (aucune différence de DOM/comportement).
                const rowSwipeActions = swipeActions ? swipeActions(row) : []
                return (
                  <SwipeableCard key={rowKey} actions={rowSwipeActions}>
                  <div
                    role={onRowClick ? 'button' : undefined}
                    tabIndex={onRowClick ? 0 : undefined}
                    aria-pressed={onRowClick && selectable ? isSelected : undefined}
                    className={cn(
                      'rounded-xl border bg-card p-3 transition-colors',
                      isSelected ? 'border-primary bg-primary/5' : 'border-border',
                      onRowClick && 'cursor-pointer focus-ring',
                    )}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    onKeyDown={
                      onRowClick
                        ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              onRowClick(row)
                            }
                          }
                        : undefined
                    }
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        {titleCol && (
                          <div className="truncate text-sm font-semibold text-foreground">{cellOf(titleCol)}</div>
                        )}
                        {metricCol && (
                          <div className="mt-0.5 truncate text-2xl font-bold tabular-nums text-foreground">
                            {cellOf(metricCol)}
                          </div>
                        )}
                        {restCols.map((c) => (
                          <div key={c.id} className="mt-1 flex items-baseline justify-between gap-2">
                            <span className="shrink-0 text-xs text-muted-foreground">{c.header ?? c.id}</span>
                            <span className="min-w-0 truncate text-sm">{cellOf(c)}</span>
                          </div>
                        ))}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-1">
                          {selectable && (
                            <Checkbox checked={isSelected} onCheckedChange={() => onToggleRow(rowKey)} aria-label={`Sélectionner la ligne ${i + 1}`} />
                          )}
                          {rowActions && <RowActions actions={actions} />}
                        </div>
                        {onRowClick && (
                          <ChevronRight data-card-chevron aria-hidden="true" className="size-5 text-muted-foreground" />
                        )}
                      </div>
                    </div>
                  </div>
                  </SwipeableCard>
                )
              })
            )}
          </div>
          )}

          {/* -------- Pagination -------- */}
          {!hidePagination && !customRow && !loading && rows.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <span aria-live="polite">{range.from === 0 ? '0 sur 0' : `${range.from}–${range.to} sur ${range.total}`}</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPageIndex(0) }}
                  aria-label="Lignes par page"
                  className="h-8 rounded-md border border-input bg-card px-2 text-xs text-foreground focus-ring"
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

/** Menu contextuel d'en-tête : déplacer (N162) / épingler / masquer (H31).
    N162 — alternative au glisser-déposer : « Déplacer à gauche / à droite »
    réordonne au clavier ou au clic, sans aucun glissement (cibles ≥ 24px). */
function ColumnHeaderMenu({ column, dispatch, canMoveLeft, canMoveRight, prevId, nextId }) {
  if (column.hideable === false && column.pinnable === false && column.reorderable === false) {
    return null
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={`Options de la colonne ${column.header ?? column.id}`}
          className="grid size-6 place-items-center rounded opacity-0 transition-opacity hover:bg-accent focus-visible:opacity-100 focus-ring group-hover:opacity-60 [tr:hover_&]:opacity-60"
          onClick={(e) => e.stopPropagation()}
        >
          <MoreHorizontal className="size-3.5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {column.reorderable !== false && (
          <>
            <DropdownMenuItem
              disabled={!canMoveLeft}
              onSelect={() => prevId && dispatch({ type: 'reorder', fromId: column.id, toId: prevId })}
            >
              <ArrowLeft /> Déplacer à gauche
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={!canMoveRight}
              onSelect={() => nextId && dispatch({ type: 'reorder', fromId: nextId, toId: column.id })}
            >
              <ArrowRight /> Déplacer à droite
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        {column.pinned === 'left' ? (
          <DropdownMenuItem onSelect={() => dispatch({ type: 'pin', id: column.id, side: null })}>
            <PinOff /> Détacher
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onSelect={() => dispatch({ type: 'pin', id: column.id, side: 'left' })}>
            <Pin /> Épingler à gauche
          </DropdownMenuItem>
        )}
        {column.pinned === 'right' ? (
          <DropdownMenuItem onSelect={() => dispatch({ type: 'pin', id: column.id, side: null })}>
            <PinOff /> Détacher (droite)
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onSelect={() => dispatch({ type: 'pin', id: column.id, side: 'right' })}>
            <Pin /> Épingler à droite
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

/** H131 — Affordances de ligne : actions rapides révélées au survol
    (`opacity-0 group-hover`) + menu kebab PERSISTANT (toujours visible) qui liste
    TOUTES les actions. Le menu garantit qu'aucune action n'est inaccessible au
    clavier ou au toucher, même quand les actions rapides sont masquées. */
function RowActions({ actions = [] }) {
  if (!actions.length) return null
  const quick = actions.slice(0, 2) // 2 actions rapides au survol
  return (
    <div className="flex items-center justify-end gap-0.5">
      {/* Actions rapides : masquées jusqu'au survol/focus (toujours visibles au toucher). */}
      <div
        data-row-quick-actions
        className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100"
      >
        {quick.map((a) => {
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
      </div>
      {/* Menu kebab PERSISTANT : toutes les actions, toujours présent. */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <IconButton label="Plus d'actions sur la ligne" variant="ghost" size="icon" className="size-8">
            <MoreVertical />
          </IconButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Actions</DropdownMenuLabel>
          {actions.map((a) => {
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
    </div>
  )
}

export default DataTable
