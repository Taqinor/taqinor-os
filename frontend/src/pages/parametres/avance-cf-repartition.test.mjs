// WIR101 — action « Voir la répartition » par champ personnalisé listable
// (AvanceSection.jsx, onglet Paramètres > Avancé). Vérification de SOURCE (JSX,
// pas de node_modules installés dans ce lane — cf. rapports-integrite.test.mjs).
//   node --test src/pages/parametres/avance-cf-repartition.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'AvanceSection.jsx'), 'utf8')
const API = readFileSync(join(HERE, '..', '..', 'api', 'reportingApi.js'), 'utf8')

test('le bouton « Voir la répartition » n’apparaît que sur un champ visible_liste', () => {
  assert.match(SRC, /d\.visible_liste && \(\s*<IconButton[^>]*label="Voir la répartition"/s)
})

test('openCfDist appelle reportingApi.cfGroupBy(cfModule, code)', () => {
  assert.match(SRC, /reportingApi\.cfGroupBy\(cfModule, d\.code\)/)
})

test('l’export xlsx passe par reportingApi.cfGroupByXlsx', () => {
  assert.match(SRC, /reportingApi\.cfGroupByXlsx\(cfModule, cfDist\.code\)/)
  assert.match(API, /cfGroupByXlsx:[\s\S]*?export: 'xlsx'[\s\S]*?responseType: 'blob'/)
})

test('le panneau affiche une table valeur/nombre + un total', () => {
  assert.match(SRC, /Répartition — \{cfDist\.libelle\}/)
  assert.match(SRC, /cfDist\.rows\.map/)
  assert.match(SRC, /cfDist\.total/)
})

test('changer de module ferme le panneau de répartition (état non périmé)', () => {
  assert.match(SRC, /setCfModule\(v\); loadCfDefs\(v\); closeCfDist\(\)/)
})
