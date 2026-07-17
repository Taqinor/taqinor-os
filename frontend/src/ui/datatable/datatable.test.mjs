import test from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeForSort, compareValues, sortRows, toggleSort,
  foldText, matchesText, globalFilterPredicate, columnFilterPredicate, filterRows,
  highlightSegments,
  pageCount, clampPageIndex, pageRange, frenchPageLabel, paginateRows,
  initColumnState, columnStateReducer, moveItem, resolveColumns,
  summarize, splitTVA,
  toggleSelected, setAllSelected, selectionState,
  computeWindow,
  pinnedEdgeOffsets, columnWidthVars,
  groupRows,
} from './logic.js'
import {
  encodeSort, decodeSort, encodeFilters, decodeFilters,
  encodeState, decodeState, managedKeys,
} from './urlState.js'
import { escapeCSVCell, rowsToCSV, rowsToTSV, exportFileName, UTF8_BOM } from './csv.js'

/* ============================== TRI ============================== */

test('normalizeForSort: nombres, dates, booléens, texte, vide', () => {
  assert.equal(normalizeForSort(42).kind, 'number')
  assert.equal(normalizeForSort('1 234,56').kind, 'number')
  assert.equal(normalizeForSort('abc').kind, 'text')
  assert.equal(normalizeForSort('').kind, 'empty')
  assert.equal(normalizeForSort(null).kind, 'empty')
  assert.equal(normalizeForSort(true).v, 1)
  assert.equal(normalizeForSort(new Date('2026-01-01')).kind, 'number')
  assert.equal(normalizeForSort(NaN).kind, 'empty')
})

test('compareValues: numérique, texte fr, vides en fin', () => {
  assert.ok(compareValues(1, 2) < 0)
  assert.ok(compareValues('10', '9') > 0) // numérique, pas lexical
  assert.ok(compareValues('éclair', 'zoo') < 0) // accents fr
  assert.equal(compareValues('a', 'a'), 0)
  // vides toujours après, quel que soit l'autre
  assert.ok(compareValues('', 'x') > 0)
  assert.ok(compareValues('x', '') < 0)
  assert.equal(compareValues('', ''), 0)
})

test('sortRows: tri multi-colonnes stable, ne mute pas', () => {
  const rows = [
    { v: 'beta', n: 2 },
    { v: 'alpha', n: 2 },
    { v: 'alpha', n: 1 },
  ]
  const copy = JSON.parse(JSON.stringify(rows))
  const out = sortRows(rows, [{ id: 'n', desc: false }, { id: 'v', desc: false }])
  assert.deepEqual(out.map((r) => `${r.n}${r.v}`), ['1alpha', '2alpha', '2beta'])
  assert.deepEqual(rows, copy) // entrée intacte
  // tri desc
  const desc = sortRows(rows, [{ id: 'n', desc: true }])
  assert.equal(desc[0].n, 2)
  // tri vide → copie inchangée
  assert.deepEqual(sortRows(rows, []), rows)
})

test('sortRows: stabilité sur égalité (ordre d entrée conservé)', () => {
  const rows = [{ id: 1, g: 'a' }, { id: 2, g: 'a' }, { id: 3, g: 'a' }]
  const out = sortRows(rows, [{ id: 'g', desc: false }])
  assert.deepEqual(out.map((r) => r.id), [1, 2, 3])
})

test('toggleSort: cycle asc → desc → aucun (mono)', () => {
  let s = []
  s = toggleSort(s, 'x')
  assert.deepEqual(s, [{ id: 'x', desc: false }])
  s = toggleSort(s, 'x')
  assert.deepEqual(s, [{ id: 'x', desc: true }])
  s = toggleSort(s, 'x')
  assert.deepEqual(s, [])
  // changer de colonne en mono → remplace
  s = toggleSort([{ id: 'a', desc: true }], 'b')
  assert.deepEqual(s, [{ id: 'b', desc: false }])
})

test('toggleSort: mode multi (Maj+clic) empile sans effacer', () => {
  let s = [{ id: 'a', desc: false }]
  s = toggleSort(s, 'b', { multi: true })
  assert.deepEqual(s, [{ id: 'a', desc: false }, { id: 'b', desc: false }])
  s = toggleSort(s, 'b', { multi: true })
  assert.deepEqual(s, [{ id: 'a', desc: false }, { id: 'b', desc: true }])
  s = toggleSort(s, 'b', { multi: true })
  assert.deepEqual(s, [{ id: 'a', desc: false }])
})

/* ============================== FILTRES ============================== */

test('foldText: minuscule + sans accents', () => {
  assert.equal(foldText('Éclairé'), 'eclaire')
  assert.equal(foldText('ÀÉÎÔÛ'), 'aeiou')
  assert.equal(foldText(null), '')
})

test('matchesText: insensible accents/casse', () => {
  assert.equal(matchesText('Société Générale', foldText('societe')), true)
  assert.equal(matchesText('ABC', foldText('bc')), true)
  assert.equal(matchesText('ABC', foldText('xy')), false)
  assert.equal(matchesText('quoi', ''), true) // aiguille vide → tout passe
})

test('globalFilterPredicate: cherche sur colonnes listées', () => {
  const row = { nom: 'Kasri', ville: 'Rabat', note: 'VIP' }
  assert.equal(globalFilterPredicate(row, 'rab', ['nom', 'ville']), true)
  assert.equal(globalFilterPredicate(row, 'vip', ['nom', 'ville']), false) // note pas listée
  assert.equal(globalFilterPredicate(row, '', ['nom']), true)
})

test('columnFilterPredicate: sous-chaîne + multi-select tableau', () => {
  const row = { statut: 'signe', canal: 'Meta' }
  assert.equal(columnFilterPredicate(row, { statut: 'sig' }), true)
  assert.equal(columnFilterPredicate(row, { statut: 'refuse' }), false)
  // tableau = appartenance exacte (repliée)
  assert.equal(columnFilterPredicate(row, { canal: ['meta', 'google'] }), true)
  assert.equal(columnFilterPredicate(row, { canal: ['google'] }), false)
  assert.equal(columnFilterPredicate(row, { canal: [] }), true) // vide → neutre
  assert.equal(columnFilterPredicate(row, { statut: '' }), true)
})

test('filterRows: combine global + colonne', () => {
  const rows = [
    { nom: 'Kasri', statut: 'signe' },
    { nom: 'Benani', statut: 'refuse' },
    { nom: 'Karim', statut: 'signe' },
  ]
  const out = filterRows(rows, {
    query: 'ka',
    globalColumns: ['nom'],
    columnFilters: { statut: 'signe' },
  })
  assert.deepEqual(out.map((r) => r.nom), ['Kasri', 'Karim'])
})

/* ============================== SURLIGNAGE ============================== */

test('highlightSegments: découpe correspondances, préserve la casse source', () => {
  const seg = highlightSegments('Société Kasri', 'kasri')
  assert.deepEqual(seg, [
    { text: 'Société ', match: false },
    { text: 'Kasri', match: true },
  ])
  // accents : recherche sans accent surligne le texte accentué
  const seg2 = highlightSegments('Éclair', 'eclair')
  assert.equal(seg2[0].match, true)
  assert.equal(seg2[0].text, 'Éclair')
  // sans correspondance → 1 segment non surligné
  assert.deepEqual(highlightSegments('abc', 'z'), [{ text: 'abc', match: false }])
  // requête vide
  assert.deepEqual(highlightSegments('abc', ''), [{ text: 'abc', match: false }])
  // occurrences multiples
  const multi = highlightSegments('aXaXa', 'x')
  assert.equal(multi.filter((s) => s.match).length, 2)
})

/* ============================== PAGINATION ============================== */

test('pageCount / clampPageIndex', () => {
  assert.equal(pageCount(0, 25), 1)
  assert.equal(pageCount(25, 25), 1)
  assert.equal(pageCount(26, 25), 2)
  assert.equal(pageCount(619, 50), 13)
  assert.equal(pageCount(100, 0), 1) // pageSize 0 → tout sur 1 page
  assert.equal(clampPageIndex(99, 26, 25), 1) // borné au dernier
  assert.equal(clampPageIndex(-5, 26, 25), 0)
})

test('pageRange / frenchPageLabel: « X–Y sur N »', () => {
  assert.deepEqual(pageRange(0, 25, 619), { from: 1, to: 25, total: 619 })
  assert.deepEqual(pageRange(1, 25, 619), { from: 26, to: 50, total: 619 })
  // dernière page partielle
  assert.deepEqual(pageRange(24, 25, 619), { from: 601, to: 619, total: 619 })
  assert.deepEqual(pageRange(0, 25, 0), { from: 0, to: 0, total: 0 })
  assert.equal(frenchPageLabel(0, 25, 619), '1–25 sur 619')
  assert.equal(frenchPageLabel(24, 25, 619), '601–619 sur 619')
  assert.equal(frenchPageLabel(0, 25, 0), '0 sur 0')
})

test('paginateRows: tranche correcte + borne hors limite', () => {
  const rows = Array.from({ length: 60 }, (unused, i) => i)
  assert.deepEqual(paginateRows(rows, 0, 25).length, 25)
  assert.deepEqual(paginateRows(rows, 2, 25), [50, 51, 52, 53, 54, 55, 56, 57, 58, 59])
  assert.deepEqual(paginateRows(rows, 99, 25), rows.slice(50)) // borné
  assert.equal(paginateRows(rows, 0, 0).length, 60) // 0 → tout
})

/* ============================== ÉTAT COLONNES ============================== */

const COLS = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]

test('initColumnState', () => {
  const s = initColumnState(COLS)
  assert.deepEqual(s.order, ['a', 'b', 'c', 'd'])
  assert.deepEqual(s.hidden, {})
  assert.deepEqual(s.pinned, {})
})

test('columnStateReducer: visibilité / pin / resize', () => {
  let s = initColumnState(COLS)
  s = columnStateReducer(s, { type: 'toggleVisibility', id: 'b' })
  assert.equal(s.hidden.b, true)
  s = columnStateReducer(s, { type: 'toggleVisibility', id: 'b' })
  assert.equal(s.hidden.b, undefined)
  s = columnStateReducer(s, { type: 'setVisibility', id: 'c', visible: false })
  assert.equal(s.hidden.c, true)
  s = columnStateReducer(s, { type: 'pin', id: 'a', side: 'left' })
  assert.equal(s.pinned.a, 'left')
  s = columnStateReducer(s, { type: 'pin', id: 'a', side: null })
  assert.equal(s.pinned.a, undefined)
  s = columnStateReducer(s, { type: 'resize', id: 'a', width: 200 })
  assert.equal(s.widths.a, 200)
  s = columnStateReducer(s, { type: 'resize', id: 'a', width: 10, min: 80 })
  assert.equal(s.widths.a, 80) // borne min
})

test('moveItem / reorder', () => {
  assert.deepEqual(moveItem(['a', 'b', 'c'], 'c', 'a'), ['c', 'a', 'b'])
  assert.deepEqual(moveItem(['a', 'b', 'c'], 'a', 'c'), ['b', 'a', 'c'])
  assert.deepEqual(moveItem(['a', 'b', 'c'], 'a', 'a'), ['a', 'b', 'c'])
  let s = initColumnState(COLS)
  s = columnStateReducer(s, { type: 'reorder', fromId: 'd', toId: 'a' })
  assert.deepEqual(s.order, ['d', 'a', 'b', 'c'])
})

test('resolveColumns: ordre + visibilité + pin gauche/droite', () => {
  let s = initColumnState(COLS)
  s = columnStateReducer(s, { type: 'toggleVisibility', id: 'b' }) // masque b
  s = columnStateReducer(s, { type: 'pin', id: 'c', side: 'left' })
  s = columnStateReducer(s, { type: 'pin', id: 'd', side: 'right' })
  const resolved = resolveColumns(COLS, s)
  assert.deepEqual(resolved.map((c) => c.id), ['c', 'a', 'd']) // b masqué, c pinned-left, d pinned-right
  assert.equal(resolved[0].pinned, 'left')
})

test('resolveColumns: colonne ajoutée hors ordre va en fin', () => {
  const s = initColumnState(COLS)
  const extended = [...COLS, { id: 'e' }]
  const resolved = resolveColumns(extended, s)
  assert.equal(resolved[resolved.length - 1].id, 'e')
})

/* ============================== RÉSUMÉ / TVA ============================== */

test('summarize: sum / avg / count / fn, parse fr-FR', () => {
  const rows = [
    { total: '1 000,00', q: 2 },
    { total: 2000, q: 3 },
    { total: null, q: 1 },
  ]
  const out = summarize(rows, { total: 'sum', q: 'avg', n: 'count' })
  assert.equal(out.total, 3000)
  assert.equal(out.q, 2) // (2+3+1)/3
  assert.equal(out.n, 3)
  const custom = summarize(rows, { total: (vals) => Math.max(...vals) })
  assert.equal(custom.total, 2000)
})

test('splitTVA: décompose TTC en HT + TVA', () => {
  const { ht, tva, ttc } = splitTVA(1200, 20)
  assert.equal(ht, 1000)
  assert.equal(tva, 200)
  assert.equal(ttc, 1200)
  assert.deepEqual(splitTVA(null), { ht: null, tva: null, ttc: null })
})

/* ============================== SÉLECTION ============================== */

test('toggleSelected / setAllSelected / selectionState', () => {
  let sel = {}
  sel = toggleSelected(sel, 'r1')
  assert.equal(sel.r1, true)
  sel = toggleSelected(sel, 'r1')
  assert.equal(sel.r1, undefined)
  sel = setAllSelected({}, ['a', 'b', 'c'], true)
  assert.equal(selectionState(sel, ['a', 'b', 'c']), 'all')
  sel = setAllSelected(sel, ['b'], false)
  assert.equal(selectionState(sel, ['a', 'b', 'c']), 'some')
  assert.equal(selectionState({}, ['a', 'b']), 'none')
  assert.equal(selectionState({}, []), 'none')
})

/* ============================== ÉPINGLAGE / LARGEURS (H130/O166) ============================== */

test('pinnedEdgeOffsets: décalages cumulés gauche et droite', () => {
  const cols = [
    { id: 'nom', pinned: 'left', width: 200 },
    { id: 'ville', width: 140 },
    { id: 'montant' },
    { id: 'actions', pinned: 'right', width: 80 },
  ]
  const { left, right } = pinnedEdgeOffsets(cols, { leadOffset: 44, fallbackWidth: 160, actionsWidth: 48 })
  assert.equal(left.nom, 44) // après la gouttière de sélection
  // une seule colonne épinglée à droite, commence après la colonne actions (48)
  assert.equal(right.actions, 48)
})

test('pinnedEdgeOffsets: deux colonnes épinglées à gauche se cumulent', () => {
  const cols = [
    { id: 'a', pinned: 'left', width: 100 },
    { id: 'b', pinned: 'left', width: 120 },
    { id: 'c' },
  ]
  const { left } = pinnedEdgeOffsets(cols, { leadOffset: 0 })
  assert.equal(left.a, 0)
  assert.equal(left.b, 100) // collée juste après a
})

test('columnWidthVars: variables CSS par colonne avec largeur', () => {
  const cols = [{ id: 'nom', width: 200 }, { id: 'ville' }, { id: 'montant', width: '10rem' }]
  const { vars, get } = columnWidthVars(cols)
  assert.equal(vars['--dt-col-nom'], '200px')
  assert.equal(vars['--dt-col-montant'], '10rem')
  assert.equal(vars['--dt-col-ville'], undefined) // pas de largeur → pas de var
  assert.equal(get('nom'), 'var(--dt-col-nom)')
  assert.equal(get('ville'), undefined)
})

/* ============================== VIRTUALISATION ============================== */

test('computeWindow: fenêtre + paddings cohérents', () => {
  const w = computeWindow({ scrollTop: 0, viewportHeight: 400, rowHeight: 40, rowCount: 619, overscan: 5 })
  assert.equal(w.startIndex, 0)
  assert.equal(w.paddingTop, 0)
  assert.ok(w.endIndex >= 10 && w.endIndex <= 20)
  // défilé au milieu
  const mid = computeWindow({ scrollTop: 4000, viewportHeight: 400, rowHeight: 40, rowCount: 619, overscan: 5 })
  assert.equal(mid.startIndex, 95) // floor(4000/40)=100, -5 overscan
  assert.equal(mid.paddingTop, 95 * 40)
  assert.ok(mid.paddingBottom > 0)
  // liste vide
  assert.deepEqual(computeWindow({ scrollTop: 0, viewportHeight: 400, rowHeight: 40, rowCount: 0 }), {
    startIndex: 0, endIndex: 0, paddingTop: 0, paddingBottom: 0,
  })
  // somme paddings + fenêtre = hauteur totale
  const total = 619 * 40
  assert.equal(mid.paddingTop + (mid.endIndex - mid.startIndex) * 40 + mid.paddingBottom, total)
})

/* ============================== URL STATE ============================== */

test('encodeSort / decodeSort round-trip', () => {
  const s = [{ id: 'montant', desc: true }, { id: 'date', desc: false }]
  assert.equal(encodeSort(s), 'montant:desc,date:asc')
  assert.deepEqual(decodeSort('montant:desc,date:asc'), s)
  assert.equal(encodeSort([]), '')
  assert.deepEqual(decodeSort(''), [])
})

test('encodeFilters / decodeFilters round-trip (string + tableau)', () => {
  const f = { statut: 'signe', canal: ['meta', 'google'] }
  const enc = encodeFilters(f)
  assert.deepEqual(decodeFilters(enc), f)
  // valeurs vides exclues
  assert.equal(encodeFilters({ statut: '', canal: [] }), '')
  assert.deepEqual(decodeFilters(''), {})
})

test('encodeState: omet les valeurs par défaut (page 1 absente)', () => {
  const params = encodeState({
    sorting: [{ id: 'a', desc: true }],
    query: 'kasri',
    columnFilters: { statut: 'signe' },
    pageIndex: 0,
    pageSize: 25,
    view: 'a-relancer',
  })
  assert.equal(params.sort, 'a:desc')
  assert.equal(params.q, 'kasri')
  assert.equal(params.f, 'statut:signe')
  assert.equal(params.page, null) // page 1 omise
  assert.equal(params.size, '25')
  assert.equal(params.view, 'a-relancer')
  // page > 1 présente (1-based dans l'URL)
  assert.equal(encodeState({ pageIndex: 2 }).page, '3')
})

test('decodeState: lit depuis URLSearchParams, page 0-based', () => {
  const sp = new URLSearchParams('sort=a:desc&q=kasri&f=statut:signe&page=3&size=50&view=signes')
  const st = decodeState(sp)
  assert.deepEqual(st.sorting, [{ id: 'a', desc: true }])
  assert.equal(st.query, 'kasri')
  assert.deepEqual(st.columnFilters, { statut: 'signe' })
  assert.equal(st.pageIndex, 2) // 3 → index 2
  assert.equal(st.pageSize, 50)
  assert.equal(st.view, 'signes')
})

test('encode/decode state round-trip via URLSearchParams + préfixe', () => {
  const state = {
    sorting: [{ id: 'montant', desc: true }],
    query: 'rab',
    columnFilters: { canal: ['meta', 'google'] },
    pageIndex: 4,
    pageSize: 25,
    view: 'en-retard',
  }
  const params = encodeState(state, 'leads')
  const sp = new URLSearchParams()
  for (const [key, val] of Object.entries(params)) if (val != null) sp.set(key, val)
  const back = decodeState(sp, 'leads')
  assert.deepEqual(back.sorting, state.sorting)
  assert.equal(back.query, state.query)
  assert.deepEqual(back.columnFilters, state.columnFilters)
  assert.equal(back.pageIndex, state.pageIndex)
  assert.equal(back.pageSize, state.pageSize)
  assert.equal(back.view, state.view)
  assert.deepEqual(managedKeys('leads'), ['leads.sort', 'leads.q', 'leads.f', 'leads.page', 'leads.size', 'leads.view'])
})

/* ============================== CSV ============================== */

test('escapeCSVCell: guillemets / virgules / sauts de ligne', () => {
  assert.equal(escapeCSVCell('simple'), 'simple')
  assert.equal(escapeCSVCell('a,b'), '"a,b"')
  assert.equal(escapeCSVCell('he said "hi"'), '"he said ""hi"""')
  assert.equal(escapeCSVCell('ligne1\nligne2'), '"ligne1\nligne2"')
  assert.equal(escapeCSVCell(null), '')
  assert.equal(escapeCSVCell(undefined), '')
})

// ERR97 — Garde anti-injection de formules (= + - @) : préfixe une apostrophe.
test('escapeCSVCell: neutralise les formules =/+/-/@ (anti-injection)', () => {
  assert.equal(escapeCSVCell('=SUM(A1:A2)'), "'=SUM(A1:A2)")
  assert.equal(escapeCSVCell('+1+2'), "'+1+2")
  assert.equal(escapeCSVCell('-1'), "'-1")
  assert.equal(escapeCSVCell('@cmd'), "'@cmd")
  // Une formule contenant aussi un délimiteur reste préfixée PUIS quotée RFC-4180
  assert.equal(escapeCSVCell('=1,2'), '"\'=1,2"')
  // Un texte ordinaire n'est jamais préfixé
  assert.equal(escapeCSVCell('valeur'), 'valeur')
  assert.equal(escapeCSVCell('a-b'), 'a-b') // le tiret au milieu n'est pas une formule
  // Un nombre négatif numérique (pas une chaîne) n'est pas concerné par String()
  assert.equal(escapeCSVCell(42), '42')
})

/* ============================== IDENTITÉ DE LIGNE (ERR96) ============================== */

// Le getRowId par défaut retombe sur l'index quand la ligne n'a pas d'id. Cet
// index DOIT être le même repère (global) pour les clés de page et la sélection,
// sinon une ligne sans id est sélectionnée à tort. On reproduit ici les deux
// chemins de génération de clés du hook pour verrouiller la cohérence.
const defaultGetRowId = (row, i) => row?.id ?? i
const keyOf = (row, globalIndex) => String(defaultGetRowId(row, globalIndex))

test('identité de ligne : clés de page = clés de sélection (index global, sans id)', () => {
  // 5 lignes SANS id, pagination cliente, page de 2, deuxième page.
  const sorted = [{ v: 'a' }, { v: 'b' }, { v: 'c' }, { v: 'd' }, { v: 'e' }]
  const pageSize = 2
  const pageIndex = 1
  const pageOffset = pageIndex * pageSize // 2
  const paged = sorted.slice(pageOffset, pageOffset + pageSize) // [c, d]

  // Clés de page : index GLOBAL (pageOffset + i)
  const pageKeys = paged.map((row, i) => keyOf(row, pageOffset + i))
  assert.deepEqual(pageKeys, ['2', '3'])

  // On sélectionne « tout sur la page » → ces clés.
  const selected = Object.fromEntries(pageKeys.map((k) => [k, true]))

  // Sélection : filtre sur l'univers complet avec l'index GLOBAL → mêmes lignes.
  const selectedRows = sorted.filter((row, i) => selected[keyOf(row, i)])
  assert.deepEqual(selectedRows.map((r) => r.v), ['c', 'd'])
})

test('identité de ligne : un index local mélangé sélectionnerait les mauvaises lignes', () => {
  // Démontre le bug d'origine : si les clés de page utilisent l'index LOCAL
  // (0,1) tandis que la sélection utilise l'index GLOBAL, on sélectionne les
  // lignes 0 et 1 (a, b) au lieu de la page courante (c, d).
  const sorted = [{ v: 'a' }, { v: 'b' }, { v: 'c' }, { v: 'd' }, { v: 'e' }]
  const pageSize = 2
  const pageOffset = 1 * pageSize
  const paged = sorted.slice(pageOffset, pageOffset + pageSize)
  const buggyPageKeys = paged.map((row, i) => keyOf(row, i)) // index LOCAL (bug)
  const selected = Object.fromEntries(buggyPageKeys.map((k) => [k, true]))
  const selectedRows = sorted.filter((row, i) => selected[keyOf(row, i)])
  // Les mauvaises lignes seraient sélectionnées — c'est exactement ce qu'ERR96 corrige.
  assert.deepEqual(selectedRows.map((r) => r.v), ['a', 'b'])
})

test('identité de ligne : un id explicite reste stable quel que soit l index', () => {
  const sorted = [{ id: 'x' }, { id: 'y' }, { id: 'z' }]
  // Quelle que soit la valeur d'index passée, la clé suit l'id.
  assert.equal(keyOf(sorted[0], 0), 'x')
  assert.equal(keyOf(sorted[0], 99), 'x')
})

test('rowsToCSV: en-têtes + valeurs + exportValue + BOM', () => {
  const rows = [
    { nom: 'Kasri, R', montant: 1000 },
    { nom: 'Benani', montant: 2000 },
  ]
  const cols = [
    { id: 'nom', header: 'Nom' },
    { id: 'montant', header: 'Montant', exportValue: (r) => `${r.montant} MAD` },
  ]
  const csv = rowsToCSV(rows, cols, { bom: false })
  const lines = csv.split('\r\n')
  assert.equal(lines[0], 'Nom,Montant')
  assert.equal(lines[1], '"Kasri, R",1000 MAD')
  assert.equal(lines[2], 'Benani,2000 MAD')
  // BOM présent par défaut
  assert.ok(rowsToCSV(rows, cols).startsWith(UTF8_BOM))
  assert.equal(UTF8_BOM.charCodeAt(0), 0xfeff)
})

test('rowsToTSV: tabulations, aucun BOM, cellules quotées (collage Excel)', () => {
  const rows = [
    { nom: 'Kasri, R', ville: 'Rabat', montant: 1000 },
    { nom: 'Ben\tani', ville: 'Casa', montant: 2000 },
  ]
  const cols = [
    { id: 'nom', header: 'Nom' },
    { id: 'ville', header: 'Ville' },
    { id: 'montant', header: 'Montant', exportValue: (r) => `${r.montant} MAD` },
  ]
  const tsv = rowsToTSV(rows, cols)
  const lines = tsv.split('\r\n')
  // Séparateur = tabulation ; une virgule NE force PAS le quoting (délimiteur tab)
  assert.equal(lines[0], 'Nom\tVille\tMontant')
  assert.equal(lines[1], 'Kasri, R\tRabat\t1000 MAD')
  // Une cellule contenant une tabulation est quotée (RFC-4180 avec délimiteur tab)
  assert.equal(lines[2], '"Ben\tani"\tCasa\t2000 MAD')
  // Aucun BOM : le presse-papiers TSV n'en a pas besoin
  assert.ok(!tsv.startsWith(UTF8_BOM))
})

test('exportFileName: base assainie + horodatage', () => {
  const name = exportFileName('Leads à relancer', { date: new Date('2026-06-18T00:00:00') })
  assert.equal(name, 'Leads-relancer-2026-06-18.csv')
  assert.match(exportFileName(), /^export-\d{4}-\d{2}-\d{2}\.csv$/)
  assert.match(exportFileName('x', { ext: 'xlsx' }), /\.xlsx$/)
})

/* ============================== NTUX19 — GROUPEMENT DE LIGNES ============================== */

test('groupRows: regroupe par colonne, ordre de PREMIÈRE APPARITION des groupes', () => {
  const rows = [
    { id: 1, statut: 'envoye' },
    { id: 2, statut: 'accepte' },
    { id: 3, statut: 'envoye' },
    { id: 4, statut: 'refuse' },
    { id: 5, statut: 'accepte' },
  ]
  const groups = groupRows(rows, 'statut')
  assert.deepEqual(groups.map((g) => g.key), ['envoye', 'accepte', 'refuse'])
  assert.deepEqual(groups[0].rows.map((r) => r.id), [1, 3])
  assert.deepEqual(groups[1].rows.map((r) => r.id), [2, 5])
  assert.deepEqual(groups[2].rows.map((r) => r.id), [4])
})

test('groupRows: valeurs vides/null/undefined regroupent sous la clé \'\'', () => {
  const rows = [{ id: 1, x: null }, { id: 2, x: '' }, { id: 3, x: undefined }, { id: 4, x: 'a' }]
  const groups = groupRows(rows, 'x')
  assert.equal(groups.length, 2)
  assert.equal(groups[0].key, '')
  assert.deepEqual(groups[0].rows.map((r) => r.id), [1, 2, 3])
  assert.equal(groups[1].key, 'a')
})

test('groupRows: liste vide/absente → aucun groupe (jamais une erreur)', () => {
  assert.deepEqual(groupRows([], 'x'), [])
  assert.deepEqual(groupRows(undefined, 'x'), [])
})

test('groupRows: respecte un accessor personnalisé (comme les autres fonctions du moteur)', () => {
  const rows = [{ id: 1, meta: { statut: 'A' } }, { id: 2, meta: { statut: 'B' } }, { id: 3, meta: { statut: 'A' } }]
  const accessor = (row, id) => row.meta?.[id]
  const groups = groupRows(rows, 'statut', accessor)
  assert.deepEqual(groups.map((g) => g.key), ['A', 'B'])
})
