// QAH-PROP — GARDE DE REGRESSION ECRAN du corpus figé #2
// (`solar_calculs_corpus.json` / `solar_calculs_expected.json`), partagé avec le
// jumeau Python `test_solar_differential_calculs.py`.
//
// Ce test RECALCULE avec la MÊME fonction que le générateur
// (`computeExpectedForEntry`) et exige l'égalité EXACTE avec le fichier commis :
// si `solar.js` change de comportement sans que quelqu'un régénère le contrat,
// CE test rougit ici, avant que le jumeau Python ne le prenne pour une fausse
// divergence inter-langage. Régénération : voir l'en-tête de
// `frontend/scripts/solar_calculs_corpus.mjs` (PACT10 — un humain, jamais pour
// faire passer un test).
//
// Run : `node --test src/features/ventes/solar.calculs.corpus.test.mjs`
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  computeExpectedForEntry, CORPUS_PATH, EXPECTED_PATH, SEED,
} from '../../../scripts/solar_calculs_corpus.mjs'

const CORPUS = JSON.parse(readFileSync(CORPUS_PATH, 'utf8'))
const EXPECTED = JSON.parse(readFileSync(EXPECTED_PATH, 'utf8'))

test('le corpus #2 et son fichier attendu sont alignés (mêmes ids, même graine)', () => {
  assert.equal(CORPUS.seed, SEED)
  assert.equal(EXPECTED.seed, SEED)
  assert.ok(CORPUS.entries.length >= 800, `corpus régressé : ${CORPUS.entries.length}`)
  assert.deepEqual(CORPUS.entries.map((e) => e.id), EXPECTED.entries.map((e) => e.id))
})

test('les neuf axes de calcul sont couverts', () => {
  const axes = new Set(CORPUS.entries.map((e) => e.axe))
  for (const a of ['tranche_bill', 'bill_to_kwh', 'facture_detail', 'conso_annuelle',
    'two_bills', 'roi', 'pompe_debit', 'pompe_select', 'pompe_variateur']) {
    assert.ok(axes.has(a), `axe manquant : ${a}`)
  }
})

test('les branches limites sont dans le corpus (aucun distributeur, autre, SRM, zéro, énorme)', () => {
  const b2k = CORPUS.entries.filter((e) => e.axe === 'bill_to_kwh')
  const utils = new Set(b2k.map((e) => String(e.utility ?? '').trim().toLowerCase()))
  for (const u of ['', 'onee', 'autre', 'srm-casablanca-settat']) assert.ok(utils.has(u), `distributeur absent : « ${u} »`)
  assert.ok(b2k.some((e) => e.bill <= 0))
  assert.ok(b2k.some((e) => e.bill >= 2e6), 'aucune facture hors plage')
  const ca = CORPUS.entries.filter((e) => e.axe === 'conso_annuelle')
  assert.ok(ca.some((e) => e.factures.every((f) => f === 0)), 'aucune série de factures nulles')
  assert.ok(ca.some((e) => e.factures.filter((f) => f > 0).length === 1), 'aucune série à UN SEUL mois')
  assert.ok(ca.some((e) => e.factures.length < 12), 'aucune série incomplète')
  const roi = CORPUS.entries.filter((e) => e.axe === 'roi')
  assert.ok(roi.some((e) => e.batteryKwh === 0) && roi.some((e) => e.batteryKwh > 0), 'une seule option couverte')
  assert.ok(roi.some((e) => e.conso === null), 'aucun ROI sans consommation')
})

const parId = new Map(EXPECTED.entries.map((e) => [e.id, e]))
for (const entry of CORPUS.entries) {
  test(`recalcul ${entry.id} (${entry.axe}) == fichier attendu commis`, () => {
    const recalc = { id: entry.id, axe: entry.axe, ...computeExpectedForEntry(entry) }
    // Aller-retour JSON : NaN/undefined disparaissent exactement comme à l'écriture.
    assert.deepEqual(JSON.parse(JSON.stringify(recalc)), parId.get(entry.id))
  })
}
