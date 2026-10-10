// AGNR45 (C-AGNR-007, jumeau de réouverture) — `devisVersEtat` compte les
// panneaux relus par la règle du kWc facturé (`comptePanneauxOption`, AGNR18 :
// `isPanel` + nom du produit lié), jamais `/panneau/i` sur la désignation.
// Run : node --test src/features/ventes/quote/etatDevis.agnrPanneauxReouverture.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { devisVersEtat } from './etatDevis.js'

const ICI = dirname(fileURLToPath(import.meta.url))
const CAS = JSON.parse(readFileSync(join(ICI,
  '../../../../../backend/django_core/apps/ventes/contract_samples/classification_lignes.json'), 'utf-8'))
  .exemple.cas_ligne_produit

const ligne = (id, designation, quantite, extra = {}) => ({
  id, produit: id, designation, quantite: String(quantite), prix_unitaire: '1000.00',
  taux_tva: '20.00', ordre: id, type_ligne: 'produit', optionnelle: false, variante: '', ...extra,
})
const devis = (lignes) => ({
  id: 1, mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
  etude_params: {}, lignes,
})

test('20 × « JA Solar 550 Wc » + onduleur rouvrent à 20 panneaux (jamais 0)', () => {
  const etat = devisVersEtat(devis([
    ligne(1, 'JA Solar 550 Wc', 20), ligne(2, 'Onduleur réseau Huawei 10 kW', 1),
  ]))
  assert.equal(etat.panneaux, 20)
})

test('une ligne liée à un produit panneau compte, même sans « panneau » dans la désignation', () => {
  const etat = devisVersEtat(devis([ligne(7, 'Modules toiture sud', 12)]),
    { produits: [{ id: 7, nom: 'Panneau Jinko 550W' }] })
  assert.equal(etat.panneaux, 12)
})

test('branche AVEC exclue du compte (comme avant)', () => {
  const etat = devisVersEtat(devis([
    ligne(1, 'Panneau Jinko 550W', 10), ligne(2, 'Panneau Jinko 550W', 2, { variante: 'avec' }),
  ]))
  assert.equal(etat.panneaux, 10)
})

test('contrat AGNR2 : compte = quantité ssi `est_panneau`', () => {
  for (const cas of CAS) {
    const produits = cas.produit_nom ? [{ id: 1, nom: cas.produit_nom }] : []
    const etat = devisVersEtat(devis([ligne(1, cas.designation, 10)]), { produits })
    assert.equal(etat.panneaux, cas.est_panneau ? 10 : 0, cas.designation)
  }
})
