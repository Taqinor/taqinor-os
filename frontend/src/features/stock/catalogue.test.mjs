// Tests de la taxonomie d'affichage CATÉGORIE → MARQUE → ARTICLES.
// Run with: node --test src/features/stock/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  groupCatalogue, searchCatalogue, keySpec, sansPrix, MARQUE_GENERIQUE,
} from './catalogue.js'
import {
  classifyProduct, isPanel, isBattery, isReseauInverter, isHybridInverter,
} from '../ventes/solar.js'

const CAT = {
  panneaux: { nom: 'Panneaux photovoltaïques', ordre: 10 },
  reseau: { nom: 'Onduleurs réseau', ordre: 20 },
  hybrides: { nom: 'Onduleurs hybrides', ordre: 30 },
  variateurs: { nom: 'Variateurs', ordre: 90 },
  pompes: { nom: 'Pompes', ordre: 80 },
  services: { nom: 'Services & prestations', ordre: 100 },
}

const FIXTURE = [
  { id: 1, nom: 'Panneau Canadien Solar 710W', marque: 'Canadien Solar', prix_vente: '1272.73', tva: '10.00', categorie: CAT.panneaux },
  { id: 2, nom: 'Panneau Jinko 710W', marque: 'Jinko', prix_vente: '1272.73', tva: '10.00', categorie: CAT.panneaux },
  { id: 3, nom: 'Onduleur réseau Huawei 10kW Triphasé', marque: 'Huawei', prix_vente: '16666.67', tva: '20.00', categorie: CAT.reseau },
  { id: 4, nom: 'Onduleur hybride Deye 5kW Monophasé', marque: 'Deye', prix_vente: '14166.67', tva: '20.00', categorie: CAT.hybrides },
  { id: 5, nom: 'VARIATEUR VEICHI SI23 7.5KW 380V', marque: 'VEICHI', prix_vente: '3333.33', tva: '20.00', pompe_kw: '7.5', tension_v: 380, categorie: CAT.variateurs },
  { id: 6, nom: 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)', marque: 'OSP', prix_vente: '0.00', tva: '20.00', pompe_cv: '10', hmt_m: '91', courbe_pompe: { debits_m3h: [0, 12], hmt_m: [91, 85] }, categorie: CAT.pompes },
  { id: 7, nom: 'Installation', marque: '', prix_vente: '4000', tva: '20.00', categorie: CAT.services },
  { id: 8, nom: 'Transport', marque: '', prix_vente: '833.33', tva: '20.00', categorie: CAT.services },
]

test('groupement : catégories dans l\'ordre délibéré, hybrides ≠ réseau', () => {
  const g = groupCatalogue(FIXTURE)
  const noms = g.map(c => c.nom)
  assert.deepEqual(noms, [
    'Panneaux photovoltaïques', 'Onduleurs réseau', 'Onduleurs hybrides',
    'Pompes', 'Variateurs', 'Services & prestations',
  ])
  // marques sous chaque catégorie ; sans-marque → Génériques en dernier
  const services = g.find(c => c.nom === 'Services & prestations')
  assert.equal(services.brands.length, 1)
  assert.equal(services.brands[0].marque, MARQUE_GENERIQUE)
  assert.equal(services.brands[0].items.length, 2)
})

test('recherche transverse : trouve par nom, marque, catégorie et spec', () => {
  assert.equal(searchCatalogue(FIXTURE, 'veichi').length, 1)
  assert.equal(searchCatalogue(FIXTURE, 'hybride').length, 1)
  assert.equal(searchCatalogue(FIXTURE, 'panneaux photo').length, 2) // catégorie
  assert.equal(searchCatalogue(FIXTURE, '710')[0].id, 1)            // nom
  assert.ok(searchCatalogue(FIXTURE, '7.5 kW').some(p => p.id === 5)) // spec
  assert.equal(searchCatalogue(FIXTURE, '').length, FIXTURE.length)
})

test('spec clé par catégorie : Wc, kW+tension, CV/HMT/courbe', () => {
  assert.equal(keySpec(FIXTURE[0]), '710 Wc')
  assert.equal(keySpec(FIXTURE[4]), '7.5 kW · 380 V')
  assert.ok(keySpec(FIXTURE[5]).includes('10 CV'))
  assert.ok(keySpec(FIXTURE[5]).includes('courbe constructeur'))
  assert.equal(keySpec(FIXTURE[6]), null) // service : pas de spec inventée
})

test('prix vide : signalé, jamais sélectionnable comme produit chiffrable', () => {
  assert.equal(sansPrix(FIXTURE[5]), true)   // OSP à prix vide
  assert.equal(sansPrix(FIXTURE[0]), false)
})

// ── 762 — cohérence des familles : affichage catalogue ↔ classification PDF/
// auto-fill. Le moteur PDF (quote_engine/builder.py) et l'auto-fill (solar.js)
// partagent les MÊMES mots-clés de désignation (réseau/injection, hybride,
// batterie, panneau) — vérifié par ailleurs côté ventes. Ici on garantit que la
// taxonomie catalogue (catégorie réelle + keySpec) classe ces familles de la
// même manière que solar.js, pour qu'un article affiché sous « Panneaux » soit
// bien traité comme un panneau par le PDF, etc.
// Mots-clés canoniques de builder.py (_is_panel/_is_battery/_is_reseau_inverter/
// _is_hybrid_inverter), repris à l'identique par solar.js.
const FAMILLES = [
  {
    cat: 'Panneaux photovoltaïques', nom: 'Panneau Jinko 710W',
    classe: 'panneau', predicat: isPanel,
  },
  {
    cat: 'Onduleurs réseau', nom: 'Onduleur réseau Huawei 10kW Triphasé',
    classe: 'onduleur_reseau', predicat: isReseauInverter,
  },
  {
    cat: 'Onduleurs hybrides', nom: 'Onduleur hybride Deye 5kW Monophasé',
    classe: 'onduleur_hybride', predicat: isHybridInverter,
  },
  {
    cat: 'Batteries', nom: 'Batterie Pylontech 5kWh',
    classe: 'batterie', predicat: isBattery,
  },
]

test('762 — familles catalogue alignées sur la classification solar.js/builder.py', () => {
  for (const f of FAMILLES) {
    // solar.js classe la désignation dans la bonne famille…
    assert.equal(classifyProduct(f.nom), f.classe, `classifyProduct(${f.nom})`)
    // …et le prédicat de désignation (mêmes mots-clés que builder.py) répond oui.
    assert.equal(f.predicat(f.nom), true, `predicat ${f.classe}(${f.nom})`)
    // La taxonomie catalogue produit bien une spec pour ces familles (l'article
    // est reconnu, pas relégué dans « Autres » sans spec).
    const p = { nom: f.nom, categorie: { nom: f.cat, ordre: 10 } }
    assert.notEqual(keySpec(p), null, `keySpec famille ${f.classe}`)
  }
})

test('762 — exclusivité : un onduleur réseau n\'est ni hybride ni batterie', () => {
  const reseau = 'Onduleur réseau Huawei 10kW Triphasé'
  assert.equal(isReseauInverter(reseau), true)
  assert.equal(isHybridInverter(reseau), false)
  assert.equal(isBattery(reseau), false)
  assert.equal(isPanel(reseau), false)
})
