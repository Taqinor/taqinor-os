// VX157 — pastille d'impact du parc en pied de Sidebar. Vérification de
// SOURCE (pas de node_modules installés dans ce lane — cf.
// MesEquipesCard.test.mjs) :
//   node --test src/components/layout/ImpactPastille.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ImpactPastille.jsx'), 'utf8')
const SIDEBAR_SRC = readFileSync(join(HERE, 'Sidebar.jsx'), 'utf8')

test('charge via monitoringApi.getCo2Fleet (scoping company déjà côté serveur)', () => {
  assert.match(SRC, /monitoringApi\.getCo2Fleet\(\)/)
})

test('rend NULL en erreur ou avant chargement (jamais de pastille cassée)', () => {
  assert.match(SRC, /if \(error \|\| data == null\) return null/)
})

test('rend NULL si le parc n’a aucune donnée réelle — jamais un "0" inventé', () => {
  assert.match(SRC, /if \(productionKwh <= 0 && co2Tonnes <= 0\) return null/)
})

test('affiche les MWh cumulés ET les tonnes de CO₂ évitées', () => {
  assert.match(SRC, /MWh/)
  assert.match(SRC, /CO₂ évitées/)
})

test('utilise l’icône métier unifiée (METRIC_ICONS.co2), pas un import lucide ad hoc', () => {
  assert.match(SRC, /import { METRIC_ICONS } from '\.\.\/\.\.\/ui\/metricIcons'/)
  assert.match(SRC, /const Icon = METRIC_ICONS\.co2/)
  assert.doesNotMatch(SRC, /from 'lucide-react'/)
})

test('Sidebar : monte ImpactPastille en lazy + Suspense (jamais bloquant pour la nav)', () => {
  assert.match(SIDEBAR_SRC, /const ImpactPastille = lazy\(\(\) => import\('\.\/ImpactPastille'\)\)/)
  assert.match(SIDEBAR_SRC, /<ImpactPastille collapsed={collapsed} \/>/)
  assert.match(SIDEBAR_SRC, /<Suspense fallback={null}>/)
})
