// AGNR18 (C-AGNR-007) — le kWc « facturé par les lignes » se dérive du watt
// de CHAQUE ligne panneau (`isPanel` sur désignation + nom du produit lié ;
// watt de la fiche / désignation / nom du produit), le `panelW` d'état n'étant
// qu'un repli quand le watt est illisible — comme `panneaux_et_watt_lu` du
// serveur. Avant : `/panneau/i` (20 × « JA Solar 550 Wc » = 0 panneau) et
// `n × panelW` (10 × « Panneau Jinko 550W » à panelW 710 = 7,1 kWc).
//
// Joue les cas compte/watt de `classification_lignes.json` (AGNR2,
// `exemple.cas_ligne_produit` : `est_panneau`, `watt_lu`).
// Run : node --test src/features/ventes/solar.agnrKwcLignes.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { comptePanneauxOption, kwcFactureDesLignes, kwcPanneauxOption } from './solar.js'

const ICI = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(join(ICI,
  '../../../../backend/django_core/apps/ventes/contract_samples/classification_lignes.json'), 'utf-8'))
const CAS = CONTRAT.exemple.cas_ligne_produit

const ligne = (designation, quantite, extra = {}) => ({
  designation, quantite: String(quantite), variante: '', ...extra,
})

test('contrat AGNR2 : chaque cas compte comme panneau ssi `est_panneau`, au watt lu du serveur', () => {
  assert.ok(CAS.length > 0, 'aucun cas_ligne_produit dans le contrat')
  for (const cas of CAS) {
    const produits = cas.produit_nom ? [{ id: 1, nom: cas.produit_nom }] : []
    const lignes = [ligne(cas.designation, 10, cas.produit_nom ? { produit: '1' } : {})]
    assert.equal(comptePanneauxOption(lignes, 'sans', produits), cas.est_panneau ? 10 : 0, cas.designation)
    const kwc = kwcFactureDesLignes(lignes, 710, null, produits)
    if (!cas.est_panneau) assert.equal(kwc, null, cas.designation)
    else if (cas.watt_lu) assert.equal(kwc, 10 * cas.watt_lu / 1000, cas.designation)
  }
})

test('10 × « Panneau Jinko 550W » à panelW 710 = 5,5 kWc (jamais 7,1)', () => {
  assert.equal(kwcFactureDesLignes([ligne('Panneau Jinko 550W', 10)], 710, 9.94), 5.5)
})

test('20 × « JA Solar 550 Wc » = 11,0 kWc (le mot « panneau » n’est pas requis)', () => {
  const lignes = [ligne('JA Solar 550 Wc', 20)]
  assert.equal(comptePanneauxOption(lignes, 'sans'), 20)
  assert.equal(kwcFactureDesLignes(lignes, 710, 9.94), 11)
})

test('une désignation retouchée se lit sur le nom du produit lié', () => {
  const produits = [{ id: 7, nom: 'Panneau Jinko 550W' }]
  const lignes = [ligne('Modules toiture sud', 12, { produit: '7' })]
  assert.equal(comptePanneauxOption(lignes, 'sans', produits), 12)
  assert.equal(kwcFactureDesLignes(lignes, 710, null, produits), 6.6)
})

test('watt illisible : repli sur panelW pour CETTE ligne seulement ; lignes mixtes sommées', () => {
  const lignes = [ligne('Panneau générique', 4), ligne('Panneau Jinko 550W', 10)]
  // 4 × 710 + 10 × 550 = 8 340 W
  assert.equal(kwcFactureDesLignes(lignes, 710, null), 8.34)
})

test('aucune ligne panneau : repli (la cible), jamais un 0 inventé', () => {
  assert.equal(kwcFactureDesLignes([ligne('Onduleur réseau 5kW Monophasé', 1)], 710, 3.2), 3.2)
})

test('branche AVEC : variante « sans » exclue, watt de chaque ligne', () => {
  const lignes = [
    ligne('Panneau Jinko 550W', 10),
    ligne('Panneau Jinko 550W', 2, { variante: 'avec' }),
    ligne('Panneau Jinko 550W', 1, { variante: 'sans' }),
  ]
  assert.equal(kwcPanneauxOption(lignes, 'avec', 710), 6.6)
  assert.equal(kwcPanneauxOption(lignes, 'sans', 710), 6.05)
})
