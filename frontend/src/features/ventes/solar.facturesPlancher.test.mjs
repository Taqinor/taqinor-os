// ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — `controlerFacturesSaisies` refuse
// une facture réelle sous les lignes fixes du compteur et signale un écart avec
// la facture d'hiver du lead. Run : node --test src/features/ventes/solar.facturesPlancher.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { controlerFacturesSaisies, estimerMois, chargesFixesTtc } from './solar.js'

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

test('le générateur bloque la série sous le plancher et fait confirmer un écart', () => {
  const HERE = dirname(fileURLToPath(import.meta.url))
  const SRC = readFileSync(join(HERE, '../../pages/ventes/DevisGenerator.jsx'), 'utf8')
  const debut = SRC.indexOf('const validate = () => {')
  const VALIDATE = SRC.slice(debut, SRC.indexOf('return Object.keys(e).length === 0', debut))
  assert.ok(debut > 0)
  assert.match(VALIDATE, /controlerFacturesSaisies\(monthly, \{/)
  assert.match(VALIDATE, /factureHiverLead: selectedLead\?\.facture_hiver/)
  assert.match(VALIDATE, /if \(ctl\.sousPlancher\.length\) \{\s*e\.factures =/)
  assert.match(VALIDATE, /facturesEcartConfirme\.current !== signature/)
  assert.match(SRC, /errors\.conso \|\| errors\.factures\}/)
})
