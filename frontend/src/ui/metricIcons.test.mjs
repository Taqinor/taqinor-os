// VX157 — vocabulaire d'icône unifié pour les grandeurs métier. Vérification
// de SOURCE (pas de node_modules installés dans ce lane — cf.
// MesEquipesCard.test.mjs) :
//   node --test src/ui/metricIcons.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'metricIcons.js'), 'utf8')

test('associe chaque grandeur métier à une icône lucide fixe', () => {
  assert.match(SRC, /production:\s*Sun/)
  assert.match(SRC, /kwc:\s*Zap/)
  assert.match(SRC, /co2:\s*Leaf/)
  assert.match(SRC, /economies:\s*Wallet/)
  assert.match(SRC, /chantier:\s*HardHat/)
})

test('les 5 grandeurs métier ont chacune une icône lucide DISTINCTE (pas de collision visuelle)', () => {
  const matches = [...SRC.matchAll(/^\s*(production|kwc|co2|economies|chantier):\s*(\w+),/gm)]
  assert.equal(matches.length, 5)
  const icons = matches.map((m) => m[2])
  assert.equal(new Set(icons).size, icons.length)
})

test('getMetricIcon() est le seul accès prévu à une icône par clé (pas de valeur par défaut inventée)', () => {
  assert.match(SRC, /export function getMetricIcon\(key\)/)
  assert.match(SRC, /return METRIC_ICONS\[key\]/)
})
