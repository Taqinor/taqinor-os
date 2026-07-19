// VX147 — LeadsPage et ses 4 vues parlent enfin le même langage d'état.
// Vérifié contre la SOURCE (pas de node_modules dans ce worktree/lane, donc
// pas de rendu RTL possible) — même convention que
// `views/ListViewCallReady.test.mjs`.
//   node --test src/pages/crm/leads/LeadsPageVX147EmptyState.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const LEADS_PAGE = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')
const KANBAN = readFileSync(join(HERE, 'views/KanbanView.jsx'), 'utf8')
const LIST = readFileSync(join(HERE, 'views/ListView.jsx'), 'utf8')
const CARTE = readFileSync(join(HERE, 'views/CarteView.jsx'), 'utf8')

test('VX147 : LeadsPage ne rend plus .page-loading/.page-error (StateBlock à la place)', () => {
  assert.doesNotMatch(LEADS_PAGE, /className="page-loading"/)
  assert.doesNotMatch(LEADS_PAGE, /className="page-error"/)
  assert.match(LEADS_PAGE, /import StateBlock from '..\/..\/..\/components\/StateBlock'/)
  assert.match(LEADS_PAGE, /<StateBlock loading loadingText=/)
  assert.match(LEADS_PAGE, /<StateBlock\s*\n\s*error=/)
})

test('VX147 : KanbanView monte EmptyState pour leads=[] au lieu de colonnes vides en texte brut', () => {
  assert.match(KANBAN, /import \{ EmptyState \} from '..\/..\/..\/..\/ui'/)
  assert.match(KANBAN, /if \(!leads \|\| leads\.length === 0\) \{/)
  const idx = KANBAN.indexOf('if (!leads || leads.length === 0)')
  const block = KANBAN.slice(idx, idx + 200)
  assert.match(block, /<EmptyState/)
})

test('VX147 : ListView monte EmptyState pour sorted=[] au lieu du texte brut "Aucun lead à afficher..."', () => {
  assert.match(LIST, /import \{ EmptyState \} from '..\/..\/..\/..\/ui'/)
  assert.doesNotMatch(LIST, />Aucun lead à afficher avec ces filtres\.</)
  const idx = LIST.indexOf('{!sorted.length && (')
  assert.ok(idx > 0)
  // LB19 — la fenêtre a grandi de quelques caractères : colSpan calcule
  // désormais le nombre de colonnes VISIBLES (choix de colonnes persisté)
  // au lieu d'une constante 13/12 en dur.
  const block = LIST.slice(idx, idx + 400)
  assert.match(block, /<EmptyState/)
})

test('VX147 : CarteView monte EmptyState pour leads=[] (distinct du cas "sans GPS" conservé)', () => {
  assert.match(CARTE, /import \{ EmptyState \} from '..\/..\/..\/..\/ui'/)
  assert.match(CARTE, /if \(!leads \|\| leads\.length === 0\) \{/)
  // le bandeau "sans GPS" (leads existants, aucun avec GPS) reste inchangé.
  assert.match(CARTE, /Aucun lead dans cette sélection n'a de coordonnées GPS/)
})
