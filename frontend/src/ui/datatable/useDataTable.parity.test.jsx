import { describe, test, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useDataTable } from './useDataTable.js'
import { filterRows, sortRows, paginateRows } from './logic.js'

/* ============================================================================
   P171 — Preuve de PARITÉ du moteur migré sur @tanstack/react-table.
   On compare la sortie du hook (rows / allRows / sélection) au pipeline PUR de
   référence (`filterRows` → `sortRows` → `paginateRows` de logic.js, inchangé).
   Si le moteur react-table divergeait d'un seul cas, ces tests virent rouge.
   ========================================================================== */

const wrapper = ({ children }) => <MemoryRouter>{children}</MemoryRouter>

const DATA = [
  { id: 1, nom: 'Kasri', ville: 'Rabat', montant: '1 200,50', statut: 'signe', canal: 'Meta' },
  { id: 2, nom: 'Benani', ville: 'Casablanca', montant: 800, statut: 'refuse', canal: 'Google' },
  { id: 3, nom: 'Éclair', ville: 'Rabat', montant: '', statut: 'signe', canal: 'Meta' },
  { id: 4, nom: 'karim', ville: 'Fès', montant: 2000, statut: 'signe', canal: 'Direct' },
  { id: 5, nom: 'Zoubir', ville: 'Rabat', montant: 50, statut: 'refuse', canal: 'Google' },
  { id: 6, nom: 'amine', ville: 'Casablanca', montant: 1200.5, statut: 'signe', canal: 'Meta' },
  { id: 7, nom: 'Naoufal', ville: null, montant: null, statut: 'refuse', canal: 'Direct' },
]

const COLUMNS = [
  { id: 'nom' }, { id: 'ville' }, { id: 'montant' }, { id: 'statut' }, { id: 'canal' },
]
const GLOBAL_IDS = COLUMNS.map((c) => c.id)
const ACCESSOR = (row, id) => row?.[id]

/** Pipeline pur de référence (l'ancien moteur). */
function reference({ data = DATA, query = '', columnFilters = {}, sorting = [], pageIndex = 0, pageSize = 25 }) {
  const filtered = filterRows(data, { query, columnFilters, globalColumns: GLOBAL_IDS }, ACCESSOR)
  const sorted = sortRows(filtered, sorting, ACCESSOR)
  const paged = paginateRows(sorted, pageIndex, pageSize)
  return { sorted, paged }
}

function renderTable(initial = {}) {
  return renderHook(
    () => useDataTable({
      data: DATA,
      columns: COLUMNS,
      globalColumns: GLOBAL_IDS,
      initialSorting: initial.sorting ?? [],
      initialColumnFilters: initial.columnFilters ?? {},
      initialPageSize: initial.pageSize ?? 25,
    }),
    { wrapper },
  )
}

const ids = (rows) => rows.map((r) => r.id)

describe('P171 parité moteur react-table vs pipeline pur', () => {
  test('aucun filtre / aucun tri : ordre d entrée préservé', () => {
    const { result } = renderTable()
    const ref = reference({})
    expect(ids(result.current.allRows)).toEqual(ids(ref.sorted))
    expect(ids(result.current.rows)).toEqual(ids(ref.paged))
    expect(result.current.totalCount).toBe(DATA.length)
  })

  test('tri ascendant texte (accents fr) identique', () => {
    const sorting = [{ id: 'nom', desc: false }]
    const { result } = renderTable({ sorting })
    expect(ids(result.current.allRows)).toEqual(ids(reference({ sorting }).sorted))
  })

  test('tri descendant numérique : vides traités identiquement', () => {
    const sorting = [{ id: 'montant', desc: true }]
    const { result } = renderTable({ sorting })
    expect(ids(result.current.allRows)).toEqual(ids(reference({ sorting }).sorted))
  })

  test('tri multi-colonnes (statut puis montant) identique', () => {
    const sorting = [{ id: 'statut', desc: false }, { id: 'montant', desc: true }]
    const { result } = renderTable({ sorting })
    expect(ids(result.current.allRows)).toEqual(ids(reference({ sorting }).sorted))
  })

  test('recherche globale (accents/casse) identique', () => {
    const { result } = renderTable()
    act(() => result.current.onQueryChange('rab'))
    expect(ids(result.current.allRows)).toEqual(ids(reference({ query: 'rab' }).sorted))
    act(() => result.current.onQueryChange('eclair'))
    expect(ids(result.current.allRows)).toEqual(ids(reference({ query: 'eclair' }).sorted))
  })

  test('filtre par colonne (sous-chaîne + multi-select) identique', () => {
    const { result } = renderTable()
    act(() => result.current.onColumnFilterChange('statut', 'signe'))
    expect(ids(result.current.allRows)).toEqual(
      ids(reference({ columnFilters: { statut: 'signe' } }).sorted),
    )
    act(() => result.current.onColumnFilterChange('canal', ['meta', 'google']))
    expect(ids(result.current.allRows)).toEqual(
      ids(reference({ columnFilters: { statut: 'signe', canal: ['meta', 'google'] } }).sorted),
    )
  })

  test('filtre + tri + pagination combinés identiques', () => {
    const sorting = [{ id: 'nom', desc: false }]
    const { result } = renderTable({ sorting, pageSize: 2 })
    act(() => {
      result.current.onColumnFilterChange('statut', 'signe')
    })
    const ref = reference({ columnFilters: { statut: 'signe' }, sorting, pageSize: 2, pageIndex: 0 })
    expect(ids(result.current.rows)).toEqual(ids(ref.paged))
    act(() => result.current.setPageIndex(1))
    const ref2 = reference({ columnFilters: { statut: 'signe' }, sorting, pageSize: 2, pageIndex: 1 })
    expect(ids(result.current.rows)).toEqual(ids(ref2.paged))
  })

  test('onSort : cycle asc → desc → aucun (parité avec toggleSort)', () => {
    const { result } = renderTable()
    act(() => result.current.onSort('montant'))
    expect(result.current.sorting).toEqual([{ id: 'montant', desc: false }])
    expect(ids(result.current.allRows)).toEqual(ids(reference({ sorting: [{ id: 'montant', desc: false }] }).sorted))
    act(() => result.current.onSort('montant'))
    expect(result.current.sorting).toEqual([{ id: 'montant', desc: true }])
    act(() => result.current.onSort('montant'))
    expect(result.current.sorting).toEqual([])
  })

  test('sélection « tout sur la page » + clés cohérentes', () => {
    const { result } = renderTable({ pageSize: 3 })
    act(() => result.current.onToggleAllPage())
    expect(result.current.pageSelectionState).toBe('all')
    const expectedKeys = reference({ pageSize: 3 }).paged.map((r) => String(r.id))
    expect(result.current.selectedKeys.sort()).toEqual(expectedKeys.sort())
    expect(ids(result.current.selectedRows).sort()).toEqual(
      reference({ pageSize: 3 }).paged.map((r) => r.id).sort(),
    )
  })

  test('résumé (sous-totaux) calculé sur l ensemble filtré', () => {
    const { result } = renderHook(
      () => useDataTable({
        data: DATA, columns: COLUMNS, globalColumns: GLOBAL_IDS,
        summary: { montant: 'sum' },
      }),
      { wrapper },
    )
    // 1200.5 + 800 + 0 + 2000 + 50 + 1200.5 + 0 = 5251
    expect(result.current.summaryValues.montant).toBeCloseTo(5251, 5)
  })
})
