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
// views → leads → crm → pages → src/index.css
const CSS = readFileSync(join(HERE, '..', '..', '..', '..', 'index.css'), 'utf8')

// Découpe le corps d'une règle CSS `selecteur {` à partir d'un décalage donné,
// en équilibrant les accolades (les commentaires du bloc n'en contiennent pas).
function corpsDeRegle(css, selecteur, depuis = 0) {
  const debut = css.indexOf(selecteur, depuis)
  if (debut === -1) return null
  const ouvrante = css.indexOf('{', debut)
  let profondeur = 0
  for (let i = ouvrante; i < css.length; i += 1) {
    if (css[i] === '{') profondeur += 1
    else if (css[i] === '}') {
      profondeur -= 1
      if (profondeur === 0) return css.slice(ouvrante + 1, i)
    }
  }
  return null
}

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
  // Classe de bug #43 (sens inverse) : usePanScroll renvoie une FONCTION
  // callback-ref — lire `.current` dessus vaut undefined en silence et le
  // haptique du round 2 etait mort-ne. Le noeud vit sur `.node.current`.
  assert.match(KANBAN, /boardRef\.node\?\.current/)
  assert.doesNotMatch(KANBAN, /boardRef\.current/)
})

test("la colonne mobile ne peut plus devenir un scrolleur horizontal (overflow-x: clip)", () => {
  // ORDRE FONDATEUR 2026-08-01 : « quand je balaie une étape dans Devis
  // envoyé / Relance, je finis par balayer les LEADS dans l'étape ».
  // Cause racine : `overflow-y: auto` sur `.kb-col` fait CALCULER l'axe X en
  // `auto` (spec Overflow niv. 3) — une carte qui déborde d'1 px suffit alors
  // à faire de la colonne un scrolleur horizontal qui vole le geste au pager.
  // Ce test est le cliquet : il rougit si `overflow-x: clip` disparaît.
  // `.kb-col {` existe à plusieurs paliers ; on ancre sur le pager mobile par
  // sa signature exclusive (le board qui claque étape par étape), puis on
  // prend la PREMIÈRE règle `.kb-col` qui suit — c'est la colonne du pager.
  const mobile = CSS.indexOf('scroll-snap-type: x mandatory')
  assert.notEqual(mobile, -1, 'le pager mobile du board a disparu')
  const col = corpsDeRegle(CSS, '.kb-col {', mobile)
  assert.ok(col, '.kb-col introuvable dans le bloc mobile')
  assert.match(col, /scroll-snap-align:\s*start/, "c'est bien la colonne du pager mobile")
  assert.match(col, /overflow-y:\s*auto/, 'la colonne reste le scrolleur vertical du mobile')
  assert.match(col, /overflow-x:\s*clip/)
  // `hidden` crée un vrai conteneur de défilement (donc une cible de geste) :
  // seul `clip` n'en crée aucun. La régression la plus probable est ce
  // remplacement-là — on la nomme.
  assert.doesNotMatch(col, /overflow-x:\s*hidden/)
})

test("le débord est aussi étranglé à la SOURCE, sur les rangées L2/L3 de la carte", () => {
  // Ceinture ET bretelles : sans `min-width: 0`, un flex-item vaut
  // `min-width: auto` (« jamais plus étroit que mon contenu ») — le montant
  // en `white-space: nowrap` poussait la rangée hors de la carte.
  const l2 = corpsDeRegle(CSS, '.kb-card--lead .kb-card-value {')
  assert.ok(l2, 'la rangée L2 (.kb-card-value) a disparu')
  assert.match(l2, /min-width:\s*0/)
  assert.match(l2, /overflow:\s*clip/)
  const montant = corpsDeRegle(CSS, '.kb-card--lead .kb-card-montant {')
  assert.ok(montant, 'le montant L2 a disparu')
  assert.match(montant, /min-width:\s*0/)
  const l3 = corpsDeRegle(CSS, '.kb-card--lead .kb-card-foot {')
  assert.ok(l3, 'la rangée L3 (.kb-card-foot) a disparu')
  assert.match(l3, /min-width:\s*0/)
  assert.match(l3, /overflow:\s*clip/)
})
