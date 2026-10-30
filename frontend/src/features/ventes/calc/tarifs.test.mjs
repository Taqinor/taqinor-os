// SPL210 — tests de calc/tarifs.js déplacés tel quel de solar.test.mjs (move
// only : aucune assertion modifiée).
//
// Run : node --test src/features/ventes/calc/tarifs.test.mjs
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  monthlyBillFromKwh, ONEE_TRANCHES, kwhFromBill, FALLBACK_KWH_PRICE, twoBillsSavings,
} from './tarifs.js'

test('QF4 — monthlyBillFromKwh : barème ONEE SÉLECTIF (300 kWh/mois)', () => {
  // BARÈME SÉLECTIF (grille officielle, cf. solar.js) : au-dessus de 150
  // kWh/mois, TOUTE la conso est facturée au tarif de SA tranche. 300 kWh/mois
  // tombe dans la bande 201-300 (bornes effectives 211-310, tolérance 10 kWh)
  // → tarif 1,187388 sur les 300 kWh (2026, TVA 20%).
  // Dérivation à la main : 300 × 1,187388 = 356,2164 MAD/mois.
  assert.ok(Math.abs(monthlyBillFromKwh(300, ONEE_TRANCHES) - 356.2164) < 1e-9)
  // La bande d'EN DESSOUS (progressive, ≤ 150) reste cumulative :
  // 100 × 0,916272 + 50 × 1,091388 = 91,6272 + 54,5694 = 146,1966 MAD/mois.
  assert.ok(Math.abs(monthlyBillFromKwh(150, ONEE_TRANCHES) - 146.1966) < 1e-9)
})

test('QF4 — kwhFromBill : inverse EXACT du barème sélectif', () => {
  // Facture atteignable : 700 × 1,622856 = 1 135,9992 MAD/mois → 700 kWh/mois.
  const r = kwhFromBill(1135.9992, 'onee')
  assert.equal(r.kwhMensuel, 700)
  assert.equal(r.approximatif, false)
  assert.equal(r.estimation, false)
  // 850 MAD/mois tombe dans un TROU du barème : la bande 301-500 plafonne à
  // 510 × 1,381704 = 704,66904 MAD et la bande supérieure démarre au-dessus de
  // 511 × 1,622856 = 829,279416 MAD… mais 850 MAD EST atteignable au-dessus de
  // 510 : 850 / 1,622856 = 523,7998… kWh (> 510, donc bien dans sa bande) →
  // arrondi 523,8.
  assert.equal(kwhFromBill(850, 'onee').kwhMensuel, 523.8)
  // Vrai trou : 235 MAD/mois. À 210 kWh la facture vaut 210 × 1,091388 =
  // 229,19148 ; au premier kWh au-dessus elle saute à 211 × 1,187388 =
  // 250,538868. Aucune conso ne produit 235 MAD → on résout à la BORNE BASSE
  // du saut (210 kWh), jamais une conso que le barème ne peut pas produire
  // (règle miroir en Python).
  assert.equal(kwhFromBill(235, 'onee').kwhMensuel, 210)
})

test('Q7 (fondateur 20/08) — kwhFromBill : Lydec/Redal = LA grille nationale, plus d\'approximation', () => {
  // Il n'existe pas de grille Lydec/Redal distincte : les distributeurs
  // appliquent la grille nationale unique — même inversion, même résultat
  // que l'ONEE, et le drapeau « approximatif » n'a plus d'objet.
  const onee = kwhFromBill(500, 'onee')
  for (const distributeur of ['lydec', 'redal']) {
    const r = kwhFromBill(500, distributeur)
    assert.deepEqual(r, onee, distributeur)
    assert.equal(r.approximatif, false, distributeur)
  }
})

test('QF4/CAD167 — kwhFromBill : SANS distributeur → repli FALLBACK_KWH_PRICE, étiqueté estimation', () => {
  // Même règle que test_cad167 test_SANS_distributeur_le_comportement_d_avant_est_conserve.
  for (const aucun of [undefined, null, '', '  ']) {
    const r = kwhFromBill(120, aucun)
    assert.equal(r.kwhMensuel, Math.round((120 / FALLBACK_KWH_PRICE) * 10) / 10)
    assert.equal(r.estimation, true)
  }
})

test('CAD167 — kwhFromBill : un distributeur NOMMÉ hors table (SRM, « autre ») lit la grille nationale', () => {
  // Même règle que pricing._resolve_tranches (test_cad167 test_autre_cesse_de_casser_la_courbe) :
  // AVANT, 'srm_casablanca' divisait la facture par 1,20 — DEV-202609-0113.
  const onee = kwhFromBill(22000, 'onee')
  for (const code of ['srm_casablanca', 'srm_rabat', 'autre', 'amendis', 'inconnu']) {
    const r = kwhFromBill(22000, code)
    assert.deepEqual(r, onee, code)
    assert.equal(r.estimation, false, code)
  }
  assert.notEqual(onee.kwhMensuel, Math.round((22000 / FALLBACK_KWH_PRICE) * 10) / 10)
})

test('QF4 — kwhFromBill : facture vide → 0 kWh, estimation', () => {
  const r = kwhFromBill(0, 'onee')
  assert.equal(r.kwhMensuel, 0)
  assert.equal(r.estimation, true)
})

// QJR168 — les factures ci-dessous portent le barème COMPLET (énergie + les
// deux lignes fixes + TPPAN), jumeau de bareme.facture_mad : 39,936 MAD TTC de
// location/entretien par mois (479,23/an) et une TPPAN empilée 0,10/0,15/0,20,
// bornes 100/200 kWh, plafonnée à 100 MAD/mois, nulle sous 50 kWh/mois.
test('QF2/QF5 — twoBillsSavings : économie réelle au barème (ratio 0.60, sans batterie)', () => {
  // Dérivation à la main (barème SÉLECTIF, 2026 — TVA 20 %) :
  //   conso    7 200/12 = 600 kWh/mois → > 510 → 600 × 1,622856 = 973,7136
  //                                            MAD/mois × 12 = 11 684,5632
  //     TPPAN  10 + 15 + 400 × 0,20 = 105 → PLAFOND 100 MAD/mois × 12 = 1 200
  //     fixes  479,23 → facture 11 684,5632 + 479,232 + 1 200 = 13 363,80 → 13 364
  //   autoconsommé 6 000 × 0,60 = 3 600 kWh (≤ conso) → résiduel 3 600 kWh/an
  //   résiduel 3 600/12 = 300 kWh/mois → bande 211-310 → 300 × 1,187388 =
  //                                            356,2164 × 12 = 4 274,5968
  //     TPPAN  10 + 15 + 100 × 0,20 = 45 MAD/mois × 12 = 540
  //     fixes  479,23 → facture 4 274,5968 + 479,232 + 540 = 5 293,83 → 5 294
  //   économie 13 364 − 5 294 = 8 070 MAD/an
  const r = twoBillsSavings(6000, 7200, 0.6, 'onee')
  assert.deepEqual(r, {
    factureSans: 13364, factureAvec: 5294, economie: 8070, autoconsoKwh: 3600,
  })
})

test('QF2/QF5 — twoBillsSavings : économie réelle au barème (ratio 0.85, avec batterie)', () => {
  // Dérivation à la main (barème SÉLECTIF, 2026 — TVA 20 %) :
  //   autoconsommé 6 000 × 0,85 = 5 100 kWh → résiduel 2 100 kWh/an
  //   résiduel 2 100/12 = 175 kWh/mois → bande 151-210 → 175 × 1,091388 =
  //                                            190,9929 × 12 = 2 291,9148
  //     TPPAN  10 + 75 × 0,15 = 21,25 MAD/mois × 12 = 255
  //     fixes  479,23 → facture 2 291,9148 + 479,232 + 255 = 3 026,15 → 3 026
  //   économie 13 364 − 3 026 = 10 338 MAD/an
  // En redescendant sous 510 PUIS sous 310, le client ne fait pas qu'effacer
  // des kWh : il RE-TARIFE tout son résiduel (1,622856 → 1,091388), et sa
  // TPPAN dégringole avec lui (les lignes fixes, elles, s'annulent).
  const r = twoBillsSavings(6000, 7200, 0.85, 'onee')
  assert.deepEqual(r, {
    factureSans: 13364, factureAvec: 3026, economie: 10338, autoconsoKwh: 5100,
  })
})

// ── VERROU DE DÉRIVE — barème SÉLECTIF : JS ↔ Python ↔ site ─────────────────
// Jumeau EXACT de apps/ventes/tests/test_bareme_selectif_fondateur.py (ERP) et
// de apps/web/tests/savingsTranchesFondateur.test.ts (site public). Les trois
// fichiers portent les MÊMES entrées et les MÊMES attendus, tous DÉRIVÉS À LA
// MAIN de la grille officielle (jamais copiés d'une sortie de code).
//
// ÉCART TEMPORAIRE ASSUMÉ ET DATÉ (QJR26, 29/08/2026) : la correction T5
// ci-dessous est portée sur les DEUX branches ERP (ce fichier + le jumeau
// Python), PAS sur la branche site — apps/web/** est une tâche séparée (QJW).
// Tant qu'elle n'a pas atterri, savingsTranchesFondateur.test.ts reste sur
// l'ancienne valeur. Le verrou à trois branches se referme avec QJW.
//
// Grille (TTC, 2026 — TVA 20 %) : progressif 0-100 = 0,916272 ·
// 101-150 = 1,091388 ; sélectif (toute la conso au tarif de sa tranche,
// tolérance 10 kWh) : 151-210 = 1,091388 · 211-310 = 1,187388 ·
// 311-510 = 1,381704 · > 510 = 1,622856.
//
// DÉCISION FONDATEUR D5 (29/08/2026) — T5 RECALÉE SUR LA FACTURE : 311-510
// vaut 1,381704 (facture SRM n° 643769639 du 08/05/2026 : 359 kWh × 1,15142 HT
// = 496,03 TTC ⇒ 1,15142 × 1,20), et non l'extrapolation « HT constant ». TOUS
// les attendus T5 ci-dessous ont été RE-DÉRIVÉS À LA MAIN de 1,381704.
const BAREME_FIXTURE = [
  [100, 91.6272],      // progressif : 100 × 0,916272
  [150, 146.1966],     // progressif : 91,6272 + 50 × 1,091388 (= 54,5694)
  [151, 164.799588],   // 1re marche sélective : 151 × 1,091388
  [210, 229.19148],    // haut de bande (tolérance) : 210 × 1,091388
  [211, 250.538868],   // bande suivante, TOUTE la conso : 211 × 1,187388
  [310, 368.09028],    // 310 × 1,187388
  [311, 429.709944],   // 311 × 1,381704
  [499, 689.470296],   // 499 × 1,381704
  [500, 690.852],      // 500 × 1,381704 — le seuil « 500 » du fondateur
  [501, 692.233704],   // 501 × 1,381704 (encore dans sa bande : borne effective 510)
  [510, 704.66904],    // 510 × 1,381704
  [511, 829.279416],   // 511 × 1,622856 — la marche du haut de grille
  [700, 1135.9992],    // 700 × 1,622856
]

test('VERROU — barème sélectif : chaque marche vaut le montant dérivé à la main', () => {
  for (const [kwh, mad] of BAREME_FIXTURE) {
    assert.ok(Math.abs(monthlyBillFromKwh(kwh, ONEE_TRANCHES) - mad) < 1e-9,
      `${kwh} kWh/mois → attendu ${mad} MAD, obtenu ${monthlyBillFromKwh(kwh, ONEE_TRANCHES)}`)
  }
  // La facture ne décroît JAMAIS quand la conso monte (monotonie du barème).
  for (let i = 1; i < BAREME_FIXTURE.length; i++) {
    assert.ok(BAREME_FIXTURE[i][1] > BAREME_FIXTURE[i - 1][1])
  }
  // 511 kWh coûte 124,610376 MAD de plus que 510 kWh pour UN kWh de plus :
  // c'est la marche sélective (829,279416 − 704,66904), pas une erreur d'arrondi.
  // La marche a GRANDI avec la correction D5 : son bas est descendu à 1,381704
  // alors que son haut (1,622856) n'a pas bougé.
  assert.ok(Math.abs((829.279416 - 704.66904) - 124.610376) < 1e-9)
})

test('VERROU — kwhFromBill est l’inverse EXACT sur toute la grille (aller-retour)', () => {
  for (const [kwh] of BAREME_FIXTURE) {
    assert.equal(kwhFromBill(monthlyBillFromKwh(kwh, ONEE_TRANCHES), 'onee').kwhMensuel, kwh)
  }
})

test('VERROU — scénario FONDATEUR : 700 kWh/mois, résiduel sous le seuil', () => {
  // « The client will go down in the price per kWh because he will be below
  //   500 kWh per month — I want the new price per kWh to be used. »
  // Dérivation à la main (2026 — TVA 20 %) :
  //   avant  700 kWh/mois → 700 × 1,622856 = 1 135,9992 MAD (1,622856 MAD/kWh)
  //   après  280 kWh/mois → 280 × 1,187388 =   332,46864 MAD (1,187388 MAD/kWh)
  //   économie 1 135,9992 − 332,46864 = 803,53056 MAD/mois → × 12 = 9 642,3672 MAD/an
  const avant = monthlyBillFromKwh(700, ONEE_TRANCHES)
  const apres = monthlyBillFromKwh(280, ONEE_TRANCHES)
  assert.ok(Math.abs(avant - 1135.9992) < 1e-9)
  assert.ok(Math.abs(apres - 332.46864) < 1e-9)
  assert.ok(Math.abs((avant - apres) - 803.53056) < 1e-9)
  // Le PRIX du kWh baisse vraiment (c'est la phrase du fondateur).
  assert.ok(Math.abs(avant / 700 - 1.622856) < 1e-9)
  assert.ok(Math.abs(apres / 280 - 1.187388) < 1e-9)
  // …et l'économie vaut PLUS que les 420 kWh effacés au tarif marginal :
  // 420 × 1,622856 = 681,59952 MAD < 803,53056 MAD (le résiduel est re-tarifé).
  assert.ok(Math.abs(420 * 1.622856 - 681.59952) < 1e-9)
  assert.ok(803.53056 > 681.59952)
  // Annualisation : 803,53056 × 12 = 9 642,3672 → 9 642 MAD/an. Le mois est
  // l'unité de tarification (le seuil est MENSUEL) : on ne divise jamais
  // l'année avant de tarifer.
  assert.equal(Math.round((avant - apres) * 12), 9642)
})

test('twoBillsSavings : dégrade en null sans donnée réelle (jamais un chiffre inventé)', () => {
  assert.equal(twoBillsSavings(0, 7200, 0.6, 'onee'), null) // pas de production
  assert.equal(twoBillsSavings(6000, 0, 0.6, 'onee'), null) // pas de conso
  assert.equal(twoBillsSavings(6000, 7200, 0, 'onee'), null) // pas de ratio
  assert.equal(twoBillsSavings(6000, 7200, 0.6, undefined), null) // pas de barème
  // CAD167 — un distributeur NOMMÉ (SRM) n'est plus « pas de barème » : grille nationale.
  assert.deepEqual(twoBillsSavings(6000, 7200, 0.6, 'srm_casablanca'),
    twoBillsSavings(6000, 7200, 0.6, 'onee'))
})
