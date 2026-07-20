// LB22 — URL partageable (blueprint D5/I7) : LeadsPage.jsx priorise
// URL > localStorage > défauts au premier chargement et réécrit l'URL
// (débouncée 300ms, `replace`) à chaque changement de filtres/vue, via le
// module pur `urlFilters.js`. Verified against SOURCE (no node_modules in
// this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageUrlFilters.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('LB22 : VALID_VIEWS est importé depuis urlFilters.js — jamais une 2e liste déclarée', () => {
  assert.match(
    PAGE_SRC,
    /import \{\s*VALID_VIEWS, hasUrlFilterState, readFiltersFromParams, readViewFromParams,\s*\n\s*writeFiltersToParams,\s*\n\} from '\.\/urlFilters'/,
  )
  assert.doesNotMatch(PAGE_SRC, /const VALID_VIEWS = \[/)
})

test('LB22→LB49 : la vue initiale priorise `?view=` puis la SESSION (sessionStorage — une nouvelle connexion repart sur la vue rang 1 du compte)', () => {
  const start = PAGE_SRC.indexOf('const [view, setView] = useState(() => {')
  assert.ok(start > 0)
  const block = PAGE_SRC.slice(start, start + 400)
  assert.match(block, /const fromUrl = readViewFromParams\(searchParams\)/)
  assert.match(block, /if \(fromUrl\) return fromUrl/)
  assert.match(block, /sessionStorage\.getItem\(VIEW_KEY\)/)
  assert.doesNotMatch(block, /localStorage/)
})

test('LB49 : le défaut de connexion (vue rang 1) ne s\'applique que sans URL et sans session, une seule fois', () => {
  const idx = PAGE_SRC.indexOf('const defaultViewApplied = useRef(false)')
  assert.ok(idx > 0, 'garde defaultViewApplied introuvable')
  const block = PAGE_SRC.slice(idx, idx + 600)
  assert.match(block, /if \(initSource\.url \|\| initSource\.session\) return/)
  assert.match(block, /applySavedView\(savedViews\[0\]\)/)
})

test('LB56 : les 4 priorités tiennent après le refactor picker — URL > session > rang 1 > kanban', () => {
  // 1. URL d'abord (vue).
  const viewInit = PAGE_SRC.slice(PAGE_SRC.indexOf('const [view, setView] = useState(() => {'), PAGE_SRC.indexOf('const [view, setView] = useState(() => {') + 400)
  assert.match(viewInit, /if \(fromUrl\) return fromUrl/)
  // 2. Session ensuite… 4. kanban en dernier recours.
  assert.match(viewInit, /sessionStorage\.getItem\(VIEW_KEY\)/)
  assert.match(viewInit, /return VALID_VIEWS\.includes\(saved\) \? saved : 'kanban'/)
  // 3. Rang 1 gardé par initSource (URL/session gagnent toujours).
  assert.match(PAGE_SRC, /url: !!readViewFromParams\(searchParams\) \|\| hasUrlFilterState\(searchParams\)/)
  // Le picker n'introduit AUCUNE écriture de vue hors applySavedView/setView.
  assert.match(PAGE_SRC, /const applySavedView = useCallback\(\(v\) => \{\s*setActiveViewName\(v\.name\)/)
})

test('LB22 : les filtres initiaux priorisent l’URL (hasUrlFilterState) — jamais un mélange avec localStorage', () => {
  const start = PAGE_SRC.indexOf('const [filters, setFilters] = useState(() => {')
  assert.ok(start > 0)
  const block = PAGE_SRC.slice(start, start + 400)
  assert.match(block, /if \(hasUrlFilterState\(searchParams\)\) return readFiltersFromParams\(searchParams\)/)
})

test('LB22 : écriture d’URL débouncée 300ms, en `replace`, jamais un spam d’historique', () => {
  const idx = PAGE_SRC.indexOf('setSearchParams((prev) => writeFiltersToParams(prev, filters, view), { replace: true })')
  assert.ok(idx > 0, 'écriture URL introuvable')
  const block = PAGE_SRC.slice(Math.max(0, idx - 200), idx + 200)
  assert.match(block, /setTimeout\(\(\) => \{/)
  assert.match(block, /\}, 300\)/)
  assert.match(block, /return \(\) => clearTimeout\(t\)/)
  assert.match(block, /\[filters, view, setSearchParams\]/)
})

test('LB22 : le lien profond `?lead=` reste géré indépendamment (jamais touché par urlFilters)', () => {
  assert.match(PAGE_SRC, /const wantedLeadId = searchParams\.get\('lead'\)/)
})
