// LB32 — ViewSwitcher rebâti sur `ui/Segmented` (radiogroup + roving tabindex
// + flèches/Home/End au clavier "gratuits") au lieu du role="group" main-roulé
// + SVG bruts d'origine, en CONSERVANT les 6 noms accessibles exacts pinnés
// par le blueprint. + dédup useIsMobile (FilterBar/ListView/ChartsView →
// hook CANONIQUE ui/ResponsiveDialog, plus aucune copie locale verbatim).
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/ViewSwitcherSegmented.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const VS = readFileSync(join(HERE, 'ViewSwitcher.jsx'), 'utf8')
const FB = readFileSync(join(HERE, 'FilterBar.jsx'), 'utf8')
const LV = readFileSync(join(HERE, 'views/ListView.jsx'), 'utf8')
const CV = readFileSync(join(HERE, 'views/ChartsView.jsx'), 'utf8')
const E2E_HELPERS = readFileSync(join(HERE, '../../../../e2e/helpers.js'), 'utf8')

test('LB32 : ViewSwitcher rendu par ui/Segmented (plus de role="group" main-roulé ni de <svg> brut)', () => {
  assert.match(VS, /import \{ Segmented \} from '\.\.\/\.\.\/\.\.\/ui'/)
  assert.match(VS, /<Segmented/)
  assert.doesNotMatch(VS, /role="group"/)
  assert.doesNotMatch(VS, /<svg/)
})

test('LB32 : ViewSwitcher utilise des icônes lucide alignées sur celles de chaque vue', () => {
  assert.match(VS, /import \{ LayoutGrid, List, Calendar, BarChart3, Map, CalendarClock \} from 'lucide-react'/)
})

test('LB32 : les 6 noms accessibles pinnés sont conservés verbatim', () => {
  for (const label of ['Vue kanban', 'Vue liste', 'Vue calendrier', 'Vue graphique', 'Vue carte', 'Vue prévision']) {
    assert.ok(VS.includes(label), `libellé manquant : ${label}`)
  }
})

test('LB32 : useIsMobile importé depuis le hook CANONIQUE, jamais une copie locale (FilterBar n\'en a PLUS besoin — LB43, un seul Popover pour tous les gabarits)', () => {
  assert.doesNotMatch(FB, /useIsMobile/)
  for (const [name, src, depth] of [
    ['ListView.jsx', LV, '../../../../ui/ResponsiveDialog'],
    ['ChartsView.jsx', CV, '../../../../ui/ResponsiveDialog'],
  ]) {
    // Correspondance de chaîne EXACTE (pas de RegExp construite : l'échappement
    // partiel laissait les `.` en jokers — alerte CodeQL js/incomplete-sanitization).
    assert.ok(src.includes(`import { useIsMobile } from '${depth}'`), `${name} : import canonique manquant`)
    assert.match(src, /const isMobile = useIsMobile\(MOBILE_QUERY\)/, `${name} : appel useIsMobile(MOBILE_QUERY) manquant`)
    assert.doesNotMatch(src, /function useIsMobile\(/, `${name} : copie locale résiduelle`)
  }
})

test('LB32 : e2e helpers.js#setLeadsView cible role="radio" (Segmented), pas role="button"', () => {
  const idx = E2E_HELPERS.indexOf('export async function setLeadsView')
  assert.ok(idx > 0)
  const block = E2E_HELPERS.slice(idx, idx + 250)
  assert.match(block, /getByRole\('radio', \{ name: label \}\)/)
  assert.doesNotMatch(block, /getByRole\('button', \{ name: label \}\)/)
})
