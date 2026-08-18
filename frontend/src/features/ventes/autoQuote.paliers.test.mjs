// Verrouille la règle fondateur du 18/08 telle qu'appliquée par
// autoQuote.js::createAutoQuote (branche facture, mode non-agricole) :
//   1. une taille EXPLICITE (cible du devis ou taille souhaitée du lead) est
//      ramenée au palier de 5 kWc le plus proche (arrondirAuPasKwc) ;
//   2. sans taille explicite, le besoin se lit sur la facture d'hiver
//      (estimerKwcDepuisFacture) et la taille retenue minimise le payback
//      parmi les paliers testés (optimalKwcByPayback) — jamais la plus
//      grosse qui rentre sur le toit.
//
// autoQuote.js ne peut pas être importé tel quel par `node --test` (import
// relatif sans extension vers ./store/ventesSlice, résolu par Vite mais pas
// par l'ESM natif de Node, + dépendance à un `dispatch` Redux réel) : ce test
// rejoue donc EXACTEMENT la même séquence d'appels solar.js que la branche
// facture de createAutoQuote, avec les mêmes paramètres par défaut
// (panelW=710, dayUsagePct résidentiel), pour prouver que le résultat
// respecte la règle des paliers — sans dupliquer la formule elle-même
// (elle vit uniquement dans solar.js, testée par solar.dimensionnement.test.mjs).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  KWC_STEP, estimerKwcDepuisFacture, arrondirAuPasKwc, optimalKwcByPayback,
  estimerMois, panneauxPourKwc, DAY_USAGE_DEFAULTS, KWH_PRICE, EFFICIENCY,
  autoFillLines, roleLabel,
} from './solar.js'

const ici = dirname(fileURLToPath(import.meta.url))
const lire = (rel) => readFileSync(join(ici, rel), 'utf-8')

const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc) => ({ id: ++_id, nom, prix_vente: ht(ttc) })
const SEEDED = [
  P('Onduleur réseau Huawei 5kW Monophasé', 14000),
  P('Onduleur réseau Huawei 10kW Monophasé', 18000),
  P('Onduleur réseau Huawei 12kW Monophasé', 20000),
  P('Onduleur réseau Huawei 15kW Triphasé', 23000),
  P('Onduleur réseau Huawei 20kW Triphasé', 28000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Structures acier', 500),
  P('Socles', 80),
  P('Smart Meter', 1800),
  P('Wifi Dongle', 1200),
  P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000),
  P('Installation', 4800),
  P('Transport', 1000),
  P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

// Rejoue la branche « bill fallback » de createAutoQuote (lead sans taille
// souhaitée, sans cible de devis) pour un lead résidentiel.
function sizeFromBillLikeAutoQuote(hiver) {
  const besoinKwc = estimerKwcDepuisFacture(hiver)
  if (besoinKwc <= 0) return null
  const opt = optimalKwcByPayback({
    produits: SEEDED, factures: estimerMois(hiver, hiver),
    dayUsagePct: DAY_USAGE_DEFAULTS['Résidentielle'],
    panelW: 710, structureType: 'acier', discountPct: '0',
    kwhPrice: KWH_PRICE, efficiency: EFFICIENCY, besoinKwc,
  })
  return opt
}

test('devis auto sans taille explicite : la taille retenue est un palier de 5 kWc, jamais plus que le besoin facture', () => {
  const hiver = 2600 // → besoin 10 kWc (2600/900 = 2 tranches pleines)
  const res = sizeFromBillLikeAutoQuote(hiver)
  assert.ok(res, 'un palier doit être trouvé pour une facture au-dessus du seuil')
  assert.equal(res.kwcOptimal % KWC_STEP, 0, `taille hors palier : ${res.kwcOptimal}`)
  assert.ok(res.kwcOptimal <= estimerKwcDepuisFacture(hiver),
    'la taille retenue ne doit jamais dépasser le besoin lu sur la facture')
  assert.ok(res.nbPanneaux > 0)
})

test('devis auto sous le seuil de 900 MAD : aucun palier chiffrable, on retombe sur le repli historique', () => {
  const hiver = 500 // < 900 MAD → besoin 0
  assert.equal(estimerKwcDepuisFacture(hiver), 0)
  const res = sizeFromBillLikeAutoQuote(hiver)
  assert.equal(res, null, 'sous le seuil, createAutoQuote garde estimerPanneaux (comportement historique)')
})

test('devis auto AVEC taille explicite (cible ou lead) : toujours ramenée au palier de 5 kWc le plus proche', () => {
  // Une cible de 7 kWc (par ex. saisie ponctuelle du commercial) n'est jamais
  // envoyée telle quelle au catalogue — elle est d'abord arrondie au palier.
  const cibleBrute = 7
  const tailleRetenue = arrondirAuPasKwc(cibleBrute)
  assert.equal(tailleRetenue, 5)
  const panels = panneauxPourKwc(tailleRetenue, 710)
  assert.ok(panels > 0)
  // La puissance PV qui en résulte reste proche du palier (± 1 panneau, un
  // nombre entier de panneaux de 710 W ne tombe jamais pile sur 5,000 kWc).
  const kwpReel = panels * 710 / 1000
  assert.ok(Math.abs(kwpReel - tailleRetenue) < 0.71)
})

// ── PVMRQ — GARDE « devis auto sans panneaux » (correctif 18/08) ─────────────
// `createAutoQuote` n'enregistre que les lignes qui ont un produit ET une
// quantité > 0. Une marque épinglée absente du stock laisse la ligne concernée
// en PLACEHOLDER (aucun produit, 0 MAD) : elle était donc écartée EN SILENCE et
// le devis partait sans panneaux, à un prix effondré. La garde REFUSE désormais
// la création, avec EXACTEMENT le message du bandeau de DevisGenerator —
// LeadDevisPanel le rend tel quel (`setErrorMsg(err.detail)`).

// Catalogue SANS Jinko : la marque épinglée n'a aucun candidat.
const CATALOGUE_SANS_JINKO = [
  P('Onduleur réseau Huawei 10kW Monophasé', 18000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Structures acier', 500), P('Socles', 80), P('Installation', 4800),
]

const MESSAGE_ATTENDU =
  'Marque épinglée introuvable au stock : Jinko (Panneaux). '
  + 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.'

test('devis auto : une marque épinglée absente laisserait un devis SANS panneaux', () => {
  // Rejoue l'appel `autoFillLines` de createAutoQuote (branche non-agricole).
  const rows = autoFillLines(CATALOGUE_SANS_JINKO, {
    kwp: 14 * 710 / 1000, panelW: 710, nbPanneaux: 14,
    structureType: 'acier', marques: { panneau: 'Jinko' },
  })
  assert.deepEqual(rows.marquesManquantes, [{ role: 'panneau', marque: 'Jinko' }])
  // La ligne panneaux existe (quantité 14) mais SANS produit ni prix…
  const pan = rows.find(r => /panneau/i.test(r.designation))
  assert.equal(pan.produit, '')
  assert.equal(pan.prix_unit_ttc, 0)
  assert.ok(parseFloat(pan.quantite) > 0)
  // …donc le filtre d'enregistrement de createAutoQuote la jette : c'est
  // exactement le devis muet que la garde doit empêcher.
  const enregistrees = rows.filter(r => r.produit && parseFloat(r.quantite) > 0)
  assert.ok(!enregistrees.some(r => /panneau/i.test(r.designation)),
    'sans garde, le devis serait créé sans aucune ligne panneau')
  // Message que la garde doit lever, construit avec le VRAI libellé de rôle.
  const detail = `Marque épinglée introuvable au stock : ${rows.marquesManquantes
    .map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')}. `
    + 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.'
  assert.equal(detail, MESSAGE_ATTENDU)
})

test('devis auto : la garde lève AVANT createDevis (aucun devis vide persisté)', () => {
  const src = lire('./autoQuote.js')
  const garde = src.indexOf('rows.marquesManquantes ?? []')
  const jet = src.indexOf('Marque épinglée introuvable au stock')
  const creation = src.indexOf('await dispatch(createDevis(')
  assert.ok(garde > 0, 'createAutoQuote doit relever rows.marquesManquantes')
  assert.ok(jet > garde, 'la garde doit lever le message de marque manquante')
  assert.ok(jet < creation,
    'la garde doit lever AVANT createDevis — sinon un devis vide est persisté')
  // Le `detail` est bien la clé lue par LeadDevisPanel (`err.detail`).
  assert.ok(/throw \{\s*\n\s*detail: `Marque épinglée introuvable au stock/.test(src),
    'le jet doit porter la clé `detail`')
  // Second filet : plus aucun panneau chiffrable, même sans marque épinglée.
  assert.ok(src.includes('aucun panneau du stock ne correspond'),
    'un catalogue sans panneau doit aussi être refusé, pas expédié muet')
})

test('devis auto : le message de la garde est CELUI du bandeau de DevisGenerator', () => {
  // Verrou de dérive inter-fichiers : le commercial voit la MÊME phrase, qu'il
  // passe par le générateur complet ou par « Devis automatique » de la fiche
  // lead. Les deux fichiers portent le même gabarit, à la lettre.
  const auto = lire('./autoQuote.js')
  const gen = lire('../../pages/ventes/DevisGenerator.jsx')
  const gabarit = 'Marque épinglée introuvable au stock : ${metaMarquesManquantes'
  assert.ok(gen.includes(gabarit), 'gabarit du bandeau introuvable dans DevisGenerator')
  assert.ok(auto.includes('Marque épinglée introuvable au stock : ${marquesAbsentes'))
  const suite = 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.'
  assert.ok(gen.includes(suite) && auto.includes(suite))
  assert.ok(gen.includes('.map(m => `${m.marque} (${roleLabel(m.role)})`).join(\', \')'))
  assert.ok(auto.includes('.map(m => `${m.marque} (${roleLabel(m.role)})`).join(\', \')'))
})

test('devis auto : catalogue complet sans marque épinglée → aucune garde ne se déclenche', () => {
  const rows = autoFillLines(SEEDED, {
    kwp: 14 * 710 / 1000, panelW: 710, nbPanneaux: 14, structureType: 'acier',
  })
  assert.deepEqual(rows.marquesManquantes ?? [], [])
  const pan = rows.find(r => /panneau/i.test(r.designation))
  assert.ok(pan.produit, 'un catalogue complet doit chiffrer les panneaux')
})
