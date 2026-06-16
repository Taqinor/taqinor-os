import test from 'node:test'
import assert from 'node:assert/strict'

import {
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  STATUS_COLORS,
  statusOrder,
  filterInstallations,
  sortInstallations,
  groupInstallationsByStatus,
  EMPTY_FILTERS,
} from './statuses.js'

test('les 7 statuts chantier, dans l\'ordre d\'entonnoir', () => {
  assert.deepEqual(INSTALLATION_STATUSES, [
    'a_planifier', 'planifie', 'pose_en_cours', 'pose',
    'raccordement_onee', 'mise_en_service', 'cloture',
  ])
  for (const s of INSTALLATION_STATUSES) {
    assert.ok(STATUS_LABELS[s], `libellé manquant pour ${s}`)
    assert.ok(STATUS_COLORS[s], `couleur manquante pour ${s}`)
  }
})

test('statusOrder respecte l\'entonnoir, pas l\'alphabet', () => {
  // "à planifier" (a_planifier) vient AVANT "clôturé" (cloture) dans
  // l'entonnoir, alors que l'alphabet mettrait a_planifier avant cloture
  // aussi — on teste un cas où alpha ≠ funnel : pose_en_cours avant pose ?
  assert.ok(statusOrder('a_planifier') < statusOrder('planifie'))
  assert.ok(statusOrder('mise_en_service') < statusOrder('cloture'))
  // "raccordement_onee" (commence par r) doit venir AVANT "mise_en_service"
  // (commence par m) dans l'entonnoir — l'inverse de l'ordre alphabétique.
  assert.ok(statusOrder('raccordement_onee') < statusOrder('mise_en_service'))
  assert.equal(statusOrder('inconnu'), INSTALLATION_STATUSES.length)
})

test('sortInstallations trie par statut dans l\'ordre funnel', () => {
  const rows = [
    { id: 1, statut: 'cloture' },
    { id: 2, statut: 'a_planifier' },
    { id: 3, statut: 'pose' },
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

test('groupInstallationsByStatus : 7 colonnes ordonnées, drapeau annulé reste dans sa colonne', () => {
  const rows = [
    { id: 1, statut: 'pose', annule: false },
    { id: 2, statut: 'pose', annule: true },
    { id: 3, statut: 'a_planifier', annule: false },
  ]
  const cols = groupInstallationsByStatus(rows)
  // Toujours 7 colonnes, dans l'ordre d'entonnoir.
  assert.equal(cols.length, 7)
  assert.deepEqual(cols.map((c) => c.key), INSTALLATION_STATUSES)
  // Un chantier annulé reste dans sa colonne de statut (pas exclu).
  const pose = cols.find((c) => c.key === 'pose')
  assert.equal(pose.count, 2)
  assert.equal(cols.find((c) => c.key === 'a_planifier').count, 1)
  assert.equal(cols.find((c) => c.key === 'cloture').count, 0)
})
