import test from 'node:test'
import assert from 'node:assert/strict'

import {
  rows,
  buildDocumentParams,
  normalizeQuery,
  hasActiveSearch,
  filterDocuments,
} from './search.js'

test('rows accepte un tableau brut, une page DRF, ou {results}', () => {
  assert.deepEqual(rows({ data: [1, 2] }), [1, 2])
  assert.deepEqual(rows({ data: { results: [3] } }), [3])
  // /semantique renvoie { mode, results }
  assert.deepEqual(rows({ data: { mode: 'plein-texte', results: [9] } }), [9])
  assert.deepEqual(rows({ data: null }), [])
  assert.deepEqual(rows(undefined), [])
})

test('buildDocumentParams n’émet que les filtres renseignés', () => {
  assert.deepEqual(buildDocumentParams({}), {})
  assert.deepEqual(buildDocumentParams({ folder: 5 }), { folder: 5 })
  assert.deepEqual(
    buildDocumentParams({ folder: '', tag: 3, coffre: 'null' }),
    { tag: 3, coffre: 'null' },
  )
})

test('normalizeQuery trim + borne, vide pour des espaces', () => {
  assert.equal(normalizeQuery('  onduleur  '), 'onduleur')
  assert.equal(normalizeQuery('   '), '')
  assert.equal(normalizeQuery(null), '')
  assert.equal(normalizeQuery('x'.repeat(300)).length, 200)
})

test('hasActiveSearch détecte requête/tag/coffre', () => {
  assert.equal(hasActiveSearch({}), false)
  assert.equal(hasActiveSearch({ query: '  ' }), false)
  assert.equal(hasActiveSearch({ query: 'pv' }), true)
  assert.equal(hasActiveSearch({ tag: 4 }), true)
  assert.equal(hasActiveSearch({ coffre: 'null' }), true)
})

const DOCS = [
  { id: 1, nom: 'A', tags: [{ id: 10 }, { id: 11 }], custom_data: { confidentialite: 'interne' } },
  { id: 2, nom: 'B', tags: [{ id: 10 }], custom_data: { confidentialite: 'public' } },
  { id: 3, nom: 'C', tags: [], custom_data: {} },
]

test('filterDocuments exige TOUS les tags demandés', () => {
  assert.deepEqual(filterDocuments(DOCS, { tagIds: [10] }).map((d) => d.id), [1, 2])
  assert.deepEqual(filterDocuments(DOCS, { tagIds: [10, 11] }).map((d) => d.id), [1])
  assert.deepEqual(filterDocuments(DOCS, { tagIds: [99] }).map((d) => d.id), [])
})

test('filterDocuments matche les métadonnées custom_data (insensible à la casse)', () => {
  assert.deepEqual(
    filterDocuments(DOCS, { meta: { confidentialite: 'INTERNE' } }).map((d) => d.id),
    [1],
  )
  // Combine tag + métadonnée.
  assert.deepEqual(
    filterDocuments(DOCS, { tagIds: [10], meta: { confidentialite: 'public' } }).map((d) => d.id),
    [2],
  )
})

test('filterDocuments sans critère renvoie tout ; entrée invalide → []', () => {
  assert.equal(filterDocuments(DOCS, {}).length, 3)
  assert.deepEqual(filterDocuments(null, { tagIds: [1] }), [])
})
