// Règle de dimensionnement FONDATEUR du 18/08, verrouillée ici :
//   1. les installations se vendent par paliers de 5 kWc, jamais entre deux ;
//   2. le besoin se lit sur la facture d'hiver — 5 kWc par tranche de 900 MAD ;
//   3. chaque palier est chiffré avec le catalogue RÉEL (il n'existe aucun
//      barème au kWc — le prix vient des lignes, pas d'un ratio).
// DOCTRINE D'HORIZON FIXE (fondateur 25/08, RECALÉE depuis la tolérance
// relative du même jour) — la taille retenue N'EST PLUS bornée au seul palier
// de payback le plus court : depuis ce palier, `optimalKwcByPayback` grimpe
// vers la plus grande taille atteignable par des pas ascendants dont chaque
// pas MARGINAL se rembourse en ≤ `HORIZON_MARGINAL_PV` (10 ans, un seuil
// FIXE — plus une tolérance relative au meilleur payback du dossier). Les
// tests « … HORIZON FIXE 25/08 » en bas de fichier verrouillent ce
// changement — les tests plus haut (héritage 18/08) restent corrects tels
// quels : leurs scénarios n'ont simplement aucun pas ascendant admissible,
// donc la taille retenue continue d'y coïncider avec le payback minimal (cas
// particulier, pas la règle générale).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  KWC_STEP, MAD_PAR_PALIER, estimerKwcDepuisFacture, arrondirAuPasKwc,
  optimalKwcByPayback, autoFillLines, optionTotalsTTC, computeROI,
  batteryKwhFromLines, HORIZON_MARGINAL_PV,
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

test('la taille retenue est un PALIER de 5 kWc (ici, aucun pas ascendant admissible → coïncide avec le meilleur payback)', () => {
  const besoinKwc = estimerKwcDepuisFacture(FACTURES[0]) // 2600 MAD → 10 kWc
  assert.equal(besoinKwc, 10)
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc,
  })
  assert.equal(res.kwcOptimal % KWC_STEP, 0, `taille hors palier : ${res.kwcOptimal}`)
  assert.ok(res.kwcOptimal >= KWC_STEP)
  assert.ok(res.nbPanneaux > 0)

  // Seulement 2 paliers chiffrables (5 et 10, plafonnés par le besoin) : ici
  // le meilleur payback EST le sommet du balayage, donc il n'y a par
  // construction aucun pas ascendant à essayer — la taille retenue coïncide
  // avec le payback minimal. Ce n'est PAS la règle générale (voir les tests
  // « … TOLÉRANCE 25/08 » plus bas, où un pas ascendant admissible existe et
  // fait grimper la taille retenue AU-DELÀ du payback minimal).
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

// ══ DOCTRINE D'HORIZON FIXE (règle fondateur 25/08) — miroir du backend ════
// Avec le catalogue SEEDED et FACTURES de ce fichier, un besoin de 40 kWc
// produit un vrai payback en U (5→3,9 ans en descendant, puis remontée) : le
// meilleur payback est à 25 kWc. Sous horizon FIXE (`HORIZON_MARGINAL_PV` =
// 10 ans), TOUS les pas ascendants mesurés dans ce scénario passent le seuil
// (3,91, 8,19 et 2,85 ans sont chacun ≤ 10) : l'ascension grimpe jusqu'au
// sommet du balayage (40 kWc, plafonné par le besoin lui-même) — un résultat
// différent de la doctrine relative du même jour (qui s'arrêtait à 30 kWc,
// H = 3,9 × 1,20 = 4,68 < 8,19). C'est exactement le défaut que l'horizon
// fixe corrige : un dossier au meilleur payback court (3,9 ans) ne punit plus
// les pas suivants avec une tolérance étroite.
// Reproduction exacte des paliers mesurés (probe ad hoc, catalogue/facture
// RÉELS de ce fichier — jamais un chiffre inventé) :
//   kwc  payback  paybackMarginal (depuis le palier retenu précédent)
//    5    5,6
//   10    4,6
//   15    4,2
//   20    4,1
//   25    3,9      ← meilleur payback (ancienne règle 18/08 s'arrêtait ICI)
//   30    3,9      3,91  ≤ H(10) → ADMIS
//   35    4,5      8,19  ≤ H(10) → ADMIS (refusé sous l'ancien H relatif 4,68)
//   40    4,3      2,85  ≤ H(10) → ADMIS, nouvelle taille retenue (= plafond)
const besoinAscension = 40

// Rejoue le choix PUR PAYBACK de l'ancienne règle (18/08, avant toute
// doctrine d'ascension) : payback le plus court, égalité stricte → palier le
// plus petit. Les champs par palier (`payback`, `economieAnnuelle`,
// `totalTtc`) sont calculés IDENTIQUEMENT dans toutes les règles — seule la
// SÉLECTION finale change — donc recalculer ce choix sur `res.paliers`
// reproduit fidèlement ce que `optimalKwcByPayback` aurait renvoyé avant le
// 25/08.
function ancienChoixPurPayback(paliers) {
  const chiffrables = paliers.filter(p => p.chiffrable && Number.isFinite(p.payback) && p.payback > 0)
  return chiffrables.reduce((best, p) => (p.payback < best.payback - 1e-9 ? p : best), chiffrables[0])
}

test('DOCTRINE HORIZON FIXE 25/08 (a) — un pas ascendant admissible fait grimper la taille retenue AU-DELÀ du meilleur payback', () => {
  assert.equal(HORIZON_MARGINAL_PV, 10, 'l\'horizon fixe par défaut doit rester 10 ans')
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: besoinAscension,
  })
  const ancien = ancienChoixPurPayback(res.paliers)
  // Preuve « rouge sur l'ancienne règle » : l'ancien choix pur-payback est
  // 25 kWc, la nouvelle taille retenue (mesurée, jamais posée a priori) est
  // le sommet du balayage — elles DIVERGENT.
  assert.equal(ancien.kwc, 25, 'le palier au meilleur payback doit être 25 kWc pour ce scénario')
  assert.equal(res.kwcOptimal, 40, 'taille mesurée sous horizon fixe = 10 ans pour ce scénario')
  assert.notEqual(res.kwcOptimal, ancien.kwc,
    'la taille retenue doit dépasser le palier au meilleur payback — sinon la doctrine ne fait rien')
  assert.ok(res.kwcOptimal > ancien.kwc)

  // Chaque pas de l'ascension a bien été jugé admissible sous l'horizon FIXE
  // (H ne dépend plus de meilleur.payback).
  for (const kwc of [30, 35, 40]) {
    const palier = res.paliers.find(p => p.kwc === kwc)
    assert.ok(Number.isFinite(palier.paybackMarginal), `palier ${kwc} : paybackMarginal manquant`)
    assert.ok(palier.paybackMarginal <= HORIZON_MARGINAL_PV + 1e-9,
      `pas marginal ${palier.paybackMarginal} (palier ${kwc}) doit être ≤ H (${HORIZON_MARGINAL_PV})`)
    assert.equal(palier.admissibleMarginal, true)
  }

  // Garantie mathématique du commentaire de doctrine : ici meilleur_payback
  // (3,9) ≤ H (10), donc le payback GLOBAL du palier retenu ne dépasse
  // jamais H — cas (1) de la preuve.
  const retenu = res.paliers.find(p => p.kwc === res.kwcOptimal)
  assert.ok(retenu.payback <= HORIZON_MARGINAL_PV + 1e-9,
    `payback global du palier retenu (${retenu.payback}) doit rester ≤ H (${HORIZON_MARGINAL_PV})`)
})

test('DOCTRINE HORIZON FIXE 25/08 (b) — un pas marginal AU-DELÀ de l\'horizon est refusé, l\'ascension s\'arrête net (cas construit)', () => {
  // Dans CE catalogue/ces factures, aucun pas marginal naturel ne dépasse
  // l'horizon par défaut (10 ans — le plus grand mesuré est 8,19 ans, au pas
  // 30→35). On CONSTRUIT donc le cas de refus avec l'override réservé aux
  // tests, en choisissant un horizon plus étroit que ce pas mesuré (5 < 8,19)
  // — le pas 25→30 (3,91 ans), lui, reste admissible sous ce même horizon.
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: besoinAscension,
    horizonMarginal: 5,
  })
  const palier30 = res.paliers.find(p => p.kwc === 30)
  const palier35 = res.paliers.find(p => p.kwc === 35)
  assert.ok(Number.isFinite(palier30.paybackMarginal))
  assert.ok(palier30.paybackMarginal <= 5 + 1e-9,
    `pas marginal ${palier30.paybackMarginal} (25→30) doit rester ≤ horizon (5) pour ce test`)
  assert.equal(palier30.admissibleMarginal, true)
  assert.ok(Number.isFinite(palier35.paybackMarginal))
  assert.ok(palier35.paybackMarginal > 5,
    `pas marginal ${palier35.paybackMarginal} (30→35) doit dépasser l'horizon (5) pour ce test`)
  assert.equal(palier35.admissibleMarginal, false)
  // L'ascension s'arrête AU pas refusé — jamais un saut par-dessus vers 35/40,
  // même si un palier plus loin redevenait par hasard rentable (40 kWc l'est,
  // paybackMarginal mesuré à 2,85 ≤ 5 — mais il n'est jamais atteint).
  assert.equal(res.kwcOptimal, 30)
  assert.ok(res.kwcOptimal < 35)
})

test('DOCTRINE HORIZON FIXE 25/08 (c) — horizonMarginal = meilleur_payback reproduit EXACTEMENT l\'ancien choix relatif-zéro', () => {
  const resDefaut = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: besoinAscension,
  })
  const ancien = ancienChoixPurPayback(resDefaut.paliers)
  // Overrider l'horizon par le meilleur payback DU DOSSIER (dynamique, comme
  // l'ancienne tolérance relative à 0 % le faisait implicitement) : aucun pas
  // marginal ne peut alors passer sous ce seuil sans être au moins aussi bon
  // que le meilleur payback lui-même — même sélection que la règle 18/08.
  const resRelatifZero = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: besoinAscension,
    horizonMarginal: ancien.payback,
  })
  assert.equal(resRelatifZero.kwcOptimal, ancien.kwc)
  assert.equal(resRelatifZero.kwcOptimal, 25, 'horizon = meilleur payback → même palier que la règle 18/08')
  // Et l'horizon fixe par défaut (10 ans) diverge bien de ce cas relatif-zéro
  // sur ce même scénario — la doctrine ne dégénère pas silencieusement.
  assert.notEqual(resDefaut.kwcOptimal, resRelatifZero.kwcOptimal)
})

test('DOCTRINE HORIZON FIXE 25/08 (d) — garde meilleur-payback-hors-horizon : jamais pire que le choix pur payback', () => {
  // Horizon délibérément plus étroit que TOUS les pas marginaux naturels de
  // ce scénario (le plus petit mesuré est 2,85 ans) : aucune ascension n'est
  // possible, quel que soit le palier de départ. La fonction doit alors
  // retomber exactement sur le palier au meilleur payback — jamais un
  // résultat pire (ni un palier plus cher, ni une erreur).
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: besoinAscension,
    horizonMarginal: 1,
  })
  const ancien = ancienChoixPurPayback(res.paliers)
  assert.equal(ancien.kwc, 25)
  assert.equal(res.kwcOptimal, ancien.kwc,
    'sous un horizon trop étroit pour toute ascension, la taille retenue doit rester le meilleur payback pur')
})
