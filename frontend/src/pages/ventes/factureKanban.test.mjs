// Run: node --test src/pages/ventes/factureKanban.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  KANBAN_COLUMNS, columnForFacture, groupByColumn, columnTotal, kanbanSummary,
  isOverdue, isPartiallyPaid,
} from './factureKanban.js'

const TODAY = '2026-07-05'

test('KANBAN_COLUMNS déclare les 5 colonnes attendues (annulée exclue du pipeline)', () => {
  assert.deepEqual(KANBAN_COLUMNS.map((c) => c.key),
    ['brouillon', 'emise', 'en_retard', 'partielle', 'payee'])
})

test('columnForFacture : brouillon', () => {
  assert.equal(columnForFacture({ statut: 'brouillon' }, TODAY), 'brouillon')
})

test('columnForFacture : émise en retard tombe dans en_retard, jamais emise', () => {
  const f = { statut: 'emise', date_echeance: '2026-01-01' }
  assert.equal(columnForFacture(f, TODAY), 'en_retard')
})

test('columnForFacture : émise non échue tombe dans emise', () => {
  const f = { statut: 'emise', date_echeance: '2026-12-31' }
  assert.equal(columnForFacture(f, TODAY), 'emise')
})

test('columnForFacture : is_overdue backend prime même sans date_echeance dépassée', () => {
  const f = { statut: 'emise', is_overdue: true, date_echeance: '2099-01-01' }
  assert.equal(columnForFacture(f, TODAY), 'en_retard')
})

test('columnForFacture : partiellement payée (paiement > 0, dû > 0, pas annulée)', () => {
  const f = { statut: 'payee_partielle_ou_autre', montant_paye: 100, montant_du: 50 }
  assert.equal(columnForFacture(f, TODAY), 'partielle')
})

test('columnForFacture : payée intégralement (statut payee, pas de dû)', () => {
  const f = { statut: 'payee', montant_paye: 100, montant_du: 0 }
  assert.equal(columnForFacture(f, TODAY), 'payee')
})

test('columnForFacture : annulée n’a aucune colonne (omise du pipeline)', () => {
  assert.equal(columnForFacture({ statut: 'annulee' }, TODAY), null)
})

test('columnForFacture : tolère une entrée vide/undefined', () => {
  assert.equal(columnForFacture(undefined, TODAY), null)
  assert.equal(columnForFacture(null, TODAY), null)
})

test('isOverdue / isPartiallyPaid : cohérents avec la dérivation FactureList.jsx', () => {
  assert.equal(isOverdue({ statut: 'emise', date_echeance: '2020-01-01' }, TODAY), true)
  assert.equal(isOverdue({ statut: 'brouillon', date_echeance: '2020-01-01' }, TODAY), false)
  assert.equal(isPartiallyPaid({ montant_paye: 10, montant_du: 5, statut: 'emise' }), true)
  assert.equal(isPartiallyPaid({ montant_paye: 10, montant_du: 5, statut: 'annulee' }), false)
})

test('groupByColumn : toutes les colonnes présentes même vides, une facture par colonne unique', () => {
  const factures = [
    { id: 1, statut: 'brouillon' },
    { id: 2, statut: 'emise', date_echeance: '2020-01-01' }, // en_retard
    { id: 3, statut: 'annulee' }, // omise
  ]
  const groups = groupByColumn(factures, TODAY)
  assert.deepEqual(Object.keys(groups).sort(), KANBAN_COLUMNS.map((c) => c.key).sort())
  assert.equal(groups.brouillon.length, 1)
  assert.equal(groups.en_retard.length, 1)
  assert.equal(groups.emise.length, 0)
  // Facture annulée n'apparaît dans AUCUNE colonne.
  const allIds = Object.values(groups).flat().map((f) => f.id)
  assert.ok(!allIds.includes(3))
})

test('columnTotal : somme total_ttc de la colonne, tolère les valeurs manquantes', () => {
  assert.equal(columnTotal([{ total_ttc: 100 }, { total_ttc: 50 }, { total_ttc: null }]), 150)
  assert.equal(columnTotal([]), 0)
  assert.equal(columnTotal(undefined), 0)
})

test('kanbanSummary : compte + total par colonne, cohérent avec groupByColumn', () => {
  const factures = [
    { id: 1, statut: 'brouillon', total_ttc: 1000 },
    { id: 2, statut: 'payee', montant_paye: 500, montant_du: 0, total_ttc: 500 },
  ]
  const summary = kanbanSummary(factures, TODAY)
  const brouillon = summary.find((c) => c.key === 'brouillon')
  assert.equal(brouillon.count, 1)
  assert.equal(brouillon.total, 1000)
  const payee = summary.find((c) => c.key === 'payee')
  assert.equal(payee.count, 1)
  assert.equal(payee.total, 500)
})

// ── AFAC72 — mêmes prédicats que les onglets de la liste ────────────────────
test('partielle avant émise : une émise à solde partiel va en « Partiellement payée »', () => {
  const f = { statut: 'emise', montant_paye: 100, montant_du: 200, date_echeance: '2099-01-01' }
  assert.equal(columnForFacture(f, TODAY), 'partielle')
})

test('en_retard dû 0 visible : une facture au statut en_retard n\'est plus omise', () => {
  const f = { statut: 'en_retard', montant_paye: 0, montant_du: 0 }
  assert.equal(columnForFacture(f, TODAY), 'en_retard')
})

test('parité colonnes/onglets : chaque colonne compte autant que l\'onglet homonyme', async () => {
  const { isOverdue: ovl, isPartiallyPaid: part } = await import('./factureList/factureHelpers.js')
  const corpus = [
    { id: 1, statut: 'brouillon' },
    { id: 2, statut: 'emise', date_echeance: '2099-01-01', montant_paye: 0, montant_du: 300 },
    { id: 3, statut: 'emise', date_echeance: '2099-01-01', montant_paye: 100, montant_du: 200 },
    { id: 4, statut: 'en_retard', montant_du: 0 },
    { id: 5, statut: 'emise', date_echeance: '2020-01-01', montant_paye: 0, montant_du: 300 },
    { id: 6, statut: 'payee', montant_paye: 300, montant_du: 0 },
    { id: 7, statut: 'annulee' },
  ]
  const g = groupByColumn(corpus, TODAY)
  assert.equal(g.en_retard.length, corpus.filter((f) => ovl(f, TODAY)).length)
  assert.equal(g.partielle.length, corpus.filter(part).length)
  assert.equal(g.emise.length, corpus.filter((f) => f.statut === 'emise' && !ovl(f, TODAY) && !part(f)).length)
  assert.equal(g.payee.length, corpus.filter((f) => f.statut === 'payee').length)
})
