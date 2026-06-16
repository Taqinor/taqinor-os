import test from 'node:test'
import assert from 'node:assert/strict'

import {
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  STATUS_COLORS,
  statusOrder,
  filterInstallations,
  sortInstallations,
  EMPTY_FILTERS,
} from './statuses.js'

test('les 7 statuts chantier canoniques, dans l\'ordre d\'entonnoir', () => {
  assert.deepEqual(INSTALLATION_STATUSES, [
    'signe', 'materiel_commande', 'planifie', 'en_cours',
    'installe', 'receptionne', 'cloture',
  ])
  for (const s of INSTALLATION_STATUSES) {
    assert.ok(STATUS_LABELS[s], `libellé manquant pour ${s}`)
    assert.ok(STATUS_COLORS[s], `couleur manquante pour ${s}`)
  }
})

test('statusOrder respecte l\'entonnoir, pas l\'alphabet', () => {
  assert.ok(statusOrder('signe') < statusOrder('planifie'))
  assert.ok(statusOrder('receptionne') < statusOrder('cloture'))
  // "installe" (i) doit venir AVANT "receptionne" (r) dans l'entonnoir.
  assert.ok(statusOrder('installe') < statusOrder('receptionne'))
  // Un statut hérité tombe dans sa colonne canonique : mise_en_service →
  // receptionne (donc au même rang que receptionne).
  assert.equal(statusOrder('mise_en_service'), statusOrder('receptionne'))
  assert.equal(statusOrder('inconnu'), INSTALLATION_STATUSES.length)
})

test('sortInstallations trie par statut dans l\'ordre funnel', () => {
  const rows = [
    { id: 1, statut: 'cloture' },
    { id: 2, statut: 'signe' },
    { id: 3, statut: 'installe' },
  ]
  const sorted = sortInstallations(rows, 'statut', 'asc')
  assert.deepEqual(sorted.map((r) => r.id), [2, 3, 1])
})

test('filterInstallations : recherche + drapeau annulé', () => {
  const rows = [
    { id: 1, reference: 'CHT-1', client_nom: 'Alpha', statut: 'pose', annule: false },
    { id: 2, reference: 'CHT-2', client_nom: 'Beta', statut: 'pose', annule: true },
  ]
  assert.equal(filterInstallations(rows, { ...EMPTY_FILTERS, q: 'alpha' }).length, 1)
  assert.equal(filterInstallations(rows, { ...EMPTY_FILTERS, annule: 'sans' }).length, 1)
  assert.equal(filterInstallations(rows, { ...EMPTY_FILTERS, annule: 'seuls' }).length, 1)
  assert.equal(filterInstallations(rows, EMPTY_FILTERS).length, 2)
})
