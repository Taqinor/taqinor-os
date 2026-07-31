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
// LB22 — VALID_VIEWS a déménagé dans urlFilters.js (source unique).
const URLFILTERS_SRC = readFileSync(join(HERE, '..', 'urlFilters.js'), 'utf8')

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
  // LB28 — le glisser ET le <select> clavier passent désormais par le MÊME
  // point d'entrée `commitDate` (busy-lock partagé) plutôt que d'appeler
  // `onInlineSave` en direct depuis handleDragEnd.
  assert.match(SRC, /onInlineSave\?\.\(lead, 'date_cloture_prevue', `\$\{targetKey\}-01`\)/)
  assert.match(SRC, /commitDate\(lead, over\.id\)/)
})

test('LB28 : KeyboardSensor branché (parité clavier avec KanbanView)', () => {
  assert.match(SRC, /KeyboardSensor/)
  assert.match(SRC, /useSensor\(KeyboardSensor\)/)
})

test('LB28 : annonces FR partagées avec KanbanView (jamais une 2e implémentation)', () => {
  assert.match(SRC, /import \{\s*\n?\s*buildKanbanAnnouncements,\s*\n?\s*kanbanScreenReaderInstructions,\s*\n?\s*\} from '\.\.\/\.\.\/\.\.\/\.\.\/features\/kanban\/kanbanA11y'/)
  assert.match(SRC, /accessibility=\{\{/)
  assert.match(SRC, /screenReaderInstructions: kanbanScreenReaderInstructions/)
})

test('LB28 : équivalent clavier du glisser — un <select> mois par carte via useOptimisticSave (même motif que StageMover)', () => {
  assert.match(SRC, /function MonthMover\(/)
  assert.match(SRC, /useOptimisticSave\(\s*currentKey/)
  assert.match(SRC, /className="form-control fv-month-select"/)
  // « Non daté » n'est JAMAIS offert comme nouvelle cible — seulement quand
  // c'est déjà la valeur courante (carte encore sans date).
  assert.match(SRC, /const options = currentKey === UNDATED_KEY/)
  assert.match(SRC, /\.\.\.monthOptions\]\s*\n\s*: monthOptions/)
})

test('LB28 : options du <select> mois excluent « Non daté » (jamais une cible valide)', () => {
  assert.match(SRC, /monthOptions = useMemo\(/)
  assert.match(SRC, /\.filter\(\(c\) => c\.key !== UNDATED_KEY\)/)
})

test('LB28 : busy-lock réel — verrou local partagé par le glisser ET le select clavier', () => {
  assert.match(SRC, /const \[savingId, setSavingId\] = useState\(null\)/)
  assert.match(SRC, /const commitDate = useCallback\(/)
  assert.match(SRC, /setSavingId\(lead\.id\)/)
  assert.match(SRC, /lead\.id === busyLeadId \|\| lead\.id === savingId/)
})

test('LB28 : listeners de drag isolés sur une poignée (le sélecteur de mois reste hors du conteneur listeners)', () => {
  // Le conteneur `{...listeners} {...attributes}` n'enveloppe QUE LeadCard ;
  // MonthMover est un frère, hors de la poignée (comme StageMover/KanbanView).
  // LB35 — le MÊME nœud porte désormais `data-lead-id` (cible du focus
  // post-drop) ; l'isolation testée ici est inchangée.
  assert.match(SRC, /<div data-lead-id=\{lead\.id\} \{\.\.\.listeners\} \{\.\.\.attributes\}>\s*\n\s*<LeadCard/)
  assert.match(SRC, /<MonthMover lead=\{lead\} monthOptions=\{monthOptions\} onCommitDate=\{onCommitDate\} busy=\{busy\} \/>/)
})

test('LB28 : EmptyState global sur les leads OUVERTS (0 lead ouvert, y compris « tous filtrés/fermés »)', () => {
  assert.match(SRC, /import \{ EmptyState \} from '\.\.\/\.\.\/\.\.\/\.\.\/ui'/)
  assert.match(SRC, /const openCount = columns\.reduce\(\(s, col\) => s \+ col\.leads\.length, 0\)/)
  assert.match(SRC, /if \(openCount === 0\)/)
})

test('LB28 : hint de drop en pointillés par colonne (jamais sur « Non daté »)', () => {
  assert.match(SRC, /fv-col-drop-hint/)
  assert.match(SRC, /col\.key === UNDATED_KEY/)
})

test('XSAL15 : « Non daté » n\'est jamais une cible de drop valide', () => {
  assert.match(SRC, /if \(over\.id === UNDATED_KEY\) return/)
})

test('XSAL15 : réutilise @dnd-kit/core déjà installé, aucune nouvelle dépendance', () => {
  assert.match(SRC, /from '@dnd-kit\/core'/)
})

test('XSAL15 : la vue est enregistrée dans ViewSwitcher et LeadsPage (VALID_VIEWS)', () => {
  // LB32 — ViewSwitcher rebâti sur ui/Segmented : `key` → `value` (contrat
  // `options = [{ value, label, icon }]` de Segmented).
  assert.match(VIEWSWITCHER_SRC, /value: 'prevision', label: 'Vue prévision'/)
  // VX186 — LeadsPage charge ses vues en `lazy()` (le plus gros chunk de route
  // du repo) : ForecastView reste enregistré, via un import dynamique.
  assert.match(LEADSPAGE_SRC, /const ForecastView = lazy\(\(\) => import\('\.\/views\/ForecastView'\)\)/)
  // LB22 — VALID_VIEWS a déménagé dans urlFilters.js (source UNIQUE, réutilisée
  // par l'encodage d'URL) : LeadsPage l'IMPORTE désormais au lieu de la
  // redéclarer localement.
  assert.match(LEADSPAGE_SRC, /import \{\s*\n\s*VALID_VIEWS,/)
  assert.match(URLFILTERS_SRC, /'kanban', 'liste', 'calendrier', 'graphique', 'carte', 'prevision'/)
  assert.match(LEADSPAGE_SRC, /\{view === 'prevision' && <ForecastView \{\.\.\.viewProps\} \/>\}/)
})

// ── LB35 — parité des trois invariants du kanban (memo, focus post-drop, pan).
// Même motif de sonde que LeadsPageMemoStability.test.mjs : assertions sur la
// SOURCE (aucun node_modules dans ce worktree/lane), on verrouille le CONTRAT.

test('LB35 : ForecastView mémoïse DraggableCard (memo(), parité LB6/KanbanView)', () => {
  assert.match(SRC, /const DraggableCard = memo\(function DraggableCard\(/)
  assert.match(SRC, /^import \{ memo, /m)
  // Le composant est bien REFERMÉ sur memo() (`})` et non `}`) — garde-fou
  // explicite contre un demi-fix qui ne compilerait pas.
  const start = SRC.indexOf('const DraggableCard = memo(function DraggableCard(')
  const end = SRC.indexOf('\nfunction MonthColumn(', start)
  assert.ok(start > 0 && end > start, 'DraggableCard introuvable')
  // (\r? — le dépôt est checkouté en CRLF sous Windows.)
  assert.match(SRC.slice(start, end), /\r?\n\}\)\r?\n\r?$/)
})

test('LB35 : `data-lead-id` posé sur le MÊME nœud que `{...listeners} {...attributes}` (motif LB12)', () => {
  assert.match(SRC, /<div data-lead-id=\{lead\.id\} \{\.\.\.listeners\} \{\.\.\.attributes\}>/)
})

test('LB35 : un drop RÉUSSI restaure le focus sur la carte déplacée (souris ET clavier)', () => {
  const start = SRC.indexOf('const handleDragEnd = ')
  const end = SRC.indexOf('const handleDragCancel', start)
  assert.ok(start > 0 && end > start, 'handleDragEnd introuvable')
  const block = SRC.slice(start, end)
  const commitIdx = block.indexOf('commitDate(lead, over.id)')
  assert.ok(commitIdx > 0, 'appel commitDate introuvable')
  const after = block.slice(commitIdx)
  assert.match(after, /requestAnimationFrame\(\(\) => \{/)
  assert.match(after, /document\.querySelector\(`\[data-lead-id="\$\{lead\.id\}"\]`\)\?\.focus\(\)/)
  // La restauration suit les gardes (pas de `over` / drop sur place / « Non
  // daté ») : aucune sortie anticipée ne l'atteint jamais.
  assert.ok(block.indexOf('if (over.id === UNDATED_KEY) return') < commitIdx)
  // Le focus n'est tenté qu'en cas de SUCCÈS (chaîné sur `.then`, jamais
  // avant que le store ait re-parenté la carte — onInlineSave n'est pas
  // optimiste, contrairement au changeStage du kanban).
  assert.match(after, /\.then\(\(\) => \{[\s\S]*requestAnimationFrame/)
  // Un seul handleDragEnd : souris et clavier partagent le même chemin.
  assert.equal((SRC.match(/const handleDragEnd = /g) || []).length, 1)
})

test('LB35 : drag-to-pan via le hook EXISTANT usePanScroll (jamais une 2e implémentation)', () => {
  assert.match(SRC, /import \{ usePanScroll \} from '\.\.\/\.\.\/\.\.\/\.\.\/features\/kanban\/usePanScroll'/)
  assert.match(SRC, /const boardRef = usePanScroll\(\)/)
  // Callback-ref posé sur `.kb-board` (le scrolleur), pas ailleurs.
  assert.match(SRC, /<div className="kb-board fv-board" ref=\{boardRef\}/)
  // Aucun écouteur de pan maison dans la vue.
  assert.doesNotMatch(SRC, /addEventListener\('pointerdown'/)
})
