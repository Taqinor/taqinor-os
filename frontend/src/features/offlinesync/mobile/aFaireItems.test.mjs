// NTMOB19 — agrégation « À faire aujourd'hui » (logique pure, sans DOM).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { aFaireAujourdhui, construireItems, MAX_ITEMS } from './aFaireItems.js'

const TODAY = '2026-08-13'

test('NTMOB19: agrège les quatre sources en items cliquables', () => {
  const items = construireItems({
    relances: [{ id: 4, prenom: 'Amine', nom: 'B.', date_relance: TODAY }],
    approbations: [{ id: 7, source: 'ged', libelle: 'Document X' }],
    interventions: [{ id: 9, titre: 'Pose toiture', date_prevue: TODAY }],
    factures: [{ id: 2, label: 'FA-1', date: '2026-08-01', overdue: true }],
  })
  assert.equal(items.length, 4)
  assert.deepEqual(items.map((i) => i.to), [
    '/crm/leads/4', '/approbations', '/ma-journee', '/ventes/factures/2',
  ])
})

test("NTMOB19: ignore une facture non échue (pas une tâche du jour)", () => {
  const items = construireItems({
    factures: [{ id: 3, label: 'FA-2', date: '2026-09-30', overdue: false }],
  })
  assert.equal(items.length, 0)
})

test('NTMOB19: met le retard en tête, du plus ancien au plus récent', () => {
  const items = aFaireAujourdhui({
    factures: [
      { id: 1, label: 'FA-vieille', date: '2026-07-01', overdue: true },
      { id: 2, label: 'FA-recente', date: '2026-08-10', overdue: true },
    ],
    interventions: [{ id: 9, titre: 'Pose', date_prevue: TODAY }],
  }, TODAY)
  assert.deepEqual(items.map((i) => i.label), ['FA-vieille', 'FA-recente', 'Pose'])
})

test('NTMOB19: borne la liste aux 10 items les plus urgents', () => {
  const relances = Array.from({ length: 25 }, (_, i) => ({ id: i, nom: `L${i}` }))
  assert.equal(aFaireAujourdhui({ relances }, TODAY).length, MAX_ITEMS)
  assert.equal(MAX_ITEMS, 10)
})

test('NTMOB19: ne casse pas sans aucune source', () => {
  assert.deepEqual(aFaireAujourdhui({}, TODAY), [])
  assert.deepEqual(aFaireAujourdhui(undefined, TODAY), [])
})
