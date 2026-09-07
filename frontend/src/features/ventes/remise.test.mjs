// QJRREM — le miroir JS de `domain.argent.repartir_remise_par_ligne`.
// Exécutés en CI : node --test src/features/ventes/remise.test.mjs
//
// LA TABLE `FIXTURES` CI-DESSOUS EST LA MÊME, CAS POUR CAS ET VALEUR POUR
// VALEUR, que celle de `backend/django_core/apps/ventes/tests/
// test_remise_par_ligne.py` (constante `FIXTURES`). Les `attendus` ont été
// produits par l'implémentation PYTHON : si les deux répartitions divergent
// d'un centime, l'un des deux fichiers devient rouge. C'est tout l'objet de
// cette table — un écran et un PDF du même devis ne peuvent pas se contredire.
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  arrondiCentime, ligneCompteDansTotaux, montantHtLigne, puRemise,
  repartirRemiseParLigne,
} from './remise.js'

// nom, lignes [montant HT, type de ligne, optionnelle], remise globale en %,
// puis ce que la chaîne canonique arrête (remise, ht_net) et la répartition.
export const FIXTURES = [
  {
    nom: 'trois lignes à 33,33 — remise 5 %',
    lignes: [['33.33', 'produit', false], ['33.33', 'produit', false],
      ['33.33', 'produit', false]],
    pct: '5', remise: '5.00', htNet: '94.99',
    attendus: ['31.67', '31.66', '31.66'],
  },
  {
    nom: 'sept panneaux + onduleur + pose — remise 5 %',
    lignes: [['8166.69', 'produit', false], ['12500', 'produit', false],
      ['3333.33', 'produit', false]],
    pct: '5', remise: '1200.00', htNet: '22800.02',
    attendus: ['7758.36', '11875.00', '3166.66'],
  },
  {
    nom: 'remise DE LIGNE déjà appliquée — remise globale 8 %',
    lignes: [['1425.00', 'produit', false], ['950.00', 'produit', false],
      ['47.50', 'produit', false]],
    pct: '8', remise: '193.80', htNet: '2228.70',
    attendus: ['1311.00', '874.00', '43.70'],
  },
  {
    nom: 'remise nulle — aucun changement',
    lignes: [['33.33', 'produit', false], ['11.11', 'produit', false]],
    pct: '0', remise: '0.00', htNet: '44.44',
    attendus: ['33.33', '11.11'],
  },
  {
    nom: 'section et add-on non activé — aucune part',
    lignes: [['1000', 'produit', false], ['0', 'section', false],
      ['500', 'produit', true], ['333.33', 'produit', false]],
    pct: '15', remise: '200.00', htNet: '1133.33',
    attendus: ['850.00', null, null, '283.33'],
  },
  {
    nom: 'taux mixtes 10 / 20 — remise 12 %',
    lignes: [['16000', 'produit', false], ['24000', 'produit', false],
      ['1234.56', 'produit', false]],
    pct: '12', remise: '4948.15', htNet: '36286.41',
    attendus: ['14080.00', '21120.00', '1086.41'],
  },
  {
    nom: 'résidu NÉGATIF — un centime retiré à la première ligne',
    lignes: [['0.07', 'produit', false], ['0.07', 'produit', false],
      ['0.07', 'produit', false]],
    pct: '5', remise: '0.01', htNet: '0.20',
    attendus: ['0.06', '0.07', '0.07'],
  },
  {
    nom: 'devis complet de dix lignes — remise 5 %',
    lignes: [['11700', 'produit', false], ['24000', 'produit', false],
      ['15400', 'produit', false], ['14000', 'produit', false],
      ['5250', 'produit', false], ['2010', 'produit', false],
      ['1667', 'produit', false], ['1667', 'produit', false],
      ['4000', 'produit', false], ['1000', 'produit', false]],
    pct: '5', remise: '4034.70', htNet: '76659.30',
    attendus: ['11115.00', '22800.00', '14630.00', '13300.00', '4987.50',
      '1909.50', '1583.65', '1583.65', '3800.00', '950.00'],
  },
  {
    nom: 'devis complet de dix lignes — remise 15 %',
    lignes: [['11700', 'produit', false], ['24000', 'produit', false],
      ['15400', 'produit', false], ['14000', 'produit', false],
      ['5250', 'produit', false], ['2010', 'produit', false],
      ['1667', 'produit', false], ['1667', 'produit', false],
      ['4000', 'produit', false], ['1000', 'produit', false]],
    pct: '15', remise: '12104.10', htNet: '68589.90',
    attendus: ['9945.00', '20400.00', '13090.00', '11900.00', '4462.50',
      '1708.50', '1416.95', '1416.95', '3400.00', '850.00'],
  },
  {
    nom: 'une seule ligne — remise 7,5 %',
    lignes: [['10000', 'produit', false]],
    pct: '7.5', remise: '750.00', htNet: '9250.00',
    attendus: ['9250.00'],
  },
]

const enLignes = (fixture) => fixture.lignes.map(
  ([montant, type, optionnelle]) => ({
    totalHt: montant, typeLigne: type, optionnelle,
  }))

const fmt = (v) => (v === null ? null : v.toFixed(2))

for (const fixture of FIXTURES) {
  test(`repartirRemiseParLigne : ${fixture.nom}`, () => {
    const parts = repartirRemiseParLigne(enLignes(fixture), fixture.pct)
    assert.deepEqual(parts.map(fmt), fixture.attendus,
      'la répartition doit être celle du noyau Python, au centime')
  })

  test(`somme == Total HT net : ${fixture.nom}`, () => {
    const parts = repartirRemiseParLigne(enLignes(fixture), fixture.pct)
    const somme = parts.reduce(
      (acc, p) => acc + (p === null ? 0 : Math.round(p * 100)), 0)
    assert.equal(somme, Math.round(parseFloat(fixture.htNet) * 100),
      'invariant #10 : Σ lignes remisées == Total HT net, au centime')
  })
}

test('remise nulle : chaque ligne garde son montant, à l’identique', () => {
  const lignes = [{ totalHt: '1500' }, { totalHt: '2333.33' }]
  assert.deepEqual(repartirRemiseParLigne(lignes, 0), [1500, 2333.33])
  assert.deepEqual(repartirRemiseParLigne(lignes, '0'), [1500, 2333.33])
})

test('aucune ligne comptée : que des null, jamais une exception', () => {
  assert.deepEqual(
    repartirRemiseParLigne(
      [{ totalHt: '10', typeLigne: 'note' }, { totalHt: '5', optionnelle: true }],
      5),
    [null, null],
  )
  assert.deepEqual(repartirRemiseParLigne([], 5), [])
  assert.deepEqual(repartirRemiseParLigne(null, 5), [])
})

test('déterministe : deux appels rendent la MÊME répartition', () => {
  const lignes = [{ totalHt: '33.33' }, { totalHt: '33.33' }, { totalHt: '33.33' }]
  assert.deepEqual(repartirRemiseParLigne(lignes, 5),
    repartirRemiseParLigne(lignes, 5))
})

test('montantHtLigne : quantité × prix × (1 − remise de ligne)', () => {
  // MÊME formule que `LigneDevis.total_ht` : le produit brut, NON arrondi
  // (7 × 1166,67 vaut 8166,690000000001 en flottant — c'est précisément
  // pourquoi la répartition, elle, quantifie au centime).
  assert.equal(
    arrondiCentime(montantHtLigne({ quantite: '7', prix_unitaire: '1166.67' })),
    8166.69)
  assert.equal(
    montantHtLigne({ quantite: '2', prix_unitaire: '1000', remise: '10' }),
    1800)
  // `totalHt` fourni ⇒ il fait foi (aucun recalcul).
  assert.equal(montantHtLigne({ totalHt: '42.42', quantite: '9' }), 42.42)
  assert.equal(montantHtLigne({}), 0)
})

test('lignes saisies (quantité × prix) : même répartition que par totalHt', () => {
  const parSaisie = repartirRemiseParLigne([
    { quantite: '7', prix_unitaire: '1166.67' },
    { quantite: '1', prix_unitaire: '12500' },
    { quantite: '1', prix_unitaire: '3333.33' },
  ], 5)
  assert.deepEqual(parSaisie.map(fmt), ['7758.36', '11875.00', '3166.66'])
})

test('ligneCompteDansTotaux : produit non optionnelle uniquement', () => {
  assert.equal(ligneCompteDansTotaux({}), true)
  assert.equal(ligneCompteDansTotaux({ typeLigne: 'produit' }), true)
  assert.equal(ligneCompteDansTotaux({ type_ligne: 'produit' }), true)
  assert.equal(ligneCompteDansTotaux({ typeLigne: 'section' }), false)
  assert.equal(ligneCompteDansTotaux({ typeLigne: 'note' }), false)
  assert.equal(ligneCompteDansTotaux({ optionnelle: true }), false)
  assert.equal(ligneCompteDansTotaux(null), false)
})

test('puRemise : le P.U. dérive du TOTAL réparti, arrondi au centime', () => {
  assert.equal(puRemise(100, 3), 33.33)
  assert.equal(puRemise('7758.36', 7), 1108.34)
  assert.equal(puRemise(1425, 1), 1425)
  // quantité fractionnaire (mètres de câble, journées de pose)
  assert.equal(puRemise('93.75', '2.5'), 37.5)
  // quantité nulle ou absente ⇒ 0, jamais une division par zéro
  assert.equal(puRemise(100, 0), 0)
  assert.equal(puRemise(100, undefined), 0)
})

test('arrondiCentime : MOITIÉ VERS LE HAUT sur la valeur décimale', () => {
  // `Number(1.005).toFixed(2)` rend « 1.00 » (arrondi binaire) : le miroir
  // doit rendre 1,01, comme `Decimal(str(1.005)).quantize(ROUND_HALF_UP)`.
  assert.equal(arrondiCentime(1.005), 1.01)
  assert.equal(arrondiCentime(2.675), 2.68)
  assert.equal(arrondiCentime(-1.005), -1.01)
  assert.equal(arrondiCentime('33.334'), 33.33)
  assert.equal(arrondiCentime(null), 0)
})
