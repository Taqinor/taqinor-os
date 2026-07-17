import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyFilterGroup, evaluateNode, isLeafComplete, operatorsForType, emptyGroup, emptyCondition,
} from './filterLogic.js'

const COLUMNS = [
  { id: 'statut', header: 'Statut', type: 'select' },
  { id: 'montant', header: 'Montant', type: 'number' },
  { id: 'nom', header: 'Nom', type: 'text' },
  { id: 'date_creation', header: 'Créé le', type: 'date' },
]

const ROWS = [
  { id: 1, statut: 'Envoyé', montant: 60000, nom: 'Alaoui Solaire', date_creation: '2026-07-10' },
  { id: 2, statut: 'Relancé', montant: 80000, nom: 'Bennani SARL', date_creation: '2026-06-01' },
  { id: 3, statut: 'Accepté', montant: 30000, nom: 'Chraibi', date_creation: '2026-07-15' },
  { id: 4, statut: 'Envoyé', montant: 10000, nom: 'Douiri', date_creation: '2026-05-01' },
]

test('groupe vide → aucune ligne exclue', () => {
  assert.deepEqual(applyFilterGroup(ROWS, emptyGroup(), COLUMNS), ROWS)
})

test('« (statut = Envoyé OU statut = Relancé) ET montant > 50000 » — scénario NTUX3 exact', () => {
  const group = {
    op: 'AND',
    conditions: [
      {
        op: 'OR',
        conditions: [
          { field: 'statut', operator: 'is', value: 'Envoyé' },
          { field: 'statut', operator: 'is', value: 'Relancé' },
        ],
      },
      { field: 'montant', operator: 'gt', value: 50000 },
    ],
  }
  const result = applyFilterGroup(ROWS, group, COLUMNS)
  assert.deepEqual(result.map((r) => r.id), [1, 2])
})

test('opérateur texte « contient » insensible à la casse', () => {
  const group = { op: 'AND', conditions: [{ field: 'nom', operator: 'contains', value: 'sarl' }] }
  assert.deepEqual(applyFilterGroup(ROWS, group, COLUMNS).map((r) => r.id), [2])
})

test('opérateur nombre « between »', () => {
  const group = { op: 'AND', conditions: [{ field: 'montant', operator: 'between', value: [20000, 65000] }] }
  assert.deepEqual(applyFilterGroup(ROWS, group, COLUMNS).map((r) => r.id).sort(), [1, 3])
})

test('opérateur date relative « ce mois » — réévalué au moment de l\'appel (pas de date figée)', () => {
  const today = new Date()
  const inMonthRow = { id: 'in', date_creation: today.toISOString().slice(0, 10) }
  const lastYearRow = { id: 'out', date_creation: '2019-01-01' }
  const group = { op: 'AND', conditions: [{ field: 'date_creation', operator: 'relative', value: 'this_month' }] }
  assert.equal(evaluateNode(inMonthRow, group, COLUMNS), true)
  assert.equal(evaluateNode(lastYearRow, group, COLUMNS), false)
})

test('isLeafComplete : opérateur sans valeur (vide/non-vide) toujours complet', () => {
  assert.equal(isLeafComplete({ field: 'nom', operator: 'empty' }), true)
  assert.equal(isLeafComplete({ field: 'nom', operator: 'not_empty' }), true)
})

test('isLeafComplete : condition incomplète sans valeur pour un opérateur qui en exige une', () => {
  assert.equal(isLeafComplete({ field: 'nom', operator: 'contains', value: '' }), false)
  assert.equal(isLeafComplete({ field: 'nom', operator: 'contains', value: 'x' }), true)
})

test('isLeafComplete : between complet dès qu\'une borne est saisie', () => {
  assert.equal(isLeafComplete({ field: 'montant', operator: 'between', value: ['', ''] }), false)
  assert.equal(isLeafComplete({ field: 'montant', operator: 'between', value: [10, ''] }), true)
})

test('operatorsForType : type inconnu replie sur texte', () => {
  assert.deepEqual(operatorsForType('bogus'), operatorsForType('text'))
})

test('emptyCondition : opérateur par défaut = premier opérateur du type', () => {
  const c = emptyCondition('montant', 'number')
  assert.equal(c.operator, operatorsForType('number')[0].id)
})
