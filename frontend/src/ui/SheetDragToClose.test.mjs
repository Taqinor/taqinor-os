// VX43 — Glisser-vers-le-bas-pour-fermer sur les bottom-sheets (`side="bottom"`)
// de Sheet.jsx, le geste terrain attendu (MaJourneePage/InterventionsPage
// passent maintenant leurs sheets en side="bottom" sous 768px via
// ResponsiveDialog/Sheet directement). Verified against SOURCE (no
// node_modules in this worktree/lane — Sheet.jsx imports 'react' and
// '@radix-ui/react-dialog', neither resolvable here) — same convention as
// LeadCardSwipeAction.test.mjs / DataTableSwipeAction.test.mjs.
//   node --test src/ui/SheetDragToClose.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'Sheet.jsx'), 'utf8')

test('VX43 : le glisser-pour-fermer est réservé à side="bottom" (jamais right/left/top)', () => {
  assert.match(SRC, /const draggable = side === 'bottom'/)
})

test('VX43 : le geste ne s\'arme que vers le BAS (delta > 0), jamais vers le haut', () => {
  assert.match(SRC, /if \(delta <= 0\) \{/)
  // Reparti vers le haut avant toute traîne : le geste est DÉFINITIVEMENT
  // rendu au scroll — il ne redevient pas une fermeture s'il redescend.
  assert.match(SRC, /if \(!dragging\.current\) arme\.current = false/)
})

/* ORDRE FONDATEUR 2026-08-01 — « la fenêtre du lead se ferme quand je balaie
   PENDANT le défilement du contenu ». Le contrat central de ce fichier : le
   geste n'appartient au sheet QUE si plus rien ne peut le consommer. */
test("le geste ne s'arme QUE si tout est déjà en haut, décidé au TOUCHSTART", () => {
  // La décision se prend au poser du doigt et ne se rejuge jamais en cours de
  // geste : un contenu qui atteint son sommet en plein balayage ne doit pas
  // armer la fermeture au milieu du mouvement.
  assert.match(SRC, /arme\.current = !unScrolleurEstDescendu\(e\.target, e\.currentTarget\)/)
  assert.match(SRC, /if \(!arme\.current\) return/)
  // On remonte du nœud touché jusqu'au panneau INCLUS : couvre les écrans qui
  // imbriquent leur PROPRE scrolleur dans le sheet (la fenêtre lead).
  assert.match(SRC, /function unScrolleurEstDescendu\(cible, panneau\) \{/)
  assert.match(SRC, /if \(n\.scrollTop > 0\) return true/)
  assert.match(SRC, /if \(n === panneau\) return false/)
})

test('geste non armé : le sheet ne fait STRICTEMENT rien (aucune translation partielle)', () => {
  const move = SRC.slice(SRC.indexOf('const onTouchMove ='))
  const corps = move.slice(0, move.indexOf('\n  const onTouchEnd'))
  // La toute première ligne du handler sort : aucun setState, aucun transform.
  assert.match(corps, /if \(!draggable \|\| !arme\.current\) return/)
  const avantSortie = corps.slice(0, corps.indexOf('if (!draggable || !arme.current) return'))
  assert.doesNotMatch(avantSortie, /setDragY|setRelache/)
})

test('un lâcher franchit par la DISTANCE ou par la VÉLOCITÉ, et ferme via DialogPrimitive.Close', () => {
  assert.match(SRC, /const DRAG_CLOSE_THRESHOLD = 80/)
  // Sans la vélocité, une chiquenaude courte mais nette — le geste naturel —
  // ne fermait pas : « il ne veut pas se fermer ».
  assert.match(SRC, /const DRAG_CLOSE_VELOCITY = 0\.5/)
  assert.match(SRC, /const DRAG_FLICK_MIN = 24/)
  assert.match(SRC, /const franchi = dragY >= DRAG_CLOSE_THRESHOLD/)
  assert.match(SRC, /\|\| \(dragY >= DRAG_FLICK_MIN && vitesse >= DRAG_CLOSE_VELOCITY\)/)
  assert.match(SRC, /closeRef\.current\?\.click\(\)/)
})

test('traîne 1:1 SANS transition ; transition UNIQUEMENT au relâchement', () => {
  assert.match(SRC, /transform: `translateY\(\$\{dragY\}px\)`, transition: 'none'/)
  assert.match(SRC, /transition: 'transform var\(--motion-base\) var\(--ease-standard\)'/)
  // `--motion-base` vaut 0ms sous prefers-reduced-motion (tokens.css) : la
  // neutralisation du mouvement est automatique, pas un second chemin de code.
  assert.doesNotMatch(SRC, /transition: 'transform \d+ms/)
  // Le style inline ne traîne pas après le geste (un transform, même identité,
  // fait du panneau le bloc conteneur de ses descendants position:fixed).
  assert.match(SRC, /setRelache\(false\)/)
  assert.match(SRC, /e\.propertyName === 'transform'/)
})

test('VX43 : la poignée visuelle n\'apparaît que sur les bottom-sheets', () => {
  assert.match(SRC, /\{draggable && \(/)
  assert.match(SRC, /glisser pour\s*\n?\s*fermer/)
})

test('VX43 : les handlers tactiles sont conditionnés à `draggable` (aucun changement pour right\\/left\\/top)', () => {
  assert.match(SRC, /onTouchStart=\{draggable \? onTouchStart : undefined\}/)
  assert.match(SRC, /onTouchMove=\{draggable \? onTouchMove : undefined\}/)
  assert.match(SRC, /onTouchEnd=\{draggable \? onTouchEnd : undefined\}/)
})

test('VX43 : le clic programmatique fonctionne même quand showClose=false (bouton fermeture masqué mais présent)', () => {
  assert.match(SRC, /\{draggable && !showClose && \(/)
  assert.match(SRC, /<DialogPrimitive\.Close ref=\{closeRef\} className="sr-only"/)
})

test('VX43 : SIDE (right/left/bottom/top) reste inchangé (rétrocompatible)', () => {
  assert.match(SRC, /right: 'inset-y-0 right-0 h-full w-\[min\(26rem,calc\(100%-2rem\)\)\] border-l'/)
  assert.match(SRC, /bottom: 'inset-x-0 bottom-0 max-h-\[85vh\] w-full rounded-t-2xl border-t'/)
})
