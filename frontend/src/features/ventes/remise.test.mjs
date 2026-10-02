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
  arrondiCentime, ligneCompteDansTotaux, montantHtLigne, PAS_ARRONDI_DEVIS,
  puRemise, repartirRemiseParLigne, totauxCanoniques,
} from './remise.js'
import { htFromTtc, optionTotalsTTC, totauxCanoniquesTtc } from './solar.js'

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

// ── QJR642 — UN noyau, deux points d'entrée ─────────────────────────────────
// La même table passe par le GÉNÉRATEUR (`solar.totauxCanoniquesTtc` : TTC
// saisi → HT persisté → chaîne) et par la RÉPARTITION (`repartirRemiseParLigne`
// + `totauxCanoniques`), sur TROIS taux de TVA, remise 100 % comprise : HT net
// et TTC identiques au centime.
const TAUX = [10, 20, 14]
const FIXTURES_NOYAU = [
  ...FIXTURES,
  {
    nom: 'remise 100 % — HT net borné à 0',
    lignes: [['0.05', 'produit', false], ['1234.57', 'produit', false],
      ['10', 'produit', false]],
    pct: '100', htNet: '0.00',
  },
]

const avecTaux = (fixture) => enLignes(fixture).map((l, i) => ({
  ...l, taux: TAUX[i % TAUX.length],
}))
const enLignesGenerateur = (fixture) => fixture.lignes.map(
  ([montant, type, optionnelle], i) => {
    const taux = TAUX[i % TAUX.length]
    return {
      quantite: '1', taux_tva: taux, typeLigne: type, optionnelle,
      prix_unit_ttc: parseFloat(montant) * (1 + taux / 100),
    }
  })

for (const fixture of FIXTURES_NOYAU) {
  test(`QJR642 noyau unique (générateur ≡ répartition) : ${fixture.nom}`, () => {
    const generateur = enLignesGenerateur(fixture)
    // Précondition : le générateur persiste EXACTEMENT ces montants HT.
    generateur.forEach((l, i) => assert.equal(
      htFromTtc(l.prix_unit_ttc, l.taux_tva),
      parseFloat(fixture.lignes[i][0]).toFixed(2)))
    const noyau = totauxCanoniques(avecTaux(fixture), fixture.pct)
    assert.equal(noyau.htNet.toFixed(2), fixture.htNet)
    assert.ok(noyau.ttc >= 0, 'jamais un TTC négatif')
    assert.equal(totauxCanoniquesTtc(generateur, fixture.pct), noyau.ttc,
      'le générateur et la répartition rendent le MÊME TTC')
    const parts = repartirRemiseParLigne(enLignes(fixture), fixture.pct)
    const somme = parts.reduce((acc, p) => acc + (p === null ? 0 : Math.round(p * 100)), 0)
    assert.equal(somme, Math.round(noyau.htNet * 100),
      'la répartition somme au HT net du noyau')
    const tvaSomme = noyau.tvaParTaux.reduce((acc, t) => acc + Math.round(t.tva * 100), 0)
    assert.equal(Math.round(noyau.ttc * 100), Math.round(noyau.htNet * 100) + tvaSomme)
  })
}

// ── ARRONDI-100 (fondateur, 02/10/2026) ─────────────────────────────────────
// Miroir de `backend/django_core/apps/ventes/tests/test_arrondi_100.py` : MÊMES
// cas, MÊMES chiffres (produits par le noyau Python `_absorber_arrondi`).
const l = (quantite, prix, taux) => ({ quantite, prix_unitaire: prix, taux })
const SANS_0116 = [
  l(1, '30000.00', 20), l(42, '1200.00', 10), l(42, '416.67', 20),
  l(84, '66.67', 20), l(160, '10.83', 20), l(115, '11.67', 20),
  l(1, '1666.67', 20), l(1, '8333.33', 20), l(1, '11666.67', 20),
  l(1, '958.33', 20),
]
const AVEC_0116 = [l(1, '41666.67', 20), ...SANS_0116.slice(1)]
const arrondi = (lignes, pct = 0) => totauxCanoniques(
  lignes, pct, { arrondiPas: PAS_ARRONDI_DEVIS })

function invariants(t) {
  assert.equal(Math.round(t.htNet * 100) + Math.round(t.tva * 100),
    Math.round(t.ttc * 100), 'HT net + TVA = TTC au centime')
  assert.equal(Math.round(t.htBrut * 100) - Math.round(t.remise * 100)
    - Math.round(t.arrondi * 100), Math.round(t.htNet * 100))
  assert.ok(t.arrondi >= 0)
}

test('ARRONDI-100 — DEV-202609-0116 sans batterie : 150 000,32 → 150 000', () => {
  assert.equal(totauxCanoniques(SANS_0116, 0).ttc, 150000.32)
  const t = arrondi(SANS_0116)
  assert.equal(t.ttc, 150000)
  assert.equal(t.arrondi, 0.27)
  assert.equal(t.htNet, 129200)
  invariants(t)
})

test('ARRONDI-100 — DEV-202609-0116 avec batterie : 164 000,33 → 164 000', () => {
  assert.equal(totauxCanoniques(AVEC_0116, 0).ttc, 164000.33)
  const t = arrondi(AVEC_0116)
  assert.equal(t.ttc, 164000)
  invariants(t)
})

test('ARRONDI-100 — 150 057 → 150 000 (47,50 HT d’arrondi)', () => {
  const t = arrondi([l(1, '125047.50', 20)])
  assert.equal(t.ttc, 150000)
  assert.equal(t.arrondi, 47.5)
  invariants(t)
})

test('ARRONDI-100 — un second panier cède un centime', () => {
  const t = arrondi([l(1, '6223.01', 10), l(1, '14609.98', 20)])
  assert.equal(t.ttc, 24300)
  assert.equal(t.arrondi, 64.41)
  const paniers = Object.fromEntries(t.tvaParTaux.map(p => [p.taux, p.htNet]))
  assert.equal(paniers[10], 6223)
  assert.equal(paniers[20], 14545.58)
  invariants(t)
})

test('ARRONDI-100 — mono-taux 10 % inatteignable : palier d’en dessous', () => {
  const t = arrondi([l(1, '455.00', 10)])
  assert.equal(t.ttc, 400)
  invariants(t)
})

test('ARRONDI-100 — sous le palier, rond, ou sans palier : inchangé', () => {
  assert.equal(arrondi([l(1, '47.50', 20)]).ttc, 57)
  assert.equal(arrondi([l(10, '1000', 20)]).arrondi, 0)
  assert.equal(totauxCanoniques(SANS_0116, 5).arrondi, 0)
})

test('ARRONDI-100 — le générateur affiche les totaux par option au palier', () => {
  const lignes = [
    { designation: 'Onduleur réseau 5kW', quantite: '1', prix_unit_ttc: 9999.99, taux_tva: 20 },
    { designation: 'Panneau 550W', quantite: '10', prix_unit_ttc: 1234.56, taux_tva: 10 },
    { designation: 'Installation', quantite: '1', prix_unit_ttc: 3456.78, taux_tva: 20 },
  ]
  const tot = optionTotalsTTC(lignes, 0)
  assert.equal(tot.totalSans % 100, 0)
  assert.equal(tot.totalSansBrut, tot.totalSans, 'sans remise, aucun prix barré fantôme')
  assert.ok(totauxCanoniquesTtc(lignes, 0) - tot.totalSans < 100)
})
