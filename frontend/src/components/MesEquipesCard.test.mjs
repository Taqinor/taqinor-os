// ZSAL3 — Carte dashboard « Mes équipes ». Vérification de SOURCE (JSX, pas
// de node_modules installés dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/components/MesEquipesCard.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'MesEquipesCard.jsx'), 'utf8')
const DASHBOARD_SRC = readFileSync(join(HERE, '..', 'pages', 'Dashboard.jsx'), 'utf8')

test('charge via crmApi.getEquipesStatistiques', () => {
  assert.match(SRC, /crmApi\.getEquipesStatistiques\(\)/)
})

test('rend NULL sans équipe, en erreur, ou avant chargement (jamais de carte cassée/vide)', () => {
  assert.match(SRC, /if \(error \|\| equipes == null \|\| equipes\.length === 0\) return null/)
})

test('affiche pipeline ouvert, pondéré, activités en retard et CA signé vs cible', () => {
  assert.match(SRC, /pipeline_ouvert_count/)
  assert.match(SRC, /pipeline_pondere/)
  assert.match(SRC, /activites_en_retard/)
  assert.match(SRC, /ca_signe_mois/)
})

test('Dashboard : monte MesEquipesCard en lazy + Suspense (jamais bloquant)', () => {
  assert.match(DASHBOARD_SRC, /const MesEquipesCard = lazy\(\(\) => import\('\.\.\/components\/MesEquipesCard'\)\)/)
  assert.match(DASHBOARD_SRC, /<MesEquipesCard \/>/)
})
