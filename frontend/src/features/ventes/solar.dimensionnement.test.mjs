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
  consoAnnuelleDepuisFactures, kwhFromBill,
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
// ── GARDE DE SATURATION (finding 25/08, RECALAGE de ce bloc) ───────────────
// Ce scénario épinglait « l'ascension grimpe jusqu'au sommet du balayage
// (40 kWc, plafonné par le besoin) ». La mesure a montré que ce n'était pas
// un CHOIX mais une FATALITÉ : sans consommation réelle, `computeROI` ne
// plafonne pas l'économie (elle est un pourcentage de la seule PRODUCTION,
// donc LINÉAIRE en kWc), le payback marginal reste quasi constant sous
// l'horizon et l'ascension finit TOUJOURS au plafond, quel qu'il soit —
// mesuré sur CE catalogue et CES factures : besoin 40 → 40 kWc, 60 → 60,
// 100 → 100 kWc (522 341 MAD), 200 → 200 kWc. Le « dimensionnement » ne
// dépendait plus que du plafond.
//
// Les deux appelants réels (DevisGenerator, autoQuote) fournissent désormais
// la consommation réelle du client, dérivée de ses factures par le barème
// (`consoAnnuelleDepuisFactures`). Ce fichier fait pareil : c'est le SEUL
// régime dans lequel la règle marginale a un sens, et la garde structurelle
// de `optimalKwcByPayback` refuse maintenant de l'appliquer autrement.
//
// Paliers RE-MESURÉS avec la consommation réelle (17 870 kWh/an dérivée des
// 12 factures ci-dessus au barème ONEE — jamais un chiffre posé) :
//   kwc  total TTC  éco/an   payback  paybackMarginal
//    5     41 730    6 947    6,1
//   10     64 394   13 027    5,0
//   15     85 058   20 433    4,2     ← meilleur payback (choix PUR)
//   20    111 721   26 435    4,3     4,44  ≤ H(10) → ADMIS
//   25    130 385   29 000    4,5     7,28  ≤ H(10) → ADMIS ← taille retenue
//   30    156 049   29 000    5,4     —     l'économie SATURE (Δéco = 0)
//   35    209 713   29 000    7,3           → pas marginal jamais remboursé
//   40    228 376   29 000    8,0           → REFUSÉ, l'ascension s'arrête
// L'économie plafonne à 29 000 MAD/an dès 25 kWc : au-delà, on vend des
// panneaux qui produisent ce que le client ne consomme pas. L'ascension
// s'arrête donc D'ELLE-MÊME à 25 kWc — BIEN AVANT le plafond de 40.
const besoinAscension = 40
// Consommation réelle du client, dérivée de SES factures par le barème (QF1)
// — exactement ce que les deux appelants réels passent désormais.
const CONSO_ASCENSION = consoAnnuelleDepuisFactures(FACTURES, 'onee')
const UTILITY_ASCENSION = 'onee'
// Le socle commun des tests d'ascension ci-dessous.
const scenarioAscension = {
  produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
  panelW: 710, structureType: 'acier', besoinKwc: besoinAscension,
  consoAnnuelleKwh: CONSO_ASCENSION, utility: UTILITY_ASCENSION,
}

test('GARDE DE SATURATION — la consommation réelle du scénario est bien DÉRIVÉE des factures, jamais posée', () => {
  assert.equal(CONSO_ASCENSION, 17870)
  // Elle vaut exactement la somme des 12 factures inversées par le barème.
  const aLaMain = Math.round(FACTURES.reduce(
    (s, b) => s + kwhFromBill(b, UTILITY_ASCENSION).kwhMensuel, 0))
  assert.equal(CONSO_ASCENSION, aLaMain)
})

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
  const res = optimalKwcByPayback(scenarioAscension)
  const ancien = ancienChoixPurPayback(res.paliers)
  // La doctrine fait bien QUELQUE CHOSE : la taille retenue dépasse le palier
  // au meilleur payback (15 → 25 kWc, mesuré, jamais posé a priori).
  assert.equal(ancien.kwc, 15, 'le palier au meilleur payback doit être 15 kWc pour ce scénario')
  assert.equal(res.kwcOptimal, 25, 'taille mesurée sous horizon fixe = 10 ans, avec consommation réelle')
  assert.ok(res.kwcOptimal > ancien.kwc)
  assert.equal(res.ascensionDesactivee, null, 'l\'ascension doit bien avoir eu lieu ici')

  // Chaque pas de l'ascension a bien été jugé admissible sous l'horizon FIXE
  // (H ne dépend plus de meilleur.payback).
  for (const kwc of [20, 25]) {
    const palier = res.paliers.find(p => p.kwc === kwc)
    assert.ok(Number.isFinite(palier.paybackMarginal), `palier ${kwc} : paybackMarginal manquant`)
    assert.ok(palier.paybackMarginal <= HORIZON_MARGINAL_PV + 1e-9,
      `pas marginal ${palier.paybackMarginal} (palier ${kwc}) doit être ≤ H (${HORIZON_MARGINAL_PV})`)
    assert.equal(palier.admissibleMarginal, true)
  }

  // LE POINT DU FINDING — l'ascension S'ARRÊTE, et elle s'arrête AVANT le
  // plafond du balayage. Au-delà de 25 kWc l'économie SATURE (le client ne
  // consomme pas plus), donc le pas marginal n'achète plus rien et ne peut
  // jamais se rembourser : `paybackMarginal` est nul (Δéconomie = 0).
  assert.ok(res.kwcOptimal < besoinAscension,
    `la taille retenue (${res.kwcOptimal}) doit rester SOUS le plafond du balayage (${besoinAscension}) — sinon c'est le plafond qui décide, pas la règle`)
  const palier30 = res.paliers.find(p => p.kwc === 30)
  assert.equal(palier30.paybackMarginal, null,
    'au-delà de la saturation, le pas marginal n\'achète aucune économie')
  assert.equal(palier30.admissibleMarginal, false)
  // L'économie est bien PLAFONNÉE (identique de 25 à 40 kWc) : c'est la
  // saturation elle-même, la propriété sans laquelle la règle sur-vend.
  const eco = (k) => res.paliers.find(p => p.kwc === k).economieAnnuelle
  assert.equal(eco(30), eco(25))
  assert.equal(eco(40), eco(25))

  // Garantie mathématique du commentaire de doctrine : ici meilleur_payback
  // (4,2) ≤ H (10), donc le payback GLOBAL du palier retenu ne dépasse
  // jamais H — cas (1) de la preuve.
  const retenu = res.paliers.find(p => p.kwc === res.kwcOptimal)
  assert.ok(retenu.payback <= HORIZON_MARGINAL_PV + 1e-9,
    `payback global du palier retenu (${retenu.payback}) doit rester ≤ H (${HORIZON_MARGINAL_PV})`)
})

test('GARDE DE SATURATION (finding 25/08) — SANS consommation réelle, l\'ascension est DÉSACTIVÉE : retour au choix PUR payback', () => {
  // Le régime non saturant : l'économie est linéaire en kWc, donc AUCUN pas
  // marginal ne peut jamais être refusé — la règle marginale sur-vend
  // mécaniquement. On ne l'applique donc pas du tout.
  const res = optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: besoinAscension,
  })
  const ancien = ancienChoixPurPayback(res.paliers)
  assert.equal(res.ascensionDesactivee, 'sans_saturation')
  assert.equal(res.kwcOptimal, ancien.kwc,
    'sans saturation, la taille retenue doit être exactement le meilleur payback')
  assert.equal(res.kwcOptimal, 25)
})

test('GARDE DE SATURATION (finding 25/08) — sans conso, le PLAFOND ne décide plus : 40, 100 ou 200 kWc de besoin rendent la MÊME taille', () => {
  // C'est la mesure qui a exhumé le défaut : sans la garde, ces trois besoins
  // rendaient 40, 100 (522 341 MAD) et 200 kWc — le résultat n'était que le
  // plafond du balayage, jamais un dimensionnement.
  const tailles = [40, 100, 200].map(besoinKwc => optimalKwcByPayback({
    produits: SEEDED, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc,
  }).kwcOptimal)
  assert.deepEqual(tailles, [25, 25, 25])
})

test('GARDE DÉPART-HORS-HORIZON (miroir backend `depart_dans_horizon`) — un départ au-delà de l\'horizon ne grimpe pas', () => {
  // Miroir EXACT de apps/ventes/dimensionnement.py : quand le palier de
  // DÉPART dépasse déjà l'horizon, lui ajouter des dirhams ne peut
  // qu'aggraver son cas — on rend le choix pur payback, jamais pire.
  const res = optimalKwcByPayback({ ...scenarioAscension, horizonMarginal: 1 })
  const ancien = ancienChoixPurPayback(res.paliers)
  assert.ok(ancien.payback > 1,
    'le palier de départ doit bien dépasser l\'horizon pour que ce test ait un sens')
  assert.equal(res.ascensionDesactivee, 'depart_hors_horizon')
  assert.equal(res.kwcOptimal, ancien.kwc)
  assert.equal(res.kwcOptimal, 15)
})

test('DOCTRINE HORIZON FIXE 25/08 (b) — un pas marginal AU-DELÀ de l\'horizon est refusé, l\'ascension s\'arrête net (cas construit)', () => {
  // Dans CE catalogue/ces factures, aucun pas marginal naturel ne dépasse
  // l'horizon par défaut (10 ans — les deux pas admis mesurent 4,44 et 7,28
  // ans). On CONSTRUIT donc le cas de refus avec l'override réservé aux
  // tests, en choisissant un horizon plus étroit que le second pas mesuré
  // (5 < 7,28) — le pas 15→20 (4,44 ans), lui, reste admissible.
  const res = optimalKwcByPayback({ ...scenarioAscension, horizonMarginal: 5 })
  const palier20 = res.paliers.find(p => p.kwc === 20)
  const palier25 = res.paliers.find(p => p.kwc === 25)
  assert.ok(Number.isFinite(palier20.paybackMarginal))
  assert.ok(palier20.paybackMarginal <= 5 + 1e-9,
    `pas marginal ${palier20.paybackMarginal} (15→20) doit rester ≤ horizon (5) pour ce test`)
  assert.equal(palier20.admissibleMarginal, true)
  assert.ok(Number.isFinite(palier25.paybackMarginal))
  assert.ok(palier25.paybackMarginal > 5,
    `pas marginal ${palier25.paybackMarginal} (20→25) doit dépasser l'horizon (5) pour ce test`)
  assert.equal(palier25.admissibleMarginal, false)
  // L'ascension s'arrête AU pas refusé — jamais un saut par-dessus.
  assert.equal(res.kwcOptimal, 20)
  assert.ok(res.kwcOptimal < 25)
})

test('DOCTRINE HORIZON FIXE 25/08 (c) — horizonMarginal = meilleur_payback reproduit EXACTEMENT l\'ancien choix relatif-zéro', () => {
  const resDefaut = optimalKwcByPayback(scenarioAscension)
  const ancien = ancienChoixPurPayback(resDefaut.paliers)
  // Overrider l'horizon par le meilleur payback DU DOSSIER (dynamique, comme
  // l'ancienne tolérance relative à 0 % le faisait implicitement) : aucun pas
  // marginal ne peut alors passer sous ce seuil sans être au moins aussi bon
  // que le meilleur payback lui-même — même sélection que la règle 18/08.
  const resRelatifZero = optimalKwcByPayback({
    ...scenarioAscension, horizonMarginal: ancien.payback,
  })
  assert.equal(resRelatifZero.kwcOptimal, ancien.kwc)
  assert.equal(resRelatifZero.kwcOptimal, 15, 'horizon = meilleur payback → même palier que la règle 18/08')
  // Et l'horizon fixe par défaut (10 ans) diverge bien de ce cas relatif-zéro
  // sur ce même scénario — la doctrine ne dégénère pas silencieusement.
  assert.notEqual(resDefaut.kwcOptimal, resRelatifZero.kwcOptimal)
})

test('DOCTRINE HORIZON FIXE 25/08 (d) — garde meilleur-payback-hors-horizon : jamais pire que le choix pur payback', () => {
  // Horizon délibérément plus étroit que TOUS les pas marginaux naturels de
  // ce scénario (le plus petit mesuré est 4,44 ans) : aucune ascension n'est
  // possible, quel que soit le palier de départ. La fonction doit alors
  // retomber exactement sur le palier au meilleur payback — jamais un
  // résultat pire (ni un palier plus cher, ni une erreur). Depuis le finding
  // 25/08, c'est la garde DÉPART-HORS-HORIZON qui court-circuite l'ascension
  // avant même la boucle (le résultat, lui, est le même).
  const res = optimalKwcByPayback({ ...scenarioAscension, horizonMarginal: 1 })
  const ancien = ancienChoixPurPayback(res.paliers)
  assert.equal(ancien.kwc, 15)
  assert.equal(res.kwcOptimal, ancien.kwc,
    'sous un horizon trop étroit pour toute ascension, la taille retenue doit rester le meilleur payback pur')
})
