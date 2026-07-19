// LB20 — option « Par étape » : Segmented Plat/Par étape (persisté
// taqinor.leads.listGroup), rangées de groupe collantes tr.lv-group
// (StatusPill étape + compteur + total MAD via groupLeadsByStage — MÊMES
// nombres que le kanban), repliables (état persisté par étape), ordre =
// l'ordre du funnel, tri actif de la liste appliqué DANS chaque groupe.
// tr.lv-row reste le sélecteur des rangées de données dans les DEUX modes
// (contrat e2e). Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/crm/leads/views/ListViewGroupByStage.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ListView.jsx'), 'utf8')
const CSS = readFileSync(join(HERE, '..', '..', '..', '..', 'index.css'), 'utf8')

test('LB20 : Plat/Par étape persisté en localStorage (même patron try/catch que VX240(e), jamais bloquant)', () => {
  assert.match(SRC, /const LIST_GROUP_KEY = 'taqinor\.leads\.listGroup'/)
  assert.match(SRC, /const \[listGroup, setListGroup\] = useState\(lireListGroup\)/)
  assert.match(SRC, /useEffect\(\(\) => \{ ecrireListGroup\(listGroup\) \}, \[listGroup\]\)/)
})

test('LB20 : le repli par groupe est un Set persisté PAR ÉTAPE (survit au reload), jamais throw sans localStorage', () => {
  assert.match(SRC, /const LIST_GROUP_COLLAPSED_KEY = 'taqinor\.leads\.listGroupCollapsed'/)
  assert.match(SRC, /const \[collapsedGroups, setCollapsedGroups\] = useState\(lireGroupesReplies\)/)
  assert.match(SRC, /const toggleGroupCollapsed = useCallback\(\(stageKey\) => \{/)
})

test('LB20 : le Segmented Plat/Par étape est monté dans la barre d\'outils (valeurs "plat"/"stage")', () => {
  const start = SRC.indexOf('<Segmented')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 350)
  assert.match(block, /value: 'plat', label: 'Plat'/)
  assert.match(block, /value: 'stage', label: 'Par étape'/)
  assert.match(block, /value=\{listGroup\}/)
  assert.match(block, /onChange=\{setListGroup\}/)
})

test('LB20 : groupedRows agrège via groupLeadsByStage (MÊMES nombres que le kanban) mais les LIGNES viennent de `sorted` (le tri actif s\'applique DANS chaque groupe)', () => {
  const start = SRC.indexOf('const groupedRows = useMemo(')
  assert.ok(start > 0)
  const block = SRC.slice(start, start + 400)
  assert.match(block, /groupLeadsByStage\(sorted\)/)
  assert.match(block, /leads: sorted\.filter\(\(l\) => l\.stage === g\.key\)/)
})

test('LB20 : les rangées de groupe (tr.lv-group) sont collantes, précédées de leurs lignes tr.lv-row via renderRow — jamais de duplication du JSX de ligne', () => {
  assert.match(SRC, /<tr className="lv-group">/)
  // Une SEULE définition de <ListRow — le mode Plat ET le mode Par étape
  // appellent tous deux `renderRow` (pas de second bloc <ListRow ... />).
  const listRowJsxCount = (SRC.match(/<ListRow$/gm) || []).length
  assert.equal(listRowJsxCount, 1, 'un seul site <ListRow ... /> doit exister (renderRow), pas un par mode')
  assert.match(SRC, /sorted\.map\(renderRow\)/)
  assert.match(SRC, /g\.leads\.map\(renderRow\)/)
})

test('LB20 : chevron labellisé (aria-expanded) + StatusPill étape + compteur + total MAD dans la rangée de groupe', () => {
  const start = SRC.indexOf('<tr className="lv-group">')
  const block = SRC.slice(start, start + 900)
  assert.match(block, /aria-expanded=\{!collapsedGroups\.has\(g\.key\)\}/)
  assert.match(block, /onClick=\{\(\) => toggleGroupCollapsed\(g\.key\)\}/)
  assert.match(block, /<StatusPill status=\{g\.key\} label=\{g\.label\} \/>/)
  assert.match(block, /\{g\.count\}/)
  assert.match(block, /\{formatMAD\(g\.totalDevis\)\}/)
})

test('LB20 : ordre des groupes = ordre du funnel (groupLeadsByStage itère déjà PIPELINE_STAGES dans l\'ordre, aucun tri supplémentaire ici)', () => {
  assert.doesNotMatch(SRC, /groupedRows\.sort/)
})

test('LB20 : index.css pose la rangée de groupe collante avec un offset MESURÉ (--lv-thead-h), pas un pixel deviné en dur', () => {
  assert.match(SRC, /const setH = \(\) => wrapEl\.style\.setProperty\('--lv-thead-h', `\$\{theadEl\.offsetHeight\}px`\)/)
  assert.match(SRC, /new ResizeObserver\(setH\)/)
  assert.match(CSS, /\.lv-table tr\.lv-group td \{[\s\S]*?position: sticky;[\s\S]*?top: var\(--lv-thead-h, 37px\);/)
})

test('LB20 : la cible de repli (.lv-group-toggle) respecte le contrat ≥44px', () => {
  assert.match(CSS, /\.lv-group-toggle \{[\s\S]*?min-height: 44px;/)
})
