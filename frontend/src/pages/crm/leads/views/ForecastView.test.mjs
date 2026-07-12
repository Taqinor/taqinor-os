// XSAL15 — Vue kanban « Prévision » : leads ouverts groupés par mois de
// date_cloture_prevue, total brut + pondéré en tête de colonne (réutilise
// STAGE_PROBABILITY de KanbanView — jamais une 2e table de probabilités),
// glisser une carte PATCHe date_cloture_prevue via onInlineSave existant,
// colonne « Non daté » pour les leads sans date. Verified against SOURCE (no
// node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/views/ForecastView.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ForecastView.jsx'), 'utf8')
const KANBAN_SRC = readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8')
const LEADSPAGE_SRC = readFileSync(join(HERE, '..', 'LeadsPage.jsx'), 'utf8')
const VIEWSWITCHER_SRC = readFileSync(join(HERE, '..', 'ViewSwitcher.jsx'), 'utf8')

test('XSAL15 : ForecastView réutilise STAGE_PROBABILITY de KanbanView (jamais une 2e table)', () => {
  assert.match(SRC, /import \{ STAGE_PROBABILITY \} from '\.\/KanbanView'/)
  assert.match(KANBAN_SRC, /export const STAGE_PROBABILITY = \{/)
  // Aucune redéclaration locale d'une table de probabilités par étape.
  assert.doesNotMatch(SRC, /NEW: 0\.1/)
})

test('XSAL15 : les leads perdus et déjà convertis (SIGNED) sont exclus (« ouverts » seulement)', () => {
  assert.match(SRC, /const isOpenLead = \(lead\) => !isPerdu\(lead\) && lead\?\.stage !== CONVERSION_STAGE/)
})

test('XSAL15 : le regroupement se fait par mois de date_cloture_prevue, avec une colonne Non daté', () => {
  assert.match(SRC, /function monthKey\(dateStr\)/)
  assert.match(SRC, /UNDATED_KEY = 'undated'/)
  assert.match(SRC, /label: 'Non daté'/)
})

test('XSAL15 : chaque colonne calcule total brut + pondéré (même formule que KanbanView : proba × brut)', () => {
  assert.match(SRC, /totalBrut = inMonth\.reduce\(\(s, l\) => s \+ latestDevisTotal\(l\), 0\)/)
  assert.match(SRC, /totalPondere = inMonth\.reduce\(\s*\n?\s*\(s, l\) => s \+ latestDevisTotal\(l\) \* \(STAGE_PROBABILITY\[l\.stage\] \?\? 0\), 0\)/)
})

test('XSAL15 : le drop PATCHe date_cloture_prevue via onInlineSave existant (pas de nouvel endpoint)', () => {
  assert.match(SRC, /onInlineSave\?\.\(lead, 'date_cloture_prevue', `\$\{over\.id\}-01`\)/)
})

test('XSAL15 : « Non daté » n\'est jamais une cible de drop valide', () => {
  assert.match(SRC, /if \(over\.id === UNDATED_KEY\) return/)
})

test('XSAL15 : réutilise @dnd-kit/core déjà installé, aucune nouvelle dépendance', () => {
  assert.match(SRC, /from '@dnd-kit\/core'/)
})

test('XSAL15 : la vue est enregistrée dans ViewSwitcher et LeadsPage (VALID_VIEWS)', () => {
  assert.match(VIEWSWITCHER_SRC, /key: 'prevision', label: 'Vue prévision'/)
  // VX186 — LeadsPage charge ses vues en `lazy()` (le plus gros chunk de route
  // du repo) : ForecastView reste enregistré, via un import dynamique.
  assert.match(LEADSPAGE_SRC, /const ForecastView = lazy\(\(\) => import\('\.\/views\/ForecastView'\)\)/)
  assert.match(LEADSPAGE_SRC, /'kanban', 'liste', 'calendrier', 'graphique', 'carte', 'prevision'/)
  assert.match(LEADSPAGE_SRC, /\{view === 'prevision' && <ForecastView \{\.\.\.viewProps\} \/>\}/)
})
