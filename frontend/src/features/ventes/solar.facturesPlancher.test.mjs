// ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — `controlerFacturesSaisies` refuse
// une facture réelle sous les lignes fixes du compteur et signale un écart avec
// la facture d'hiver du lead. Run : node --test src/features/ventes/solar.facturesPlancher.test.mjs
// Le blocage à l'enregistrement est EXÉCUTÉ (QJR239, aucune lecture de
// source) par `pages/ventes/DevisGeneratorEditionLead.test.jsx`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { estimerMois } from './solar.js'
import {
  controlerFacturesSaisies, chargesFixesTtc,
  controlerKwhDeclare, factureMad, ONEE_TRANCHES,
} from './calc/tarifs.js'

test('DEV-202609-0108 : estimerMois(1, 1600) a deux mois sous le plancher', () => {
  const ctl = controlerFacturesSaisies(estimerMois(1, 1600), { factureHiverLead: 3000 })
  assert.deepEqual(ctl.sousPlancher, [1, 12])
  assert.ok(Math.abs(ctl.plancher - 39.936) < 1e-9)
  assert.equal(ctl.plancher, chargesFixesTtc())
})

test('zéro (mois inconnu) et une facture plausible passent', () => {
  const ctl = controlerFacturesSaisies([0, ...Array(11).fill(900)], {})
  assert.deepEqual(ctl.sousPlancher, [])
  assert.equal(ctl.ecartLead, null)
})

test("écart avec la facture d'hiver du lead : signalé au-delà de 25 %", () => {
  assert.deepEqual(
    controlerFacturesSaisies(estimerMois(1600, 1600), { factureHiverLead: 3000 }).ecartLead,
    { serie: 1600, lead: 3000 })
  assert.equal(
    controlerFacturesSaisies(estimerMois(900, 900), { factureHiverLead: 900 }).ecartLead, null)
  assert.equal(
    controlerFacturesSaisies(estimerMois(1000, 1000), { factureHiverLead: 900 }).ecartLead, null)
  // Sans facture du lead : rien à comparer.
  assert.equal(controlerFacturesSaisies(estimerMois(1600, 1600), {}).ecartLead, null)
})

// ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — `controlerKwhDeclare`, jumeau de
// etude_horaire.coherence_kwh_declare_factures (décision fondateur 30/09/2026).
// Le blocage à l'enregistrement est EXÉCUTÉ par
// `pages/ventes/DevisGeneratorEditionLead.test.jsx`.
test('DEV-202609-0082 : 46 kWh/mois contre 15 000 MAD/mois est incohérent', () => {
  const ctl = controlerKwhDeclare(46, { factureHiver: 15000 })
  assert.equal(ctl.coherent, false)
  assert.ok(ctl.ratios[0] < 0.5)
})

test('650 kWh/mois contre 1 200 MAD/mois concorde (priorité Q14 gardée)', () => {
  assert.equal(controlerKwhDeclare(650, { factureHiver: 1200 }).coherent, true)
})

test('bande [0,5 ; 2] : juste dedans passe, juste dehors refuse', () => {
  const f = factureMad(650, ONEE_TRANCHES).totalMad
  assert.equal(controlerKwhDeclare(650, { factureHiver: f / 1.99 }).coherent, true)
  assert.equal(controlerKwhDeclare(650, { factureHiver: f / 0.51 }).coherent, true)
  assert.equal(controlerKwhDeclare(650, { factureHiver: f / 2.01 }).coherent, false)
  assert.equal(controlerKwhDeclare(650, { factureHiver: f / 0.49 }).coherent, false)
})

test("l'été n'est confronté que s'il est distinct ; une facture dans la bande suffit", () => {
  assert.equal(controlerKwhDeclare(650, {
    factureHiver: 10000, factureEte: 1200, eteDifferente: true }).coherent, true)
  assert.equal(controlerKwhDeclare(650, {
    factureHiver: 10000, factureEte: 1200, eteDifferente: false }).coherent, false)
})

test('rien à confronter ⇒ null (aucun blocage)', () => {
  assert.equal(controlerKwhDeclare(null, { factureHiver: 1200 }), null)
  assert.equal(controlerKwhDeclare('650', {}), null)
})
