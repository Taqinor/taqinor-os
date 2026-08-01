// GESTES PURS (retour fondateur 2026-08-01, « make the sweep the most pleasant
// possible ») — ce fichier gardait le swipe-to-action VX43/LB17 de LeadCard.
// Le swipe est RETIRÉ : sa bande ☎/💬 doublonnait la rangée .kb-quick (44px,
// APX7) et son onTouchMove disputait le balayage horizontal au PAGER de
// colonnes (LB42) — la cause du « leads collants » du retour fondateur.
// Ce test est désormais le CONTRAT DE PURETÉ des gestes : il rougit si un
// futur changement re-pose un gestionnaire de déplacement tactile sur la
// carte. (Même convention source-grep que LeadCardFirstTouchTimer.test.mjs —
// pas de node_modules dans les lanes worktree.)
//   node --test src/pages/crm/leads/views/LeadCardSwipeAction.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')
const KANBAN = readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8')

test('gestes purs : plus AUCUN gestionnaire de déplacement tactile sur la carte', () => {
  // Le drag-follow (onTouchMove) est la seule primitive capable de disputer
  // un geste au navigateur — c'est elle qui est bannie. Les stopPropagation
  // de touchstart (checkbox LB17) ne déplacent rien : tolérés.
  assert.doesNotMatch(SRC, /onTouchMove/)
  assert.doesNotMatch(SRC, /useSwipeReveal|resolveAxisLock|clampSwipeOffset|resolveSwipeSnap/)
  assert.doesNotMatch(SRC, /kb-swipe/)
  // Aucune traînée inline : la carte au repos ne porte ni translateX ni
  // transition transform pilotés par le doigt.
  assert.doesNotMatch(SRC, /translateX\(\$\{/)
  // La décision est documentée à l'endroit même où le swipe vivait.
  assert.match(SRC, /GESTES PURS/)
})

test("les actions que le swipe révélait restent à UN geste sur la carte (rangée .kb-quick)", () => {
  assert.match(SRC, /kb-quick-tel/)
  assert.match(SRC, /kb-quick-wa/)
  // Et le nudge « noter l'appel » reste armé depuis la rangée visible.
  assert.match(SRC, /armCallNudge/)
})

test('le drag souris reste MouseSensor (jamais PointerSensor : il capture aussi le doigt)', () => {
  // PointerSensor (pointer events) réagit AUSSI au toucher : distance 6px
  // suffisait à soulever la carte au début d'un balayage — le « collant »
  // résiduel. MouseSensor n'écoute que la souris ; le doigt n'a de drag
  // qu'en mode déplacement (TouchSensor conditionnel).
  assert.match(KANBAN, /useSensor\(MouseSensor/)
  assert.doesNotMatch(KANBAN, /useSensor\(PointerSensor/)
})

test('le pager mobile claque net et le retour haptique de pose est défensif', () => {
  // Le claquement CSS (mandatory + snap-stop) est gardé par les specs board ;
  // ici on épingle le retour haptique de pose (scrollend, passif, défensif).
  assert.match(KANBAN, /scrollend/)
  assert.match(KANBAN, /navigator\.vibrate\?\.\(5\)/)
  assert.match(KANBAN, /passive: true/)
})
