// SPL210 — tests de calc/classification.js déplacés tel quel de solar.test.mjs (move
// only : aucune assertion modifiée).
//
// Run : node --test src/features/ventes/calc/classification.test.mjs
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  appartientAuPanierAvec, appartientAuPanierSans, isAnyInverter, isHybridInverter,
  isOffgridInverter, isPompe, isReseauInverter, ROLES_DEVIS,
} from './classification.js'
import { optionTotalsTTC } from './totaux.js'

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', '..')
const SERVEUR = join(RACINE, 'backend', 'django_core')

test('QX20 — isPompe classe une pompe, pas un panneau/onduleur', () => {
  assert.equal(isPompe('Pompe immergée OSP 30/8'), true)
  assert.equal(isPompe('Pompe de surface'), true)
  assert.equal(isPompe('Panneau Canadien Solar 710W'), false)
  assert.equal(isPompe('Onduleur réseau Huawei 10kW'), false)
  assert.equal(isPompe(''), false)
})

// ADVS46 (C-ADVS-VER1-110) — le rôle stocké, après la variante, comme le serveur
// (`apps/ventes/utils/options.py::panier_de_ligne`).
test('ADVS46 — le rôle stocké range la ligne', () => {
  const batterie = { designation: 'Dyness BX51100', role_devis: 'batterie', variante: '' }
  assert.equal(appartientAuPanierSans(batterie), false)
  assert.equal(appartientAuPanierAvec(batterie), true)
  const panneau = { designation: 'Panneau 710W', role_devis: 'panneau', variante: '', quantite: '1', prix_unit_ttc: '10000', taux_tva: '20' }
  const avecBatterie = { ...batterie, quantite: '1', prix_unit_ttc: '20000', taux_tva: '20' }
  const seul = optionTotalsTTC([panneau], 0)
  const deux = optionTotalsTTC([panneau, avecBatterie], 0)
  assert.equal(deux.totalSans, seul.totalSans)
  assert.equal(deux.totalAvec, seul.totalAvec + 20000)
})

test('ADVS46 — chaque cas du contrat classement_options.json donne le panier du serveur', () => {
  const contrat = JSON.parse(readFileSync(join(
    SERVEUR, 'apps', 'ventes', 'contract_samples', 'classement_options.json'), 'utf8'))
  assert.ok(contrat.exemple.cas.length > 0)
  for (const cas of contrat.exemple.cas) {
    const { sans, avec, ...ligne } = cas
    assert.equal(appartientAuPanierSans(ligne), sans, `sans : ${JSON.stringify(ligne)}`)
    assert.equal(appartientAuPanierAvec(ligne), avec, `avec : ${JSON.stringify(ligne)}`)
  }
})

test('ADVS46 — un rôle hors vocabulaire retombe sur les mots-clés', () => {
  const l = { designation: 'Batterie Dyness 5 kWh', role_devis: 'pompe', variante: '' }
  assert.equal(appartientAuPanierSans(l), false)
  assert.equal(appartientAuPanierAvec({ designation: 'Onduleur réseau Huawei 5kW', role_devis: 'pompe' }), false)
})

test('ADVS46 — ROLES_DEVIS est le vocabulaire de core/product_roles.py', () => {
  const source = readFileSync(join(SERVEUR, 'core', 'product_roles.py'), 'utf8')
  const bloc = source.match(/^ROLES_DEVIS = \(([\s\S]*?)^\)/m)[1]
  const roles = [...bloc.matchAll(/^\s*(?:'[a-z_]+',?\s*)+/gm)]
    .flatMap(m => [...m[0].matchAll(/'([a-z_]+)'/g)].map(x => x[1]))
  assert.deepEqual([...ROLES_DEVIS], roles)
})

// ADCG45 (D-ADCG-3 = réseau) — un micro-onduleur injecte au réseau, comme
// `solar_classification.py::is_reseau_inverter` (contrat classification_lignes.json).
test('ADCG45 — un micro-onduleur est un onduleur réseau (graphies, exclusions)', () => {
  for (const nom of ['Micro-onduleur 800W', 'MICRO ONDULEUR 800W', 'Microonduleur 600W',
    'micro_onduleur 800W', 'Micro-inverter 800W', 'Micro-ondûleur 800W']) {
    assert.equal(isReseauInverter(nom), true, nom)
    assert.equal(isHybridInverter(nom), false, nom)
    assert.equal(isOffgridInverter(nom), false, nom)
    assert.equal(isAnyInverter(nom), true, nom)
  }
  assert.equal(isReseauInverter('Micro-onduleur hybride 800W'), false)
  assert.equal(isHybridInverter('Micro-onduleur hybride 800W'), true)
  for (const cable of ['Câble micro-onduleur', 'cable micro onduleur 2 m']) {
    assert.equal(isReseauInverter(cable), false, cable)
    assert.equal(isAnyInverter(cable), false, cable)
  }
  assert.equal(isReseauInverter('Micro-onduleur off-grid 800W'), false)
  assert.equal(isOffgridInverter('Micro-onduleur off-grid 800W'), true)
  // Panier : la ligne micro-onduleur va dans « sans », jamais dans « avec ».
  const micro = { designation: 'Micro-onduleur 800W', variante: '' }
  assert.equal(appartientAuPanierSans(micro), true)
  assert.equal(appartientAuPanierAvec(micro), false)
})
