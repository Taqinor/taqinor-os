// PVCBL (fondateur 19/08/2026) — bug constaté (capture d'écran fondateur) :
// un devis auto avait chiffré « Câble solaire 6mm² (100m) » (produit ROULEAU
// de 100 m, 1190 MAD) avec une quantité en MÈTRES (60) → 71 400 MAD
// d'aberration. « who said 100m ????? i wanted cable DC 6mm2 per metre ».
//
// Deux corrections verrouillées ici :
//  1. autoFillLines ne retient JAMAIS un câble DC conditionné en rouleau/
//     touret — seul un produit « au mètre » entre au vivier, même si c'est
//     le seul candidat chiffré (auquel cas la ligne part en placeholder,
//     jamais un repli silencieux) ;
//  2. le métrage suit désormais 60 m × le nombre de PAIRES de MPPT utilisées
//     (30 m rouge + 30 m noir par paire), pas le palier de 5 kWc — passé en
//     paramètre explicite `mpptPaires`, repli fondateur à 1 paire sans lui.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { autoFillLines, metreCableDcParPaires, CABLE_DC_M_PAR_PALIER } from './solar.js'

const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc) => ({ id: ++_id, nom, prix_vente: ht(ttc) })

const BASE = [
  P('Onduleur réseau Huawei 10kW Triphasé', 20000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Structures acier', 500),
  P('Socles', 80),
]

// ── 1. Jamais le rouleau/100m — toujours le produit au mètre ───────────────

test('PVCBL — le câble DC retenu est le produit AU MÈTRE, jamais le rouleau 100m (les deux sont chiffrés)', () => {
  const catalogue = [
    ...BASE,
    P('Câble solaire 6mm² (100m)', 1190),          // le ROULEAU — piège du bug
    P('Câble solaire Nexans 6 mm² (au mètre)', 13), // le bon produit
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier' })
  const cable = rows.find(r => /câble/i.test(r.designation) && !/terre/i.test(r.designation))
  assert.equal(cable.designation, 'Câble solaire Nexans 6 mm² (au mètre)')
  assert.doesNotMatch(cable.designation, /100\s*m/i)
})

test('PVCBL — SEUL un rouleau/100m au catalogue (aucun produit au mètre) : la ligne part en placeholder, JAMAIS un repli sur le rouleau', () => {
  const catalogue = [...BASE, P('Câble solaire 6mm² (100m)', 1190)]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier' })
  const cable = rows.find(r => /câble/i.test(r.designation) && !/terre/i.test(r.designation))
  assert.equal(cable.produit, '')
  assert.equal(cable.prix_unit_ttc, 0)
})

test('PVCBL — le prix TOTAL de la ligne câble avec le rouleau écarté est raisonnable (jamais 71 400 MAD pour un devis résidentiel)', () => {
  const catalogue = [
    ...BASE,
    P('Câble solaire 6mm² (100m)', 1190),
    P('Câble solaire Nexans 6 mm² (au mètre)', 13),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier' })
  const cable = rows.find(r => /câble/i.test(r.designation) && !/terre/i.test(r.designation))
  const total = (parseFloat(cable.quantite) || 0) * (parseFloat(cable.prix_unit_ttc) || 0)
  assert.ok(total < 5000, `total câble DC suspect : ${total} MAD (le bug rendait 71 400 MAD)`)
})

// ── 2. Métrage = 60 m × nb de paires MPPT (repli 1 paire par défaut) ───────

test('metreCableDcParPaires : repli fondateur à 1 paire par défaut (60 m)', () => {
  assert.equal(metreCableDcParPaires(), CABLE_DC_M_PAR_PALIER)
  assert.equal(metreCableDcParPaires(undefined), 60)
})

test('metreCableDcParPaires : proportionnel au nombre de paires transmis', () => {
  assert.equal(metreCableDcParPaires(1), 60)
  assert.equal(metreCableDcParPaires(2), 120)
  assert.equal(metreCableDcParPaires(3), 180)
})

test('metreCableDcParPaires : entrée dégradée (0/négatif/NaN) ne descend jamais sous 1 paire', () => {
  assert.equal(metreCableDcParPaires(0), 60)
  assert.equal(metreCableDcParPaires(-2), 60)
  assert.equal(metreCableDcParPaires(NaN), 60)
})

test('autoFillLines : sans mpptPaires, la quantité câble DC vaut 60 m (repli 1 paire), pas 4× ce montant pour un système à 4 paliers', () => {
  const catalogue = [
    ...BASE,
    P('Câble solaire Nexans 6 mm² (au mètre)', 13),
  ]
  // 28 panneaux × 710 W ≈ 19.9 kWc → 4 paliers de 5 kWc (l'ANCIENNE formule
  // aurait rendu 4 × 60 = 240 m) ; le métrage câble DC ne suit plus les
  // paliers : repli 1 paire = 60 m, quelle que soit la taille du système.
  const kwp = 28 * 710 / 1000
  const rows = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier' })
  const cable = rows.find(r => /câble/i.test(r.designation) && !/terre/i.test(r.designation))
  assert.equal(Number(cable.quantite), 60)
})

test('autoFillLines(mpptPaires) : la quantité câble DC suit EXACTEMENT 60 × mpptPaires quand transmis', () => {
  const catalogue = [
    ...BASE,
    P('Câble solaire Nexans 6 mm² (au mètre)', 13),
  ]
  const kwp = 14 * 710 / 1000
  const rows2 = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier', mpptPaires: 2 })
  const cable2 = rows2.find(r => /câble/i.test(r.designation) && !/terre/i.test(r.designation))
  assert.equal(Number(cable2.quantite), 120)

  const rows3 = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier', mpptPaires: 3 })
  const cable3 = rows3.find(r => /câble/i.test(r.designation) && !/terre/i.test(r.designation))
  assert.equal(Number(cable3.quantite), 180)
})

// ── 3. La quantité n'est qu'une PROPOSITION — l'écran reste éditable ───────
// (le champ Qté de DevisLineRow.jsx est un <Input type="number" step="any">
// standard, câblé sur setLines — aucun effet ne réapplique autoFillLines
// après une frappe manuelle ; voir DevisLineRowReorder.test.mjs pour le
// verrou source de ce champ.)

test('autoFillLines : la ligne câble DC reste un objet PLAT { produit, designation, quantite, prix_unit_ttc, taux_tva } — modifiable comme toute autre ligne', () => {
  const catalogue = [...BASE, P('Câble solaire Nexans 6 mm² (au mètre)', 13)]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier' })
  const cable = rows.find(r => /câble/i.test(r.designation) && !/terre/i.test(r.designation))
  assert.deepEqual(Object.keys(cable).sort(),
    ['designation', 'prix_unit_ttc', 'produit', 'quantite', 'taux_tva'])
})

// ── 4. La classification (réseau/injection, hybride, batterie, panneau) et
// le câble de terre restent INCHANGÉS par ce correctif ──────────────────────

test('PVCBL — le câble de TERRE reste distinct (formule palier inchangée), et lui aussi exige "au mètre"', () => {
  const catalogue = [
    ...BASE,
    P('Câble solaire Nexans 6 mm² (au mètre)', 13),
    P('Câble de terre 6mm² (100m)', 900),
    P('Câble de terre Nexans 6 mm² (au mètre)', 13),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier' })
  const terre = rows.find(r => /câble de terre/i.test(r.designation))
  assert.equal(terre.designation, 'Câble de terre Nexans 6 mm² (au mètre)')
  // Formule palier INCHANGÉE pour la terre : base 25 + 15/palier. 14 panneaux
  // à 710 W ≈ 9.94 kWc → blocks = round(9.94/5) = 2 paliers → 25 + 2×15 = 55.
  assert.equal(Number(terre.quantite), 55)
})
