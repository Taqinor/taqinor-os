// LB19 — choix de colonnes persisté : vol DIRECT de deux pièces du moteur
// ui/datatable (blueprint D4, zéro fork) — `useColumnPrefs` (persistance
// localStorage) + `ColumnManager`/`columnStateReducer`/`initColumnState`.
// Explicitement PAS `DataTable`/`FilterBuilder`/`urlState` du moteur : un
// seul état de filtres pour toute la page (D5) — cette liste n'en emprunte
// rien d'autre. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/crm/leads/views/ListViewColumnChooser.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ListView.jsx'), 'utf8')

test('LB19 : import direct de useColumnPrefs + ColumnManager/columnStateReducer/initColumnState (zéro fork)', () => {
  assert.match(SRC, /import \{ useColumnPrefs \} from '\.\.\/\.\.\/\.\.\/\.\.\/ui\/datatable\/useColumnPrefs'/)
  assert.match(SRC, /import \{ ColumnManager, columnStateReducer, initColumnState \} from '\.\.\/\.\.\/\.\.\/\.\.\/ui\/datatable'/)
  // PAS le reste du moteur (D4 — refit en place, pas d'adoption complète).
  // Recherche une IMPORTATION précisément (les commentaires nomment ces
  // pièces pour expliquer qu'elles ne sont PAS utilisées ici).
  assert.doesNotMatch(SRC, /import\s*\{[^}]*\bDataTable\b/)
  assert.doesNotMatch(SRC, /import\s*\{[^}]*FilterBuilder/)
  assert.doesNotMatch(SRC, /import\s*\{[^}]*urlState/)
})

test('LB19 : useColumnPrefs(\'leads.columns\') alimente le useReducer(columnStateReducer) — préférences lues UNE FOIS au montage', () => {
  assert.match(SRC, /const \{ initialColumnState, onColumnStateChange \} = useColumnPrefs\('leads\.columns'\)/)
  const start = SRC.indexOf('const [columnState, dispatchColumns] = useReducer(')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 200)
  assert.match(block, /columnStateReducer/)
  assert.match(block, /LIST_COLUMNS/)
  assert.match(block, /\(cols\) => initialColumnState \|\| initColumnState\(cols\)/)
})

test('LB19 : toute mutation de columnState est renvoyée à onColumnStateChange (persistance, contrat NTUX16)', () => {
  assert.match(SRC, /useEffect\(\(\) => \{\s*onColumnStateChange\(columnState\)\s*\}, \[columnState, onColumnStateChange\]\)/)
})

test('LB19 : <ColumnManager> monté dans une barre d\'outils locale HORS de .lv-wrap (reste visible au scroll)', () => {
  const toolbarStart = SRC.indexOf('<div className="lv-toolbar">')
  const wrapStart = SRC.indexOf('<div className="lv-wrap"')
  assert.ok(toolbarStart > 0 && toolbarStart < wrapStart, 'la barre doit précéder .lv-wrap')
  const block = SRC.slice(toolbarStart, wrapStart)
  assert.match(block, /<ColumnManager columns=\{LIST_COLUMNS\} columnState=\{columnState\} dispatch=\{dispatchColumns\} \/>/)
})

test('LB19 : chaque colonne .m-hide (score/telephone/ville/facture/canal/owner/priorite/next_activity/tags) est conditionnée par hiddenCols — en thead ET dans ListRow', () => {
  const hideable = [
    'score', 'telephone', 'ville', 'facture', 'canal', 'owner', 'priorite',
    'next_activity', 'tags',
  ]
  for (const id of hideable) {
    const re = new RegExp(`\\{!hiddenCols\\.${id} &&`)
    const matches = SRC.match(new RegExp(re, 'g')) || []
    assert.ok(
      matches.length >= 2,
      `colonne "${id}" : attendu ≥2 sites conditionnés (thead + ligne), trouvé ${matches.length}`,
    )
  }
  // Colonnes cœur JAMAIS conditionnées (toujours rendues).
  assert.doesNotMatch(SRC, /hiddenCols\.lead\b/)
  assert.doesNotMatch(SRC, /hiddenCols\.stage\b/)
  assert.doesNotMatch(SRC, /hiddenCols\.relance\b/)
  assert.doesNotMatch(SRC, /hiddenCols\.actions\b/)
})

test('LB19 : ListRow reçoit `hiddenCols` (défaut {} — jamais un throw si non fourni)', () => {
  assert.match(SRC, /onDelete, isMobile, onOpenInsights, today, hiddenCols = \{\},/)
  assert.match(SRC, /hiddenCols=\{hiddenCols\}/)
})

test('LB19 : <colgroup> et le colSpan de l\'état vide utilisent la MÊME liste `visibleColumns` (jamais désynchronisés)', () => {
  assert.match(SRC, /const visibleColumns = useMemo\(/)
  assert.match(SRC, /visibleColumns\.map\(\(c\) => <col key=\{c\.id\} style=\{\{ width: c\.width \}\} \/>\)/)
  assert.match(SRC, /colSpan=\{\(onToggleSelect \? 1 : 0\) \+ visibleColumns\.length\}/)
})
