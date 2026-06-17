// F4 — tests des helpers de statut d'intervention.
// Run with: node --test src/features/installations/interventionStatuses.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  INTERVENTION_STATUSES, interventionColumn,
  interventionStatusLabel, interventionTypeLabel,
} from './interventionStatuses.js'

test('six colonnes dans l\'ordre du workflow', () => {
  assert.deepEqual(INTERVENTION_STATUSES, [
    'a_preparer', 'prete', 'en_route', 'sur_site', 'terminee', 'validee'])
})

test('interventionColumn : valeur inconnue → première colonne', () => {
  assert.equal(interventionColumn('sur_site'), 'sur_site')
  assert.equal(interventionColumn('zzz'), 'a_preparer')
  assert.equal(interventionColumn(undefined), 'a_preparer')
})

test('libellés FR + repli', () => {
  assert.equal(interventionStatusLabel('a_preparer'), 'À préparer')
  assert.equal(interventionStatusLabel('terminee'), 'Terminée')
  assert.equal(interventionStatusLabel('zzz'), 'zzz')
  assert.equal(interventionTypeLabel('sav'), 'SAV')
  assert.equal(interventionTypeLabel('visite'), 'Visite')
})
