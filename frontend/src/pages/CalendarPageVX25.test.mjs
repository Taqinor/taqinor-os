// VX25 — MonthGrid partagé + résurrection du calendrier transverse.
// Done = plus aucun hex dans CalendarPage, dark mode correct (tokens
// --module-accent-* déjà déclinés clair/sombre), les deux calendriers
// importent MonthGrid. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/CalendarPageVX25.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const CALENDAR_PAGE = readFileSync(join(HERE, 'CalendarPage.jsx'), 'utf8')
const CALENDAR_VIEW = readFileSync(
  join(HERE, 'crm', 'leads', 'views', 'CalendarView.jsx'), 'utf8',
)
const MONTH_GRID = readFileSync(join(HERE, '..', 'components', 'MonthGrid.jsx'), 'utf8')

// Détecte un hex CSS littéral (#rgb / #rrggbb) hors commentaires — un
// commentaire de code contenant '#' seul (ex. '#42') ne compte pas comme une
// couleur ; on cible spécifiquement le motif hex CSS.
const HEX_COLOR = /#[0-9a-fA-F]{3,8}\b/

test('VX25 : CalendarPage.jsx importe MonthGrid (grille mensuelle partagée)', () => {
  assert.match(CALENDAR_PAGE, /import MonthGrid from '\.\.\/components\/MonthGrid'/)
  assert.match(CALENDAR_PAGE, /<MonthGrid[^]*renderCell=\{renderCell\}/)
})

test('VX25 : CalendarView.jsx (leads) importe MonthGrid également', () => {
  assert.match(
    CALENDAR_VIEW,
    /import MonthGrid, \{ localKey \} from '\.\.\/\.\.\/\.\.\/\.\.\/components\/MonthGrid'/,
  )
})

test('VX25 : CalendarPage.jsx ne code plus aucune couleur hex en dur', () => {
  // On ignore les lignes de commentaire pur (qui peuvent citer un hex
  // historique à titre de contexte) et ne teste que le code exécutable.
  const codeLines = CALENDAR_PAGE
    .split('\n')
    .filter((line) => !line.trim().startsWith('//') && !line.trim().startsWith('*'))
  for (const line of codeLines) {
    assert.ok(!HEX_COLOR.test(line), `hex codé en dur trouvé : ${line.trim()}`)
  }
})

test('VX25 : les 5 types d\'évènement utilisent var(--module-accent-*), jamais un hex', () => {
  assert.match(CALENDAR_PAGE, /--module-accent-azur/)
  assert.match(CALENDAR_PAGE, /--module-accent-success/)
  assert.match(CALENDAR_PAGE, /--module-accent-warning/)
  assert.match(CALENDAR_PAGE, /--module-accent-brass/)
  assert.match(CALENDAR_PAGE, /--module-accent-nuit/)
})

test('VX25 : MonthGrid gère la navigation mois + « Aujourd\'hui »', () => {
  assert.match(MONTH_GRID, /goMonth/)
  assert.match(MONTH_GRID, /goToday/)
  assert.match(MONTH_GRID, /Aujourd&apos;hui/)
})

test('VX25 : plus aucun btn/bouton pré-design-system (btn btn-light) dans CalendarPage', () => {
  assert.doesNotMatch(CALENDAR_PAGE, /className="btn btn-light"/)
})
