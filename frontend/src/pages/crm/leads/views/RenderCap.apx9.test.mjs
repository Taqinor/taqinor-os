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
  const corps = chargerPlus.slice(0, chargerPlus.indexOf('}, [])'))
  assert.doesNotMatch(corps, /fetch|crmApi|dispatch|await/)
  // Le bouton est une affaire de DESKTOP uniquement : base ET pas valent
  // RENDER_CAP, et la fermeture n'a plus aucune dependance (`}, [])`).
  assert.match(corps, /\(prev\[stageKey\] \?\? RENDER_CAP\) \+ RENDER_CAP/)
  // Idem cote liste.
  assert.match(LISTE, /const chargerPlus = \(\) => setLimiteRendu\(\(n\) => n \+ LIST_RENDER_CAP\)/)
})

test("ordre fondateur 2026-08-01 : au doigt on monte TOUT, le bouton n'existe pas", () => {
  // « pourquoi Charger plus ? mets-les TOUS — l'utilisateur balaie vers le bas
  // de toute facon ». Au pointeur grossier la limite EST la longueur de la
  // colonne : `restants` vaut donc toujours 0 et le bouton n'est jamais rendu
  // (il n'y a plus rien a « charger »). Le plafond tactile a disparu.
  assert.doesNotMatch(KANBAN, /RENDER_CAP_TACTILE/)
  assert.doesNotMatch(KANBAN, /capActif/)
  assert.match(
    KANBAN,
    /const limite = pointerCoarse \? visibles\.length : \(limiteParEtape\[col\.key\] \?\? RENDER_CAP\)/,
  )
  // Rejoue la regle : au doigt, quelle que soit la taille de l'etape, 0 reste.
  const limiteTactile = (n) => n
  for (const n of [0, 1, 10, 41, 300]) {
    assert.equal(Math.max(0, n - limiteTactile(n)), 0)
  }
  // APX9 desktop INCHANGE : le plafond 40 et le bouton restent (6 colonnes
  // visibles en meme temps — le mur de noeuds y est reel).
  assert.match(KANBAN, /export const RENDER_CAP = 40/)
  assert.match(KANBAN, /\{restants > 0 && \(/)
  // L'autre allegement tactile du round 3 reste en place.
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
