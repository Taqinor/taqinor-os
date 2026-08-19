// PVORD (fondateur 19/08/2026) — ordre des lignes de devis.
// Trois garanties demandées par le fondateur :
//   1. ordre PAR DÉFAUT = ordre canonique du simulateur (autoFillLines) ;
//   2. réordonnable manuellement dans l'éditeur (couvert par
//      DevisLineRowReorder.test.mjs, wiring DevisGenerator.jsx) ;
//   3. l'ordre choisi PERSISTE comme nouvel ordre par défaut pour les
//      prochains devis (`ParametresGammes.ordre_lignes`, backend + frontend).
// Ce fichier verrouille `orderLinesByRolePreference` (le tri stable par
// préférence de rôle) et `deriveRoleOrderFromLines` (la dérivation de
// l'écran vers un `ordre_lignes` à enregistrer), plus leur câblage dans
// `autoFillLines`/`defaultProductLines`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  autoFillLines, defaultProductLines, orderLinesByRolePreference,
  deriveRoleOrderFromLines,
} from './solar.js'

const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc) => ({ id: ++_id, nom, prix_vente: ht(ttc) })

const SEEDED = [
  P('Onduleur réseau Huawei 10kW Triphasé', 20000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Batterie Dyness 5 kWh', 17000),
  P('Batterie Dyness 10 kWh', 30000),
  P('Structures acier', 500),
  P('Structures aluminium', 850),
  P('Socles', 80),
  P('Smart Meter', 1800),
  P('Wifi Dongle', 1200),
  P('Câble solaire Nexans 6 mm² (au mètre)', 13),
  P('Câble de terre Nexans 6 mm² (au mètre)', 13),
  P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000),
  P('Installation', 4800),
  P('Transport', 1000),
  P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

// ── 1. orderLinesByRolePreference — la brique de tri pure ──────────────────

test('orderLinesByRolePreference : sans préférence (absente/vide) → ordre canonique inchangé', () => {
  const tagged = [['a', { d: 1 }], ['b', { d: 2 }], ['c', { d: 3 }]]
  assert.deepEqual(orderLinesByRolePreference(tagged, undefined), [{ d: 1 }, { d: 2 }, { d: 3 }])
  assert.deepEqual(orderLinesByRolePreference(tagged, []), [{ d: 1 }, { d: 2 }, { d: 3 }])
  assert.deepEqual(orderLinesByRolePreference(tagged, null), [{ d: 1 }, { d: 2 }, { d: 3 }])
})

test('orderLinesByRolePreference : les rôles préférés passent en tête, dans l\'ordre demandé', () => {
  const tagged = [['a', { n: 'a' }], ['b', { n: 'b' }], ['c', { n: 'c' }]]
  const out = orderLinesByRolePreference(tagged, ['c', 'a'])
  assert.deepEqual(out.map(x => x.n), ['c', 'a', 'b'])
})

test('orderLinesByRolePreference : un rôle absent de la préférence garde son rang canonique, TOUJOURS après les rôles préférés', () => {
  const tagged = [['a', { n: 'a' }], ['b', { n: 'b' }], ['c', { n: 'c' }], ['d', { n: 'd' }]]
  // seul 'c' est préféré → il passe devant ; a/b/d gardent leur ordre relatif d'origine, après.
  const out = orderLinesByRolePreference(tagged, ['c'])
  assert.deepEqual(out.map(x => x.n), ['c', 'a', 'b', 'd'])
})

test('orderLinesByRolePreference : tri STABLE — deux lignes du MÊME rôle préféré gardent leur ordre relatif (batterie 5/10 kWh)', () => {
  const tagged = [
    ['onduleur_reseau', { n: 'onduleur' }],
    ['batterie', { n: 'batterie-5' }],
    ['batterie', { n: 'batterie-10' }],
    ['panneau', { n: 'panneau' }],
  ]
  const out = orderLinesByRolePreference(tagged, ['batterie', 'panneau'])
  assert.deepEqual(out.map(x => x.n), ['batterie-5', 'batterie-10', 'panneau', 'onduleur'])
})

// ── 2. autoFillLines(..., ordreLignes) ──────────────────────────────────────

test('autoFillLines sans ordreLignes : sortie BYTE-IDENTIQUE au comportement historique', () => {
  const kwp = 14 * 710 / 1000
  const opts = { kwp, panelW: 710, structureType: 'acier' }
  const historique = autoFillLines(SEEDED, opts)
  const sansPref = autoFillLines(SEEDED, { ...opts, ordreLignes: undefined })
  const prefVide = autoFillLines(SEEDED, { ...opts, ordreLignes: [] })
  assert.deepEqual(sansPref.map(r => r.designation), historique.map(r => r.designation))
  assert.deepEqual(prefVide.map(r => r.designation), historique.map(r => r.designation))
})

test('autoFillLines(ordreLignes) : le panneau passe en TÊTE quand préféré', () => {
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(SEEDED, {
    kwp, panelW: 710, structureType: 'acier', ordreLignes: ['panneau'],
  })
  assert.match(rows[0].designation, /Panneau/)
})

test('autoFillLines(ordreLignes) : les métadonnées du tableau (kwcReel, nbPanneaux, marquesManquantes…) survivent au réordonnancement', () => {
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(SEEDED, {
    kwp, panelW: 710, structureType: 'acier', ordreLignes: ['panneau', 'batterie'],
  })
  assert.equal(rows.nbPanneaux, 14)
  assert.ok(rows.kwcReel > 0)
  assert.deepEqual(rows.marquesManquantes, [])
  assert.deepEqual(rows.onduleursIncomplets, [])
})

test('autoFillLines(ordreLignes) : le total des quantités/prix ne change PAS — seul l\'ORDRE bouge', () => {
  const kwp = 14 * 710 / 1000
  const opts = { kwp, panelW: 710, structureType: 'acier' }
  const historique = autoFillLines(SEEDED, opts)
  const reordonne = autoFillLines(SEEDED, { ...opts, ordreLignes: ['transport', 'suivi', 'panneau'] })
  const somme = (rows) => rows.reduce(
    (s, r) => s + (parseFloat(r.quantite) || 0) * (parseFloat(r.prix_unit_ttc) || 0), 0)
  assert.equal(somme(reordonne), somme(historique))
  assert.equal(reordonne.length, historique.length)
})

// ── 3. defaultProductLines(..., ordreLignes) ────────────────────────────────

test('defaultProductLines sans ordreLignes : ordre canonique inchangé', () => {
  const historique = defaultProductLines(SEEDED)
  const sansPref = defaultProductLines(SEEDED, [])
  assert.deepEqual(sansPref.map(r => r.designation), historique.map(r => r.designation))
})

test('defaultProductLines(ordreLignes) : « Transport » passe en tête quand préféré', () => {
  const rows = defaultProductLines(SEEDED, ['transport'])
  assert.equal(rows[0].designation, 'Transport')
})

// ── 4. deriveRoleOrderFromLines — dérive l'ordre écran vers ordre_lignes ────

test('deriveRoleOrderFromLines : classe chaque ligne, déduplique (garde la PREMIÈRE occurrence)', () => {
  const lines = [
    { designation: 'Panneau Canadien Solar 710W' },
    { designation: 'Batterie Dyness 5 kWh' },
    { designation: 'Batterie Dyness 10 kWh' },   // même rôle « batterie » → dédupliqué
    { designation: 'Onduleur réseau Huawei 10kW Triphasé' },
  ]
  assert.deepEqual(
    deriveRoleOrderFromLines(lines),
    ['panneau', 'batterie', 'onduleur_reseau'])
})

test('deriveRoleOrderFromLines : distingue structure acier / aluminium (même patron que groupProduitsByCategory)', () => {
  const lines = [
    { designation: 'Structures acier' },
    { designation: 'Structures aluminium' },
  ]
  assert.deepEqual(deriveRoleOrderFromLines(lines), ['structure_acier', 'structure_alu'])
})

test('deriveRoleOrderFromLines : ignore les lignes SANS classification reconnue (section/note/vide) — jamais un rôle inventé', () => {
  const lines = [
    { designation: 'Introduction du projet', typeLigne: 'section' },
    { designation: '' },
    { designation: 'Panneau Canadien Solar 710W' },
  ]
  assert.deepEqual(deriveRoleOrderFromLines(lines), ['panneau'])
})

test('deriveRoleOrderFromLines : round-trip — le résultat est ACCEPTÉ par orderLinesByRolePreference sans erreur', () => {
  const lines = [
    { designation: 'Transport' },
    { designation: 'Panneau Canadien Solar 710W' },
    { designation: 'Onduleur réseau Huawei 10kW Triphasé' },
  ]
  const derived = deriveRoleOrderFromLines(lines)
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(SEEDED, { kwp, panelW: 710, structureType: 'acier', ordreLignes: derived })
  assert.equal(rows[0].designation, 'Transport')
})
