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
import { metreCableDcParPaires, CABLE_DC_M_PAR_PALIER } from './solar.js'

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

// ── 3. La quantité n'est qu'une PROPOSITION — l'écran reste éditable ───────
// (le champ Qté de DevisLineRow.jsx est un <Input type="number" step="any">
// standard, câblé sur setLines — aucun effet ne réapplique autoFillLines
// après une frappe manuelle ; voir DevisLineRowReorder.test.mjs pour le
// verrou source de ce champ.)

// ── 4. La classification (réseau/injection, hybride, batterie, panneau) et
// le câble de terre restent INCHANGÉS par ce correctif ──────────────────────

// ADEV69 — second composeur supprimé (D-QJR5-9) : la composition vit au serveur (apps/ventes/domain/composition.py, testée côté backend).
// Tests retirés (ils ne protégeaient QUE `autoFillLines`) :
//   · PVCBL — le câble DC retenu est le produit AU MÈTRE, jamais le rouleau 100m (les deux sont chiffrés)
//   · PVCBL — SEUL un rouleau/100m au catalogue (aucun produit au mètre) : la ligne part en placeholder, JAMAIS un repli sur le rouleau
//   · PVCBL — le prix TOTAL de la ligne câble avec le rouleau écarté est raisonnable (jamais 71 400 MAD pour un devis résidentiel)
//   · autoFillLines : sans mpptPaires, la quantité câble DC vaut 60 m (repli 1 paire), pas 4× ce montant pour un système à 4 paliers
//   · autoFillLines(mpptPaires) : la quantité câble DC suit EXACTEMENT 60 × mpptPaires quand transmis
//   · autoFillLines : la ligne câble DC reste un objet PLAT { produit, designation, quantite, prix_unit_ttc, taux_tva } — modifiable comme toute autre ligne
//   · PVCBL — le câble de TERRE reste distinct (formule palier inchangée), et lui aussi exige "au mètre"
