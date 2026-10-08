// ATOT24 — l'aperçu multi-propriétés de l'écran suit la CHAÎNE DU RAIL :
// option effective + scénario pour le « N × … », totaux canoniques par villa
// (+ « Hors groupe ») et total général au palier pour les villas différentes.
// Source réelle : `optionTotalsTTC` / `totauxCanoniquesTtc` (noyau miroir de
// `selectors._canonical_totaux` / `multi_villa_totaux`), aucun mock.
//
// Run : node --test src/features/ventes/solar.atot.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { multiPropertyPreviewTTC, optionTotalsTTC, totauxCanoniquesTtc } from './solar.js'
import { PAS_ARRONDI_DEVIS } from './remise.js'
import { SCENARIOS_VALIDES } from './quote/scenarios.js'

const LES_DEUX = SCENARIOS_VALIDES[0]

const L = (designation, quantite, ttc, extra = {}) => ({
  designation, quantite: String(quantite), prix_unit_ttc: String(ttc), taux_tva: '20', ...extra,
})

const KIT_DEUX_OPTIONS = [
  L('Panneau Canadien Solar 715W', 8, 1320, { taux_tva: '10' }),
  L('Onduleur réseau Huawei 5kW', 1, 10800),
  L('Onduleur hybride Deye 6kW', 1, 16800),
  L('Batterie lithium 5kWh', 1, 19200),
  L('Structures acier', 8, 450),
]

test('apercu xN suit l option effective (Avec batterie × 3 = rail × 3)', () => {
  const rail = optionTotalsTTC(KIT_DEUX_OPTIONS, 0, { scenario: 'Avec batterie' })
  const r = multiPropertyPreviewTTC(KIT_DEUX_OPTIONS, {
    nombreProprietes: '3', discountPct: '0', scenario: 'Avec batterie', option: 'avec',
  })
  assert.equal(r.option, 'avec')
  assert.equal(r.totalUnitaire, rail.totalAvec)
  assert.notEqual(r.totalUnitaire, rail.totalSans, 'jamais l’option « sans » inconditionnelle')
  assert.equal(r.totalMulti, Math.round(rail.totalAvec * 100) * 3 / 100)
  // Sans option transmise, le scénario « Avec batterie » suffit.
  const s = multiPropertyPreviewTTC(KIT_DEUX_OPTIONS, { nombreProprietes: '3', scenario: 'Avec batterie' })
  assert.equal(s.totalUnitaire, rail.totalAvec)
})

test('apercu xN porte le scenario : « Les deux » + Smart Meter orphelin = rail', () => {
  // Smart Meter Huawei orphelin : aucun onduleur Huawei dans le kit.
  const lignes = [...KIT_DEUX_OPTIONS.map((l) => (l.designation.startsWith('Onduleur réseau')
    ? { ...l, designation: 'Onduleur réseau Deye 5kW' } : l)), L('Smart Meter Huawei DTSU666', 1, 2500)]
  const rail = optionTotalsTTC(lignes, 0, { scenario: LES_DEUX })
  const r = multiPropertyPreviewTTC(lignes, {
    nombreProprietes: '2', discountPct: '0', scenario: LES_DEUX, option: 'sans',
  })
  assert.equal(r.totalUnitaire, rail.totalSans)
  // Le scénario change bien la population (sinon ce test serait vacueux).
  const sansScenario = optionTotalsTTC(lignes, 0)
  assert.notEqual(sansScenario.totalSans, rail.totalSans)
  const avec = multiPropertyPreviewTTC(lignes, { nombreProprietes: '2', scenario: LES_DEUX, option: 'avec' })
  assert.equal(avec.totalUnitaire, rail.totalAvec)
})

const VILLAS = [
  L('Smart Meter', 1, 1200, { groupeIndex: 0, groupeLabel: 'Équipement commun' }),
  L('Panneau Canadien Solar 715W', 8, 1320, { taux_tva: '10', groupeIndex: 1, groupeLabel: 'Villa A' }),
  L('Onduleur réseau 5kW', 1, 10800, { groupeIndex: 1, groupeLabel: 'Villa A' }),
  L('Batterie optionnelle', 1, 19200, { groupeIndex: 1, groupeLabel: 'Villa A', optionnelle: true }),
  L('Panneau Canadien Solar 715W', 6, 1320, { taux_tva: '10', groupeIndex: 2, groupeLabel: 'Villa B' }),
  L('Onduleur réseau 3kW', 1, 7200, { groupeIndex: 2, groupeLabel: 'Villa B' }),
  L('Transport', 1, 900),
]

test('villas = totaux canoniques par groupe (remise comprise, option exclue)', () => {
  const r = multiPropertyPreviewTTC(VILLAS, { discountPct: '10' })
  assert.equal(r.mode, 'villas')
  const villaA = r.groupes.find((g) => g.label === 'Villa A')
  assert.equal(villaA.totalTtc, totauxCanoniquesTtc(VILLAS.slice(1, 3), 10, 0))
  assert.equal(villaA.totalTtc, totauxCanoniquesTtc(VILLAS.slice(1, 4), 10, 0), 'la ligne optionnelle ne compte pas')
  const villaB = r.groupes.find((g) => g.label === 'Villa B')
  assert.equal(villaB.totalTtc, totauxCanoniquesTtc(VILLAS.slice(4, 6), 10, 0))
})

test('hors groupe compte au total general (= multi_villa_totaux, palier compris)', () => {
  const r = multiPropertyPreviewTTC(VILLAS, { discountPct: '10' })
  const hors = r.groupes.find((g) => g.label === 'Hors groupe')
  assert.ok(hors, 'groupe « Hors groupe » présent')
  assert.equal(hors.index, null)
  assert.equal(hors.totalTtc, totauxCanoniquesTtc([VILLAS[6]], 10, 0))
  assert.equal(r.grandTotalTtc, totauxCanoniquesTtc(VILLAS, 10, PAS_ARRONDI_DEVIS))
  // Le total général est celui du rail (même chaîne, même palier).
  assert.equal(r.grandTotalTtc, optionTotalsTTC(VILLAS, 10).totalSans)
})
