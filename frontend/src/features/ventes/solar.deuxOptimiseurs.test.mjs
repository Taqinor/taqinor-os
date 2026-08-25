// L-2OPT (fondateur 24/08/2026) — « deux optimiseurs indépendants ». Un devis
// résidentiel « Les deux (Sans + Avec) » ne dimensionne plus les deux options
// sur le MÊME kWc : l'écran compose SANS (optimum payback sans batterie,
// comportement historique) et AVEC (optimum payback AVEC batterie —
// `optimalKwcByPayback({ avecBatterie: true })`, jamais utilisé jusqu'ici)
// séparément, puis fusionne ligne à ligne (`fusionnerVariantes`) :
//   • ligne identique (produit, désignation, PU, taux TVA, quantité)
//     → UNE ligne commune `variante: ''` ;
//   • quantité (ou produit) divergente → DEUX lignes `variante: 'sans'` /
//     `'avec'`, chacune portant SA quantité ;
//   • présente d'un seul côté → sa variante.
// Repli de sécurité (verrouillé ici) : deux compositions IDENTIQUES (le cas
// le plus courant, et le repli quand aucune source n'a d'avis sur l'optimum
// AVEC) fusionnent en lignes 100 % `variante: ''` — résultat BYTE-IDENTIQUE
// à l'ancienne composition unique.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  fusionnerVariantes, optionTotalsTTC, batteryKwhFromLines, computeROI,
  INVERTER_REPLACE_YEAR, optimalKwcByPayback,
} from './solar.js'

// ── fusionnerVariantes ────────────────────────────────────────────────────

test('fusionnerVariantes : deux compositions IDENTIQUES → repli byte-identique, AUCUNE ligne variantée', () => {
  const lignes = [
    { produit: '1', designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000, taux_tva: 20 },
    { produit: '2', designation: 'Panneau Canadien Solar 710W', quantite: 14, prix_unit_ttc: 1400, taux_tva: 10 },
    { produit: '', designation: 'Batterie', quantite: 0, prix_unit_ttc: 0, taux_tva: 20 },
  ]
  const fusion = fusionnerVariantes(lignes, lignes)
  assert.equal(fusion.length, lignes.length)
  for (const l of fusion) assert.equal(l.variante, '')
  // Byte-identique : mêmes champs que l'original, la seule addition est `variante`.
  fusion.forEach((l, i) => {
    const { variante, ...rest } = l
    assert.deepEqual(rest, lignes[i])
  })
})

test('fusionnerVariantes : quantité divergente (kwc_sans ≠ kwc_avec) → deux lignes variantées, le reste commun', () => {
  const sans = [
    { produit: '2', designation: 'Panneau Canadien Solar 710W', quantite: 10, prix_unit_ttc: 1400, taux_tva: 10 },
    { produit: '3', designation: 'Transport', quantite: 1, prix_unit_ttc: 1000, taux_tva: 20 },
  ]
  const avec = [
    { produit: '2', designation: 'Panneau Canadien Solar 710W', quantite: 17, prix_unit_ttc: 1400, taux_tva: 10 },
    { produit: '3', designation: 'Transport', quantite: 1, prix_unit_ttc: 1000, taux_tva: 20 },
  ]
  const fusion = fusionnerVariantes(sans, avec)
  assert.equal(fusion.length, 3)
  const panneaux = fusion.filter(l => l.designation === 'Panneau Canadien Solar 710W')
  assert.equal(panneaux.length, 2)
  assert.deepEqual(panneaux.map(l => l.variante).sort(), ['avec', 'sans'])
  assert.equal(panneaux.find(l => l.variante === 'sans').quantite, 10)
  assert.equal(panneaux.find(l => l.variante === 'avec').quantite, 17)
  const transport = fusion.find(l => l.designation === 'Transport')
  assert.equal(transport.variante, '')
  assert.equal(transport.quantite, 1)
})

test('fusionnerVariantes : onduleur réseau divergent → UNE ligne, le panier SANS fait foi', () => {
  // Correctif orchestrateur 25/08 (aligné backend fusionner_kits) : le réseau
  // appartient à l'option sans — l'exemplaire dimensionné pour kwc_avec est un
  // fantôme que personne n'achète, il est ÉCARTÉ (jamais tagué 'avec').
  const sans = [{ produit: '10', designation: 'Onduleur réseau Huawei 10kW', quantite: 1, prix_unit_ttc: 20000, taux_tva: 20 }]
  const avec = [{ produit: '11', designation: 'Onduleur réseau Huawei 12kW', quantite: 1, prix_unit_ttc: 24000, taux_tva: 20 }]
  const fusion = fusionnerVariantes(sans, avec)
  assert.equal(fusion.length, 1)
  assert.equal(fusion[0].variante, 'sans')
  assert.equal(fusion[0].prix_unit_ttc, 20000)
})

test('fusionnerVariantes : batterie divergente → UNE ligne, le panier AVEC fait foi (jamais de batterie taguée sans)', () => {
  // Le PDF/l'aval rangent une ligne par sa DÉCLARATION : une batterie taguée
  // 'sans' serait facturée dans l'option « Sans batterie ». Le panier
  // propriétaire fait foi — l'exemplaire dimensionné pour kwc_sans disparaît.
  const sans = [{ produit: '2', designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 30000, taux_tva: 20 }]
  const avec = [{ produit: '2', designation: 'Batterie Dyness 10 kWh', quantite: 2, prix_unit_ttc: 30000, taux_tva: 20 }]
  const fusion = fusionnerVariantes(sans, avec)
  assert.equal(fusion.length, 1)
  assert.equal(fusion[0].variante, 'avec')
  assert.equal(fusion[0].quantite, 2)
})

test('fusionnerVariantes : onduleur hybride divergent → UNE ligne, le panier AVEC fait foi', () => {
  const sans = [{ produit: '20', designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: 1, prix_unit_ttc: 28000, taux_tva: 20 }]
  const avec = [{ produit: '21', designation: 'Onduleur hybride Deye 15kW Triphasé', quantite: 1, prix_unit_ttc: 36000, taux_tva: 20 }]
  const fusion = fusionnerVariantes(sans, avec)
  assert.equal(fusion.length, 1)
  assert.equal(fusion[0].variante, 'avec')
  assert.equal(fusion[0].prix_unit_ttc, 36000)
})

test('fusionnerVariantes : batterie identique des deux côtés → ligne commune (split mots-clés historique)', () => {
  const ligne = { produit: '2', designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 30000, taux_tva: 20 }
  const fusion = fusionnerVariantes([ligne], [{ ...ligne }])
  assert.equal(fusion.length, 1)
  assert.equal(fusion[0].variante, '')
})

test('fusionnerVariantes : ligne présente d\'un seul côté → sa variante', () => {
  const sans = [{ produit: '1', designation: 'A', quantite: 1, prix_unit_ttc: 10, taux_tva: 20 }]
  const avec = [
    { produit: '1', designation: 'A', quantite: 1, prix_unit_ttc: 10, taux_tva: 20 },
    { produit: '2', designation: 'Batterie Dyness 5 kWh', quantite: 2, prix_unit_ttc: 17000, taux_tva: 20 },
  ]
  const fusion = fusionnerVariantes(sans, avec)
  assert.equal(fusion.length, 2)
  assert.equal(fusion[0].variante, '')
  assert.equal(fusion[1].variante, 'avec')
})

test('fusionnerVariantes : entrées vides/non tableau ne lèvent jamais', () => {
  assert.deepEqual(fusionnerVariantes(null, undefined), [])
  assert.deepEqual(fusionnerVariantes([], []), [])
})

// ── optionTotalsTTC — variante D'ABORD, mots-clés EN REPLI ─────────────────

test('optionTotalsTTC : lignes SANS champ `variante` — comportement historique inchangé', () => {
  const lignes = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000 },
    { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: 1, prix_unit_ttc: 28000 },
    { designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 17000 },
    { designation: 'Panneau Canadien Solar 710W', quantite: 14, prix_unit_ttc: 1400 },
  ]
  const { totalSans, totalAvec } = optionTotalsTTC(lignes, 0)
  assert.equal(totalSans, 20000 + 14 * 1400)
  assert.equal(totalAvec, 28000 + 17000 + 14 * 1400)
})

test('optionTotalsTTC : une fusion sans/avec calcule les BONS totaux (sans double-compte, sans fuite)', () => {
  const lignes = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000, variante: '' },
    { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: 1, prix_unit_ttc: 28000, variante: '' },
    { designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 17000, variante: '' },
    { designation: 'Panneau Canadien Solar 710W', quantite: 10, prix_unit_ttc: 1400, variante: 'sans' },
    { designation: 'Panneau Canadien Solar 710W', quantite: 17, prix_unit_ttc: 1400, variante: 'avec' },
    { designation: 'Transport', quantite: 1, prix_unit_ttc: 1000, variante: '' },
  ]
  const { totalSans, totalAvec } = optionTotalsTTC(lignes, 0)
  // sans = réseau (commun) + panneau 'sans' (10) + transport (commun) ;
  // batterie/hybride (commun, mais mot-clé) + panneau 'avec' exclus.
  assert.equal(totalSans, 20000 + 10 * 1400 + 1000)
  // avec = hybride + batterie (communs) + panneau 'avec' (17) + transport ;
  // réseau (mot-clé) + panneau 'sans' (variante) exclus.
  assert.equal(totalAvec, 28000 + 17000 + 17 * 1400 + 1000)
})

// ── batteryKwhFromLines — une ligne 'sans' résiduelle ne compte jamais ─────

test('batteryKwhFromLines : une ligne batterie taguée \'sans\' (résidu inévitable de la composition SANS quand les deux optima divergent) ne compte jamais', () => {
  const lignes = [
    { designation: 'Batterie Dyness 5 kWh', quantite: 2, variante: 'sans' },
    { designation: 'Batterie Dyness 10 kWh', quantite: 1, variante: 'avec' },
  ]
  // Seule la ligne 'avec' compte : 1 × 10 kWh.
  assert.equal(batteryKwhFromLines(lignes), 10)
})

test('batteryKwhFromLines : lignes SANS champ `variante` — comportement historique inchangé', () => {
  const lignes = [{ designation: 'Batterie Dyness 5 kWh', quantite: 2 }]
  assert.equal(batteryKwhFromLines(lignes), 10)
})

// ── computeROI — la provision onduleur ne double-compte jamais une ligne
// 'sans' résiduelle (autoFillLines compose TOUJOURS un onduleur hybride/une
// batterie, même côté SANS — cette ligne, exclue des totaux, ne doit pas non
// plus fausser la provision de remplacement de l'option AVEC). ────────────

test('L-2OPT — computeROI : une ligne onduleur hybride taguée \'sans\' ne double-compte jamais la provision AVEC', () => {
  const lignesMergees = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: '1', prix_unit_ttc: '20000', variante: 'sans' },
    // hybride divergent : la composition SANS (kwc=10) et la composition
    // AVEC (kwc=15) choisissent chacune un modèle différent → deux lignes.
    { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: '1', prix_unit_ttc: '28000', variante: 'sans' },
    { designation: 'Onduleur hybride Deye 15kW Triphasé', quantite: '1', prix_unit_ttc: '36000', variante: 'avec' },
    { designation: 'Batterie Dyness 10 kWh', quantite: '2', variante: 'avec' },
    { designation: 'Panneau Canadien Solar 710W', quantite: '17', prix_unit_ttc: '1400', variante: 'avec' },
  ]
  const lignesAvecSeul = lignesMergees.filter(l => l.variante !== 'sans')
  const base = {
    kwp: 12, factures: Array(12).fill(1500), dayUsagePct: 60,
    totalSans: 100000, totalAvec: 140000, batteryKwh: batteryKwhFromLines(lignesMergees),
  }
  const withMerged = computeROI({ ...base, lines: lignesMergees })
  const withAvecSeul = computeROI({ ...base, lines: lignesAvecSeul })
  assert.equal(
    withMerged.cashflow_avec[INVERTER_REPLACE_YEAR - 1],
    withAvecSeul.cashflow_avec[INVERTER_REPLACE_YEAR - 1],
    'la ligne hybride \'sans\' (28 000) ne doit JAMAIS s\'ajouter à la provision AVEC (36 000)')
})

test('L-2OPT — computeROI : une ligne onduleur réseau taguée \'avec\' ne double-compte jamais la provision SANS', () => {
  const lignesMergees = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: '1', prix_unit_ttc: '20000', variante: 'sans' },
    { designation: 'Onduleur réseau Huawei 12kW Triphasé', quantite: '1', prix_unit_ttc: '24000', variante: 'avec' },
    { designation: 'Panneau Canadien Solar 710W', quantite: '10', prix_unit_ttc: '1400', variante: 'sans' },
  ]
  const lignesSansSeul = lignesMergees.filter(l => l.variante !== 'avec')
  const base = {
    kwp: 10, factures: Array(12).fill(1500), dayUsagePct: 60,
    totalSans: 90000, totalAvec: 130000, batteryKwh: 0,
  }
  const withMerged = computeROI({ ...base, lines: lignesMergees })
  const withSansSeul = computeROI({ ...base, lines: lignesSansSeul })
  assert.equal(
    withMerged.cashflow_sans[INVERTER_REPLACE_YEAR - 1],
    withSansSeul.cashflow_sans[INVERTER_REPLACE_YEAR - 1])
})

// ── optimalKwcByPayback(avecBatterie: true) — le second optimiseur existe
// déjà (verrouillé par solar.dimensionnement.test.mjs pour `avecBatterie:
// false`) ; ce test confirme seulement qu'il peut retenir un palier
// DIFFÉRENT de l'optimum sans batterie sur un catalogue synthétique où le
// payback AVEC est minimisé par une taille plus grande. ───────────────────

test('L-2OPT — optimalKwcByPayback(avecBatterie: true) peut retenir un palier différent de avecBatterie: false', () => {
  const ht = (ttc) => (ttc / 1.2).toFixed(2)
  let _id = 0
  const P = (nom, ttc) => ({ id: ++_id, nom, prix_vente: ht(ttc) })
  const PRODUITS = [
    P('Onduleur réseau Huawei 5kW Monophasé', 14000),
    P('Onduleur réseau Huawei 10kW Monophasé', 18000),
    P('Onduleur hybride Deye 5kW Monophasé', 17000),
    P('Onduleur hybride Deye 10kW Monophasé', 28000),
    P('Panneau Canadien Solar 710W', 1400),
    P('Batterie Dyness 5 kWh', 17000),
    P('Structures acier', 500),
    P('Socles', 80),
    P('Accessoires', 2000),
    P('Tableau De Protection AC/DC', 2000),
    P('Installation', 4800),
    P('Transport', 1000),
    P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
  ]
  const FACTURES = Array(12).fill(2600)
  const commun = {
    produits: PRODUITS, factures: FACTURES, dayUsagePct: 60,
    panelW: 710, structureType: 'acier', besoinKwc: 10,
  }
  const sans = optimalKwcByPayback(commun)
  const avec = optimalKwcByPayback({ ...commun, avecBatterie: true })
  // Les deux restent des paliers valides du même balayage — la fonction ne
  // lève jamais, l'un OU l'autre peut légitimement coïncider ou diverger
  // selon le catalogue ; ce test verrouille juste qu'un objectif AVEC
  // batterie est bien pris en compte séparément (paybacks distincts par
  // palier, jamais le même tableau que « sans »).
  assert.ok(sans.kwcOptimal > 0)
  assert.ok(avec.kwcOptimal > 0)
  const paliersDivergent = sans.paliers.some((p, i) =>
    p.payback !== avec.paliers[i]?.payback)
  assert.ok(paliersDivergent, 'le payback AVEC batterie devrait différer du payback SANS par palier')
})
