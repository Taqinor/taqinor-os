// VX145(c) — Barre « vues enregistrées » partagée. Vérification de SOURCE
// (JSX, pas de node_modules RTL installés dans ce lane — cf. SigneDialog.test.mjs
// / MesEquipesCard.test.mjs pour le même pattern).
//   node --test src/components/SavedViewsBar.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'SavedViewsBar.jsx'), 'utf8')
const LEADS_SRC = readFileSync(
  join(HERE, '..', 'pages', 'crm', 'leads', 'LeadsPage.jsx'), 'utf8',
)
const CLIENTS_SRC = readFileSync(
  join(HERE, '..', 'pages', 'crm', 'ClientList.jsx'), 'utf8',
)

test('SavedViewsBar : rend NULL sans aucune vue enregistrée (0 rangée dédiée)', () => {
  assert.match(SRC, /if \(!savedViews \|\| savedViews\.length === 0\) return null/)
})

test('SavedViewsBar : rend une puce appliquer + supprimer par vue enregistrée', () => {
  assert.match(SRC, /lp-saved-view-chip/)
  assert.match(SRC, /onClick=\{\(\) => onApply\(v\)\}/)
  assert.match(SRC, /onClick=\{\(\) => onDelete\(v\.name\)\}/)
})

test('SaveViewButton : déclencheur exporté séparément, pas de rangée dédiée à lui seul', () => {
  assert.match(SRC, /export function SaveViewButton\(\{ onSave \}\)/)
  assert.match(SRC, /⭐ Enregistrer cette vue/)
})

test('LeadsPage : consomme SavedViewsBar + SaveViewButton (plus de balisage inline dupliqué)', () => {
  assert.match(LEADS_SRC, /import SavedViewsBar, \{ SaveViewButton \} from '\.\.\/\.\.\/\.\.\/components\/SavedViewsBar'/)
  assert.match(LEADS_SRC, /<SaveViewButton onSave=\{saveCurrentView\} \/>/)
  assert.match(LEADS_SRC, /<SavedViewsBar[\s\S]*?onApply=\{applySavedView\}[\s\S]*?onDelete=\{deleteSavedView\}[\s\S]*?\/>/)
  assert.doesNotMatch(LEADS_SRC, /lp-saved-view-chip/)
})

test('ClientList : consomme SavedViewsBar + SaveViewButton (plus de balisage inline dupliqué)', () => {
  assert.match(CLIENTS_SRC, /import SavedViewsBar, \{ SaveViewButton \} from '\.\.\/\.\.\/components\/SavedViewsBar'/)
  assert.match(CLIENTS_SRC, /<SaveViewButton onSave=\{saveCurrentView\} \/>/)
  assert.match(CLIENTS_SRC, /<SavedViewsBar[\s\S]*?onApply=\{applyView\}[\s\S]*?onDelete=\{deleteView\}[\s\S]*?\/>/)
  assert.doesNotMatch(CLIENTS_SRC, /lp-saved-view-chip/)
})

test('LeadsPage : en-tête démote Doublons/Importer/Exporter dans un menu « ⋯ » (DropdownMenu)', () => {
  assert.match(LEADS_SRC, /<DropdownMenu>/)
  assert.match(LEADS_SRC, /onSelect=\{\(\) => setShowDoublons\(true\)\}/)
  assert.match(LEADS_SRC, /onSelect=\{\(\) => setShowImport\(true\)\}/)
  assert.match(LEADS_SRC, /onSelect=\{exportFiltered\}/)
})

test('LeadsPage : en-tête garde + Nouveau lead / Express / ViewSwitcher comme contrôles de premier plan', () => {
  assert.match(LEADS_SRC, /\+ Nouveau lead/)
  // VX45 — l'emoji ⚡ a été remplacé par l'icône lucide <Zap/> ; on garde le
  // contrôle « Express » au premier plan (le libellé, pas l'emoji).
  assert.match(LEADS_SRC, /> Express/)
  assert.match(LEADS_SRC, /<ViewSwitcher view=\{view\} setView=\{setView\} \/>/)
})
