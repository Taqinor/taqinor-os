// AGNR23 — au modèle « factures », la série mensuelle de `computeROI` est
// répartie depuis l'annuel FINAL : Σ des 12 points = l'économie annuelle de la
// carte (le graphe « Économies mensuelles » ne contredit plus les cartes).
//
// Run : node --test src/features/ventes/solar.agnrSerieMensuelle.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { computeROI } from './solar.js'

const CAS = {
  kwp: 5, factures: Array(12).fill(800), dayUsagePct: 60, totalSans: 50000, totalAvec: 80000,
  batteryKwh: 5, consoAnnuelleKwh: 6000, utility: 'onee',
}

const somme = (serie, cle) => serie.reduce((s, m) => s + m[cle], 0)

test('AGNR23 — modèle « factures » : Σ eco_sans mensuelles = économie annuelle sans', () => {
  const r = computeROI(CAS)
  assert.equal(r.savings_model, 'factures')
  assert.ok(Math.abs(somme(r.monthly_detail, 'eco_sans') - r.eco_annuelle_sans) < 0.01,
    `${somme(r.monthly_detail, 'eco_sans')} ≠ ${r.eco_annuelle_sans}`)
})

test('AGNR23 — modèle « factures » : Σ eco_avec mensuelles = économie annuelle avec', () => {
  const r = computeROI(CAS)
  assert.ok(Math.abs(somme(r.monthly_detail, 'eco_avec') - r.eco_annuelle_avec) < 0.01,
    `${somme(r.monthly_detail, 'eco_avec')} ≠ ${r.eco_annuelle_avec}`)
})

test('AGNR23 — la répartition garde la forme saisonnière (été > hiver)', () => {
  const r = computeROI(CAS)
  assert.ok(r.monthly_detail[6].eco_sans > r.monthly_detail[0].eco_sans)
})

test('AGNR23 — modèle « estimation » inchangé : Σ = annuel (déjà vrai)', () => {
  const r = computeROI({ ...CAS, consoAnnuelleKwh: null, utility: null })
  assert.equal(r.savings_model, 'estimation')
  assert.ok(Math.abs(somme(r.monthly_detail, 'eco_sans') - r.eco_annuelle_sans) < 0.01)
})
