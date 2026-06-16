import test from 'node:test'
import assert from 'node:assert/strict'

import {
  echeanceLabel,
  echeanceColor,
  filterContrats,
  EMPTY_CONTRAT_FILTERS,
} from './contrat.js'

test('echeanceLabel reflète due / à venir / planifiée', () => {
  assert.equal(echeanceLabel({ est_due: true, jours_avant_visite: 0 }), 'Visite due')
  assert.match(
    echeanceLabel({ est_due: true, jours_avant_visite: -5 }),
    /en retard de 5 j/)
  assert.equal(
    echeanceLabel({ est_a_venir: true, jours_avant_visite: 12 }),
    'À venir dans 12 j')
  assert.equal(echeanceLabel({}), 'Planifiée')
})

test('echeanceColor : due rouge, bientôt orange, sinon vert', () => {
  assert.equal(echeanceColor({ est_due: true }), '#dc2626')
  assert.equal(echeanceColor({ est_a_venir: true }), '#d97706')
  assert.equal(echeanceColor({}), '#16a34a')
})

test('filterContrats : recherche texte et statut actif', () => {
  const rows = [
    { id: 1, libelle: 'Annuel onduleur', client_nom: 'Alpha', installation_reference: 'CHT-1', actif: true },
    { id: 2, libelle: 'Semestriel', client_nom: 'Beta', installation_reference: 'CHT-2', actif: false },
    { id: 3, libelle: 'Pompage', client_nom: 'Gamma', installation_reference: 'CHT-3', actif: true },
  ]
  assert.deepEqual(
    filterContrats(rows, { ...EMPTY_CONTRAT_FILTERS, q: 'beta' }).map((r) => r.id), [2])
  assert.deepEqual(
    filterContrats(rows, { ...EMPTY_CONTRAT_FILTERS, actif: 'true' }).map((r) => r.id), [1, 3])
  assert.deepEqual(
    filterContrats(rows, { ...EMPTY_CONTRAT_FILTERS, actif: 'false' }).map((r) => r.id), [2])
  assert.equal(filterContrats(rows, EMPTY_CONTRAT_FILTERS).length, 3)
})
