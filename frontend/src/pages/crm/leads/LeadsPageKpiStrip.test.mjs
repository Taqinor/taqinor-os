// LB24 — LeadsPage monte LeadsKpiStrip entre l'en-tête et FilterBar, câblé
// sur le MÊME état `filters`/`setFilters` que le reste de la page (invariant
// D6-I7 : un seul état de filtres). Verified against SOURCE (no node_modules
// in this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageKpiStrip.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB24 : LeadsPage importe LeadsKpiStrip', () => {
  assert.match(PAGE_SRC, /import LeadsKpiStrip from '\.\/LeadsKpiStrip'/)
})

test('LB24→LB43 : FilterBar vit DANS la ligne de contrôle, LeadsKpiStrip juste dessous, câblé sur filters/setFilters/leads', () => {
  const kpiIdx = PAGE_SRC.indexOf('<LeadsKpiStrip')
  const filterBarIdx = PAGE_SRC.indexOf('<FilterBar filters={filters} setFilters={setFilters} leads={leads} />')
  const controlbarIdx = PAGE_SRC.indexOf('lp-controlbar')
  assert.ok(kpiIdx > 0 && filterBarIdx > 0 && controlbarIdx > 0)
  // LB43 (retour fondateur) : la barre recherche/filtres est un ENFANT de la
  // ligne de contrôle unique (façon Odoo) — elle précède donc le bandeau KPI.
  assert.ok(controlbarIdx < filterBarIdx && filterBarIdx < kpiIdx,
    'ordre attendu : lp-controlbar → FilterBar → LeadsKpiStrip')
  const block = PAGE_SRC.slice(kpiIdx, kpiIdx + 700)
  // Critique Fable LB #6→#3 : le bandeau reçoit le pool APRÈS le filtre
  // additif ?equipe= (kpiPool), jamais `leads` brut — sinon les tuiles
  // annoncent des nombres que le clic ne rend pas (« chiffre menteur » D5).
  assert.match(block, /leads=\{kpiPool\}/)
  assert.match(block, /filters=\{filters\}/)
  assert.match(block, /setFilters=\{setFilters\}/)
  assert.match(block, /myUsername=\{currentUser\?\.username\}/)
})

test('LB24 (critique Fable #3) : kpiPool applique le filtre équipe (même règle que `filtered`)', () => {
  const idx = PAGE_SRC.indexOf('const kpiPool = useMemo(')
  assert.ok(idx > 0, 'kpiPool introuvable')
  const block = PAGE_SRC.slice(idx, idx + 300)
  assert.match(block, /if \(!equipeId \|\| !equipeMembreIds\) return leads/)
  assert.match(block, /equipeMembreIds\.has\(l\.owner\)/)
})
