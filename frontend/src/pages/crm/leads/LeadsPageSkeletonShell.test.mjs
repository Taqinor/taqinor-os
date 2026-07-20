// LB27 — squelette EN FORME dans le shell (blueprint I9) : au premier
// chargement, le header/FilterBar/KPI restent visibles immédiatement — seule
// la zone de vue affiche un squelette qui a la forme de la vue active
// (6 colonnes × 3 SkeletonCard en kanban/prévision, SkeletonTableRow en
// liste), piloté par `useDelayedLoading` (spinner 300ms, squelette 500ms) +
// `FadeSwap` (même pattern que LeadWorkspace.jsx, LW25). Erreur : StateBlock
// plein-page inchangé. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageSkeletonShell.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB27 : plus de retour anticipé plein-page pour le chargement initial', () => {
  assert.doesNotMatch(SRC, /if \(leadsLoading && leads\.length === 0\) \{\s*\n\s*return/)
})

test('LB27 : useDelayedLoading pilote initialLoading (spinner/squelette), placé AVANT le retour error (règle des Hooks)', () => {
  const initIdx = SRC.indexOf('const initialLoading = leadsLoading && leads.length === 0')
  assert.ok(initIdx > 0)
  const hookIdx = SRC.indexOf('const { showSpinner, showSkeleton } = useDelayedLoading(initialLoading)')
  assert.ok(hookIdx > initIdx)
  const errorReturnIdx = SRC.indexOf('if (error) return (')
  assert.ok(hookIdx < errorReturnIdx, 'useDelayedLoading doit précéder le retour anticipé error')
})

test('LB27 : import useDelayedLoading (même hook que ClientList/DevisList/LeadWorkspace)', () => {
  assert.match(SRC, /import \{ useDelayedLoading \} from '\.\.\/\.\.\/\.\.\/hooks\/useDelayedLoading'/)
})

test('LB27 : LeadsViewSkeleton — kanban/prévision = 6 colonnes × 3 SkeletonCard, liste = SkeletonTableRow', () => {
  const start = SRC.indexOf('function LeadsViewSkeleton({ view }) {')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 900)
  assert.match(block, /if \(view === 'liste'\)/)
  assert.match(block, /<SkeletonTableRow key=\{i\} columns=\{7\} \/>/)
  assert.match(block, /Array\.from\(\{ length: 6 \}\)/)
  assert.match(block, /Array\.from\(\{ length: 3 \}\)/)
  assert.match(block, /<SkeletonCard key=\{card\} \/>/)
})

test('LB27 : trois paliers exclusifs — spinner (300-500ms) XOR FadeSwap(squelette↔contenu réel)', () => {
  const spinnerIdx = SRC.indexOf('{showSpinner && (')
  const fadeIdx = SRC.indexOf('{!showSpinner && (')
  assert.ok(spinnerIdx > 0 && fadeIdx > spinnerIdx)
  const block = SRC.slice(fadeIdx, fadeIdx + 300)
  assert.match(block, /<FadeSwap/)
  assert.match(block, /loading=\{showSkeleton\}/)
  assert.match(block, /className="lp-view-skeleton-swap"/)
  assert.match(block, /skeleton=\{<LeadsViewSkeleton view=\{view\} \/>\}/)
})

test('LB27 : le header/FilterBar/KPI restent HORS de la zone de vue (visibles immédiatement, jamais dans le squelette)', () => {
  const kpiIdx = SRC.indexOf('<LeadsKpiStrip')
  const filterBarIdx = SRC.indexOf('<FilterBar')
  const viewAreaIdx = SRC.indexOf('<div className="lp-view-area"')
  assert.ok(kpiIdx > 0 && filterBarIdx > 0 && viewAreaIdx > 0)
  assert.ok(kpiIdx < viewAreaIdx && filterBarIdx < viewAreaIdx)
})

test('LB27 : erreur — StateBlock plein-page INCHANGÉ (aucun rapport avec le squelette)', () => {
  assert.match(SRC, /if \(error\) return \(/)
  assert.match(SRC, /<StateBlock\s*\n\s*error=\{`Erreur : /)
})
