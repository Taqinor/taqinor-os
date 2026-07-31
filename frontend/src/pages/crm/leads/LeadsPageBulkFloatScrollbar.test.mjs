// LB40 — Cosmétique board : (1) la barre bulk flottante ne couvre plus le
// milieu de la scrollbar horizontale du board pendant une sélection, (2) le
// DragOverlay passe AU-DESSUS d'elle pendant un glisser (dnd-kit pose 999 par
// défaut, sous `--z-sticky` = 1100), (3) les radios icône-seule du
// ViewSwitcher exposent enfin un libellé au survol souris (depuis LB32 leur
// nom n'existait qu'en `.sr-only`). Vérifié contre la SOURCE + la feuille de
// style (pas de node_modules dans ce worktree/lane ; le suite frontend de la
// CI est `node --test "src/**/*.test.mjs"`).
//   node --test src/pages/crm/leads/LeadsPageBulkFloatScrollbar.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const CSS = readFileSync(join(HERE, '../../../index.css'), 'utf8')
const KANBAN = readFileSync(join(HERE, 'views/KanbanView.jsx'), 'utf8')
const SWITCHER = readFileSync(join(HERE, 'ViewSwitcher.jsx'), 'utf8')
const SEGMENTED = readFileSync(join(HERE, '../../../ui/Segmented.jsx'), 'utf8')

// La surcharge LB40 est APPEND-ONLY : c'est la DERNIÈRE déclaration
// `.lp-bulk-float { bottom }` qui gagne (cascade, spécificité identique).
function lastBulkFloatBottom(css, { mobile = false } = {}) {
  const marker = mobile
    ? '52px + env(safe-area-inset-bottom) + 12px'
    : 'max(20px, env(safe-area-inset-bottom))'
  const idx = css.lastIndexOf(marker)
  assert.ok(idx > 0, `déclaration bottom introuvable (mobile=${mobile})`)
  return css.slice(idx, idx + 200)
}

test('LB40 : la hauteur de la lane de scrollbar du board est un TOKEN (les deux ne peuvent plus diverger)', () => {
  assert.match(CSS, /--kb-scrollbar-h: 10px;/)
  // Le token vaut exactement la hauteur réellement peinte par le board.
  assert.match(CSS, /\.kb-board::-webkit-scrollbar \{\s*\r?\n\s*height: 10px;/)
})

test('LB40 : la barre bulk est remontée d’une lane de scrollbar (desktop ET mobile)', () => {
  const desktop = lastBulkFloatBottom(CSS)
  assert.match(desktop, /var\(--kb-scrollbar-h\)/)
  assert.match(desktop, /var\(--lp-bulk-float-gap\)/)

  const mobile = lastBulkFloatBottom(CSS, { mobile: true })
  assert.match(mobile, /var\(--kb-scrollbar-h\)/)
  assert.match(mobile, /var\(--lp-bulk-float-gap\)/)
  // La réserve de tabbar mobile (VX42) n'a PAS été perdue au passage.
  assert.match(mobile, /52px \+ env\(safe-area-inset-bottom\) \+ 12px/)
})

test('LB40 : le DragOverlay passe au-dessus de la barre bulk pendant un glisser', () => {
  // Prop native dnd-kit (le calque parent est celui qui empile) — jamais un
  // z-index en dur posé sur notre `.kb-drag-overlay`, qui n'y changerait rien.
  assert.match(KANBAN, /<DragOverlay\s*\r?\n\s*zIndex=\{1200\}/)
  // 1200 > --z-sticky (1100), le palier de `.lp-bulk-float`.
  assert.match(CSS, /\.lp-bulk-float \{[\s\S]{0,400}?z-index: var\(--z-sticky, 1100\);/)
})

test('LB40 : chaque radio du ViewSwitcher porte une infobulle — la MÊME chaîne que son nom accessible', () => {
  assert.match(SWITCHER, /title: label,/)
  assert.match(SWITCHER, /label: <span className="sr-only">\{label\}<\/span>,/)
  // Les 6 vues passent par ce seul `.map` : aucun libellé en double ailleurs.
  assert.equal((SWITCHER.match(/title: label,/g) || []).length, 1)
})

test('LB40 : Segmented relaie `title` sur le bouton radio (ajout purement additif)', () => {
  assert.match(SEGMENTED, /title=\{opt\.title\}/)
  // `options` reste `[{ value, label, icon? }]` pour les autres consommateurs :
  // `title` est optionnel, aucun défaut imposé.
  assert.doesNotMatch(SEGMENTED, /title=\{opt\.title \?\?/)
})
