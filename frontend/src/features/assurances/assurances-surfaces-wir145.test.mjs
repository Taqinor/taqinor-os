// WIR145 — surfaces assurances : (a) couverture par actif sur la fiche véhicule,
// (b) exigences par marché + conformité, (c) tableau de bord dédié.
// Vérification de SOURCE (JSX, pas de node_modules dans ce lane).
//   node --test src/features/assurances/assurances-surfaces-wir145.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (...p) => readFileSync(join(HERE, ...p), 'utf8')
const API = read('assurancesApi.js')
const CONFIG = read('module.config.jsx')
const TB = read('TableauBordAssurances.jsx')
const EX = read('ExigencesMarche.jsx')
const VD = read('..', 'flotte', 'VehiculeDetail.jsx')

test('assurancesApi expose les exigences marché (list/create/delete/verifier)', () => {
  assert.match(API, /getExigencesMarche:[\s\S]*?exigences-assurance-marche\//)
  assert.match(API, /createExigenceMarche:/)
  assert.match(API, /deleteExigenceMarche:/)
  assert.match(API, /verifierExigenceMarche:[\s\S]*?\/verifier\//)
})

test('(c) tableau de bord : route + page consommant getTableauBord', () => {
  assert.match(CONFIG, /path: '\/assurances\/tableau-bord', component: TableauBordAssurances/)
  assert.match(TB, /assurancesApi\.getTableauBord\(\)/)
  assert.match(TB, /prime_annuelle_totale/)
  assert.match(TB, /taux_sinistralite/)
})

test('(b) exigences marché : route + page (créer / vérifier conformité / statut)', () => {
  assert.match(CONFIG, /path: '\/assurances\/exigences', component: ExigencesMarche/)
  assert.match(EX, /assurancesApi\.verifierExigenceMarche\(id\)/)
  assert.match(EX, /statut_verification/)
  assert.match(EX, /non_conforme/)
})

test('(a) fiche véhicule : onglet Assurances via getCouvertureActif(VEHICULE, id)', () => {
  assert.match(VD, /<TabsTrigger value="assurances">Assurances<\/TabsTrigger>/)
  assert.match(VD, /assurancesApi\.getCouvertureActif\('VEHICULE', id\)/)
  assert.match(VD, /polices_flotte/)
})

test('les routes statiques sont déclarées avant la route dynamique :id', () => {
  const iTb = CONFIG.indexOf("'/assurances/tableau-bord'")
  const iEx = CONFIG.indexOf("'/assurances/exigences'")
  const iId = CONFIG.indexOf("'/assurances/:id'")
  assert.ok(iTb > 0 && iTb < iId, 'tableau-bord avant :id')
  assert.ok(iEx > 0 && iEx < iId, 'exigences avant :id')
})
