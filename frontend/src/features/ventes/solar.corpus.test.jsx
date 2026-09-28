// QAH3 (docs/PLAN.md, GROUPE QAH) — GARDE DE RÉGRESSION ÉCRAN du corpus figé
// PACT10 partagé avec le jumeau Python (`test_solar_differential.py`).
//
// CE QUE CE FICHIER PROTÈGE. `frontend/scripts/solar_corpus.mjs` a généré UNE
// FOIS ~200 entrées de devis (`solar_corpus.json`) et ce que `solar.js`
// calcule dessus (`solar_corpus_expected.json`, la fonction
// `computeExpectedForEntry` exportée par le générateur). Ce test RECALCULE
// avec la MÊME fonction et exige l'égalité EXACTE avec le fichier committé —
// si `solar.js` change de comportement demain sans que quelqu'un régénère le
// contrat, CE test devient rouge ici, avant que le jumeau Python ne le
// constate comme une fausse divergence inter-langage. Voir l'en-tête de
// `solar_corpus.mjs` pour la portée exacte de la comparaison (classification,
// kWc dérivé des lignes, productible/production PVGIS, totaux TTC) et ce qui
// est explicitement HORS PÉRIMÈTRE (pompe/débit/HMT — builder.py ne les
// recalcule pas, comparer reviendrait à comparer solar.js à lui-même).
//
// RÉGÉNÉRATION (PACT10) — `solar_corpus.json`/`solar_corpus_expected.json` ne
// se régénèrent QUE par un humain qui a tranché une divergence (jamais un
// agent pour repasser ce test au vert) : `node frontend/scripts/solar_corpus.mjs`
// puis relire le diff des deux fichiers.
//
// Run : `npm run test:unit -- src/features/ventes/solar.corpus.test.jsx`
import { describe, test, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { computeExpectedForEntry } from '../../../scripts/solar_corpus.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const FIXTURES_DIR = join(
  HERE, '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'ventes',
  'tests', 'fixtures')
const CORPUS_PATH = join(FIXTURES_DIR, 'solar_corpus.json')
const EXPECTED_PATH = join(FIXTURES_DIR, 'solar_corpus_expected.json')

const CORPUS = JSON.parse(readFileSync(CORPUS_PATH, 'utf8'))
const EXPECTED = JSON.parse(readFileSync(EXPECTED_PATH, 'utf8'))

describe('QAH3 — corpus figé solar_corpus.json (contrat PACT10)', () => {
  test('le corpus et le fichier attendu sont alignés (mêmes ids, même compte)', () => {
    expect(CORPUS.entries.length).toBeGreaterThanOrEqual(150)
    expect(CORPUS.entries.length).toBe(EXPECTED.entries.length)
    expect(CORPUS.entries.map((e) => e.id)).toEqual(EXPECTED.entries.map((e) => e.id))
  })

  test('les trois marchés (résidentiel / industriel-commercial / agricole-pompage) sont couverts', () => {
    const marches = new Set(CORPUS.entries.map((e) => e.marche))
    expect(marches.has('residentiel')).toBe(true)
    expect(marches.has('industriel_commercial')).toBe(true)
    expect(marches.has('agricole_pompage')).toBe(true)
  })

  // Un test par entrée : recalcule avec `computeExpectedForEntry` (la MÊME
  // fonction que le générateur) et compare au bloc committé. Un `subTest`
  // implicite par entrée (describe.each) nomme l'id qui diverge.
  const byId = new Map(EXPECTED.entries.map((e) => [e.id, e]))

  test.each(CORPUS.entries)('recalcul $id == fichier attendu committé', (entry) => {
    const recompute = computeExpectedForEntry(entry)
    const attendu = byId.get(entry.id)
    expect(attendu).toBeDefined()
    expect(recompute).toEqual(attendu)
  })
})
