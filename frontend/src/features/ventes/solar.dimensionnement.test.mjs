// Règle de dimensionnement FONDATEUR du 18/08, verrouillée ici :
//   1. les installations se vendent par paliers de 5 kWc, jamais entre deux ;
//   2. le besoin se lit sur la facture d'hiver — 5 kWc par tranche de 900 MAD ;
//   3. la taille retenue est celle dont le RETOUR SUR INVESTISSEMENT est le
//      plus court, chaque palier étant chiffré avec le catalogue RÉEL (il
//      n'existe aucun barème au kWc — le prix vient des lignes, pas d'un ratio).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  KWC_STEP, MAD_PAR_PALIER, estimerKwcDepuisFacture, arrondirAuPasKwc,
  optimalKwcByPayback, autoFillLines, optionTotalsTTC, computeROI,
  batteryKwhFromLines,
} from './solar.js'

const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc) => ({ id: ++_id, nom, prix_vente: ht(ttc) })
const SEEDED = [
  P('Onduleur réseau Huawei 5kW Monophasé', 14000),
  P('Onduleur réseau Huawei 10kW Monophasé', 18000),
  P('Onduleur réseau Huawei 12kW Monophasé', 20000),
  P('Onduleur réseau Huawei 15kW Triphasé', 23000),
  P('Onduleur réseau Huawei 20kW Triphasé', 28000),
  P('Onduleur réseau Huawei 25kW Triphasé', 35000),
  P('Onduleur hybride Deye 5kW Monophasé', 17000),
  P('Onduleur hybride Deye 10kW Monophasé', 28000),
  P('Onduleur hybride Deye 15kW Triphasé', 36000),
  P('Onduleur hybride Deye 20kW Triphasé', 48000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Batterie Dyness 5 kWh', 17000),
  P('Structures acier', 500),
  P('Structures aluminium', 850),
  P('Socles', 80),
  P('Smart Meter', 1800),
  P('Wifi Dongle', 1200),
  P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000),
  P('Installation', 4800),
  P('Transport', 1000),
  P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

const FACTURES = [2600, 2400, 2200, 2000, 1900, 2400, 3000, 2900, 2600, 2300, 2200, 2500]

test('le pas de vente est 5 kWc et la tranche 900 MAD — pas des nombres magiques', () => {
  assert.equal(KWC_STEP, 5)
  assert.equal(MAD_PAR_PALIER, 900)
})

test('facture d’hiver → besoin : 5 kWc par tranche PLEINE de 900 MAD', () => {
  assert.equal(estimerKwcDepuisFacture(900), 5)
  assert.equal(estimerKwcDepuisFacture(1799), 5)   // la tranche entamée ne compte pas
  assert.equal(estimerKwcDepuisFacture(1800), 10)
  assert.equal(estimerKwcDepuisFacture(2700), 15)
  assert.equal(estimerKwcDepuisFacture(899), 0)    // sous la première tranche
  assert.equal(estimerKwcDepuisFacture(0), 0)
  assert.equal(estimerKwcDepuisFacture(null), 0)
})

test('toute taille est ramenée au palier de 5 kWc le PLUS PROCHE, jamais à 0', () => {
  assert.equal(arrondirAuPasKwc(7), 5)
  assert.equal(arrondirAuPasKwc(7.6), 10)
  assert.equal(arrondirAuPasKwc(12.5), 15)  // .5 monte
  assert.equal(arrondirAuPasKwc(0.4), 5)    // jamais une installation nulle
  assert.equal(arrondirAuPasKwc(-3), 5)
})

test('la taille retenue est un PALIER de 5 kWc et minimise le payback', () => {
  const besoinKwc = estimerKwcDepuisFacture(FACTURES[0]) // 2600 MAD → 10 kWc
  assert.equal(besoinKwc, 10)
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc,
  })
  assert.equal(res.kwcOptimal % KWC_STEP, 0, `taille hors palier : ${res.kwcOptimal}`)
  assert.ok(res.kwcOptimal >= KWC_STEP)
  assert.ok(res.nbPanneaux > 0)

  // Le gagnant a RÉELLEMENT le payback le plus court des paliers chiffrés.
  const chiffrables = res.paliers.filter(p => Number.isFinite(p.payback) && p.payback > 0)
  assert.ok(chiffrables.length >= 2, 'au moins deux paliers doivent être chiffrables')
  const meilleur = Math.min(...chiffrables.map(p => p.payback))
  const retenu = chiffrables.find(p => p.kwc === res.kwcOptimal)
  assert.ok(retenu, 'le palier retenu doit figurer dans le détail')
  assert.equal(retenu.payback, meilleur)
})

test('le balayage ne dépasse JAMAIS le besoin lu sur la facture', () => {
  // Garde ANTI-SUR-VENTE : le modèle d'économie hérité ne sature pas à la
  // consommation réelle, donc un « payback minimal » sans plafond monterait
  // indéfiniment. On ne propose jamais plus gros que le besoin.
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: 10,
  })
  assert.deepEqual(res.paliers.map(p => p.kwc), [5, 10])
  assert.ok(res.kwcOptimal <= 10)
})

test('une contrainte de toit (maxKwc) resserre le balayage sans le casser', () => {
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: 20, maxKwc: 12,
  })
  assert.deepEqual(res.paliers.map(p => p.kwc), [5, 10])
  assert.ok(res.kwcOptimal <= 10)
})

test('chaque palier est chiffré par le CATALOGUE réel, pas par un prix au kWc', () => {
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: 10,
  })
  for (const palier of res.paliers) {
    const lignes = autoFillLines(SEEDED, { kwp: palier.kwc, panelW: 710, structureType: 'acier' })
    const { totalSans } = optionTotalsTTC(lignes, 0)
    assert.equal(palier.totalTtc, totalSans, `palier ${palier.kwc} kWc : prix hors catalogue`)
    assert.equal(palier.nbPanneaux, lignes.nbPanneaux)
  }
  // Le prix au kWc N'EST PAS constant : preuve que ce n'est pas un barème.
  const ratios = res.paliers.map(p => p.totalTtc / p.kwc)
  assert.ok(Math.max(...ratios) - Math.min(...ratios) > 1, 'prix au kWc constant → barème déguisé')
})

test('le payback de chaque palier est celui du cashflow 25 ans, pas un ratio maison', () => {
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: 10,
  })
  const palier = res.paliers.find(p => p.kwc === 10)
  const lignes = autoFillLines(SEEDED, { kwp: 10, panelW: 710, structureType: 'acier' })
  const { totalSans, totalAvec } = optionTotalsTTC(lignes, 0)
  const roi = computeROI({
    kwp: lignes.kwcReel, factures: FACTURES, dayUsagePct: 60,
    totalSans, totalAvec, batteryKwh: batteryKwhFromLines(lignes),
  })
  assert.equal(palier.payback, roi.payback_sans)
  assert.equal(palier.economieAnnuelle, roi.eco_annuelle_sans)
})

test('catalogue vide : repli sur le besoin arrondi au palier, jamais un chiffre inventé', () => {
  const res = optimalKwcByPayback({
    produits: [], factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: 12,
  })
  assert.equal(res.kwcOptimal, 10)
  assert.ok(res.nbPanneaux > 0)
})
