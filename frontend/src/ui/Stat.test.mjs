// VX157 — Stat gagne un tone="impact" (accent brass) pour les grandeurs
// d'impact positif. Vérification de SOURCE (pas de node_modules installés
// dans ce lane — cf. MesEquipesCard.test.mjs) :
//   node --test src/ui/Stat.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'Stat.jsx'), 'utf8')
const MODULE_DASHBOARD_SRC = readFileSync(
  join(HERE, 'module', 'ModuleDashboard.jsx'), 'utf8',
)
const CO2_PAGE_SRC = readFileSync(
  join(HERE, '..', 'pages', 'monitoring', 'Co2Page.jsx'), 'utf8',
)
const FLEET_PAGE_SRC = readFileSync(
  join(HERE, '..', 'pages', 'monitoring', 'FleetPage.jsx'), 'utf8',
)

test('Stat accepte une prop tone et applique un accent quand tone==="impact"', () => {
  assert.match(SRC, /tone/)
  assert.match(SRC, /const isImpact = tone === 'impact'/)
})

test('ModuleDashboard transmet tone à <Stat> (les tableaux de bord de module peuvent en profiter)', () => {
  assert.match(MODULE_DASHBOARD_SRC, /tone={s\.tone}/)
})

test('Co2Page : CO₂ évité et production utilisent l’icône métier unifiée + tone impact', () => {
  assert.match(CO2_PAGE_SRC, /icon: METRIC_ICONS\.co2/)
  assert.match(CO2_PAGE_SRC, /icon: METRIC_ICONS\.production/)
  assert.match(CO2_PAGE_SRC, /tone: 'impact'/)
  // Plus d'import ad hoc Leaf/Sprout/Zak — tout passe par metricIcons.js.
  assert.doesNotMatch(CO2_PAGE_SRC, /from 'lucide-react'/)
})

test('FleetPage : kWc et production utilisent l’icône métier unifiée (même symbole que Co2Page)', () => {
  assert.match(FLEET_PAGE_SRC, /icon: METRIC_ICONS\.kwc/)
  assert.match(FLEET_PAGE_SRC, /icon: METRIC_ICONS\.production/)
})
