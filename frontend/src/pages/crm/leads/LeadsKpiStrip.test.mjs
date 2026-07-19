// LB24 — Bandeau KPI = filtres (blueprint D5). Verified against SOURCE (no
// node_modules in this worktree/lane) + la logique PURE réelle de
// filterLeads/STAGE_PROBABILITY (zéro dépendance React, importables tels
// quels).
//   node --test src/pages/crm/leads/LeadsKpiStrip.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { filterLeads, isPerdu, latestDevisTotal } from '../../../features/crm/stages.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadsKpiStrip.jsx'), 'utf8')

test('LB24 : STAGE_PROBABILITY importé depuis KanbanView — jamais une 2e table déclarée', () => {
  assert.match(SRC, /import \{ STAGE_PROBABILITY \} from '\.\/views\/KanbanView'/)
  assert.doesNotMatch(SRC, /const STAGE_PROBABILITY = \{/)
})

test('LB24 : les 3 tuiles filtre sont des <button aria-pressed> (jamais un <a>/<div> cliqué)', () => {
  const matches = [...SRC.matchAll(/aria-pressed=\{(\w+)\}/g)].map((m) => m[1])
  assert.deepEqual(matches, ['dueTodayActive', 'retardActive', 'chaudsActive'])
})

test('LB24 : la tuile Pipeline n’est PAS un bouton (affichage seul, jamais un filtre)', () => {
  const idx = SRC.indexOf('lp-kpi-tile-display')
  assert.ok(idx > 0)
  const before = SRC.slice(Math.max(0, idx - 80), idx)
  assert.match(before, /<div/)
  assert.doesNotMatch(before, /<button/)
})

test('LB24 : toggleRelance/toggleChauds bascule ON→OFF (re-cliquer désactive)', () => {
  assert.match(SRC, /relance: f\.relance === value \? '' : value,/)
  assert.match(SRC, /score: f\.score === 'chaud' \? '' : 'chaud',/)
})

test('LB24 : compte facetté — countWith applique la dimension de la tuile PAR-DESSUS les filtres actifs', () => {
  assert.match(SRC, /const countWith = \(overrides\) => filterLeads\(/)
  assert.match(SRC, /leads, \{ \.\.\.filters, \.\.\.overrides \}, \{ myUsername \},/)
  assert.match(SRC, /countWith\(\{ relance: 'aujourdhui' \}\)/)
  assert.match(SRC, /countWith\(\{ relance: 'retard' \}\)/)
  assert.match(SRC, /countWith\(\{ score: 'chaud' \}\)/)
})

test('LB24 : compte facetté — filterLeads(leads, {…actifs, dimension forcée}) donne EXACTEMENT le nombre promis', () => {
  const leads = [
    { id: 1, stage: 'NEW', relance_date: '2020-01-01' }, // en retard, peu importe l'année de test
    { id: 2, stage: 'NEW', score_label: 'Chaud' },
    { id: 3, stage: 'NEW', canal: 'site_web' },
  ]
  const activeFilters = { canal: 'site_web' }
  // Le compte facetté doit combiner le filtre ACTIF (canal) avec la
  // dimension forcée (score=chaud) — ici aucun lead ne satisfait les DEUX.
  assert.equal(
    filterLeads(leads, { ...activeFilters, score: 'chaud' }).length, 0,
  )
  assert.equal(
    filterLeads(leads, { score: 'chaud' }).length, 1,
  )
})

test('LB24 : Pipeline — pool = filterLeads(leads, filters) SANS override, puis exclusion des perdus', () => {
  const start = SRC.indexOf('const pool = filterLeads(leads, filters, { myUsername }).filter((l) => !isPerdu(l))')
  assert.ok(start > 0, 'calcul du pool Pipeline introuvable ou override non attendu détecté')
})

test('LB24 : Pipeline — brut + pondéré (STAGE_PROBABILITY), un lead perdu ne compte JAMAIS', () => {
  const leads = [
    { id: 1, stage: 'QUOTE_SENT', devis: [{ total_ttc: '10000' }] },
    { id: 2, stage: 'SIGNED', devis: [{ total_ttc: '5000' }], perdu: true },
  ]
  const pool = filterLeads(leads, {}).filter((l) => !isPerdu(l))
  assert.deepEqual(pool.map((l) => l.id), [1])
  const brut = pool.reduce((s, l) => s + latestDevisTotal(l), 0)
  assert.equal(brut, 10000)
})
