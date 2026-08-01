// APX9 — 500+ leads : plafond de RENDU par colonne + « Charger plus ».
// ----------------------------------------------------------------------------
// L'invariant a proteger n'est pas « il y a un bouton », c'est :
//   - le plafond borne le RENDU, jamais les DONNEES (elles sont deja toutes en
//     memoire : aucun appel reseau ne doit apparaitre ici) ;
//   - les compteurs et sommes d'en-tete restent les totaux REELS (sinon on
//     mentirait sur la taille du pipeline pour une raison purement technique) ;
//   - aucune dependance nouvelle (la virtualisation react-window reste refusee).
//   node --test src/pages/crm/leads/views/RenderCap.apx9.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const KANBAN = lf(readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8'))
const LISTE = lf(readFileSync(join(HERE, 'ListView.jsx'), 'utf8'))
const PKG = JSON.parse(readFileSync(join(HERE, '../../../../../package.json'), 'utf8'))

/* La regle de decoupe, rejouee ici pour la tester sur des volumes reels. */
const RENDER_CAP = 40
const decoupe = (n, palier, clics = 0) => {
  const limite = palier * (1 + clics)
  return { montees: Math.min(n, limite), restants: Math.max(0, n - limite) }
}

test('APX9 (volume) : 500 leads sur 6 etapes -> au plus 6 x 40 cartes montees', () => {
  // Repartition volontairement desequilibree (le cas reel : NEW deborde).
  const parEtape = [300, 90, 50, 30, 20, 10]
  assert.equal(parEtape.reduce((a, b) => a + b, 0), 500)
  const montees = parEtape.map((n) => decoupe(n, RENDER_CAP).montees)
  assert.deepEqual(montees, [40, 40, 40, 30, 20, 10])
  assert.equal(montees.reduce((a, b) => a + b, 0), 180)
  assert.ok(montees.every((m) => m <= RENDER_CAP))
  // Le message annonce le RESTE exact, jamais un total tronque.
  assert.equal(decoupe(300, RENDER_CAP).restants, 260)
  // Un clic ajoute exactement un palier.
  assert.deepEqual(decoupe(300, RENDER_CAP, 1), { montees: 80, restants: 220 })
})

test('APX9 (volume) : une colonne sous le plafond n\'affiche AUCUN bouton', () => {
  assert.deepEqual(decoupe(12, RENDER_CAP), { montees: 12, restants: 0 })
  assert.deepEqual(decoupe(40, RENDER_CAP), { montees: 40, restants: 0 })
  assert.deepEqual(decoupe(41, RENDER_CAP), { montees: 40, restants: 1 })
})

test('APX9 : le plafond kanban est 40 et borne le RENDU', () => {
  assert.match(KANBAN, /export const RENDER_CAP = 40/)
  assert.match(KANBAN, /visibles\.slice\(0, limite\)\.map\(\(lead\) => \(/)
  assert.match(KANBAN, /const restants = Math\.max\(0, visibles\.length - limite\)/)
  assert.match(KANBAN, /\{restants > 0 && \(/)
  assert.match(KANBAN, /Charger plus \(\{restants\} restant\{restants > 1 \? 's' : ''\}\)/)
})

test('APX9 : ZERO appel reseau — « Charger plus » ne fait que decouper la memoire', () => {
  const chargerPlus = KANBAN.slice(KANBAN.indexOf('const chargerPlus = useCallback'))
  const corps = chargerPlus.slice(0, chargerPlus.indexOf('}, [capActif])'))
  assert.doesNotMatch(corps, /fetch|crmApi|dispatch|await/)
  // Audit balayage 2026-08-01 : la BASE depend du pointeur (capActif = 10 au
  // doigt, 40 a la souris) ; le PAS d'extension reste RENDER_CAP.
  assert.match(corps, /\(prev\[stageKey\] \?\? capActif\) \+ RENDER_CAP/)
  // Idem cote liste.
  assert.match(LISTE, /const chargerPlus = \(\) => setLimiteRendu\(\(n\) => n \+ LIST_RENDER_CAP\)/)
})

test('APX9-tactile (audit balayage) : 10 cartes par etape au pointeur grossier', () => {
  // 6×40 cartes montees (~15 000 noeuds) etaient LE poids n°1 du geste : au
  // doigt on monte 10 cartes/etape, et le StageMover (9 noeuds + <select>
  // natif par carte, inatteignable au toucher) n'est plus monte du tout.
  assert.match(KANBAN, /export const RENDER_CAP_TACTILE = 10/)
  assert.match(KANBAN, /const capActif = pointerCoarse \? RENDER_CAP_TACTILE : RENDER_CAP/)
  assert.match(KANBAN, /limiteParEtape\[col\.key\] \?\? capActif/)
  assert.match(KANBAN, /onInlineSave=\{pointerCoarse \? undefined : inlineSaveAvecUndo\}/)
})

test('APX9 : les compteurs et sommes d\'en-tete restent les totaux REELS', () => {
  // Kanban : l'aria-label et la somme lisent `col.count`/`col.totalDevis`,
  // jamais la tranche rendue.
  assert.match(KANBAN, /aria-label=\{`Étape \$\{col\.label\} — \$\{col\.count\} lead/)
  assert.match(KANBAN, /\{formatMAD\(col\.totalDevis\)\} · Prév\./)
  // Liste groupee : les totaux viennent de groupLeadsByStage(sorted), seule la
  // liste de lignes est tranchee.
  assert.match(LISTE, /leads: sorted\.filter\(\(l\) => l\.stage === g\.key\)\.slice\(0, limiteRendu\)/)
  assert.match(LISTE, /<span className="lv-group-count">\{g\.count\}<\/span>/)
})

test('APX9 : la liste borne aussi son rendu, avec son propre palier', () => {
  assert.match(LISTE, /const LIST_RENDER_CAP = 200/)
  assert.match(LISTE, /const rendus = useMemo\(\(\) => sorted\.slice\(0, limiteRendu\), \[sorted, limiteRendu\]\)/)
  assert.match(LISTE, /listGroup !== 'stage' && rendus\.map\(renderRow\)/)
  // Un changement de tri/filtre/groupe repart du premier palier.
  assert.match(LISTE, /useEffect\(\(\) => \{ setLimiteRendu\(LIST_RENDER_CAP\) \}, \[sort, listGroup, leads\]\)/)
})

test('APX9 : « tout selectionner » ne coche jamais des lignes non montees', () => {
  assert.match(LISTE, /const visibleIds = rendus\.map\(\(l\) => l\.id\)/)
})

test('APX9 : AUCUNE dependance nouvelle (virtualisation toujours refusee)', () => {
  const deps = { ...(PKG.dependencies ?? {}), ...(PKG.devDependencies ?? {}) }
  for (const interdite of ['react-window', 'react-virtualized', 'react-virtuoso', '@tanstack/react-virtual']) {
    assert.ok(!(interdite in deps), `dependance de virtualisation introduite : ${interdite}`)
  }
  assert.ok(!('@dnd-kit/sortable' in deps), '@dnd-kit/sortable reste interdit')
})

test('APX9 : le glisser-deposer et les invariants LB41/42 sont intacts', () => {
  assert.match(KANBAN, /<DndContext/)
  assert.match(KANBAN, /autoScroll=\{\{ thresholds: \{ x: 0\.18, y: 0\.22 \} \}\}/)
  assert.match(KANBAN, /isStageMoveAllowed\(lead\.stage, over\.id\)/)
})
