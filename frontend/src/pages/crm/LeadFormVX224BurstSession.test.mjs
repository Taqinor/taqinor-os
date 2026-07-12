// VX224 — La session de qualification en rafale : ◀▶ prev/next, « créer un
// autre », « Mes leads » par défaut. Verified against SOURCE (no
// node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormVX224BurstSession.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const FORM_SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')
const PAGE_SRC = readFileSync(join(HERE, 'leads/LeadsPage.jsx'), 'utf8')
const STAGES_SRC = readFileSync(join(HERE, '../../features/crm/stages.js'), 'utf8')

test('VX224(b) : « Créer un autre » — persistance + reset via buildInitialFields', () => {
  assert.match(FORM_SRC, /const CREER_UN_AUTRE_KEY = 'taqinor\.leadForm\.creerUnAutre'/)
  assert.match(FORM_SRC, /const \[creerUnAutre, setCreerUnAutre\] = useState/)
  // Le reset réutilise la MÊME fonction que le montage initial (jamais une
  // réinitialisation partielle qui oublierait un défaut VX93).
  assert.match(FORM_SRC, /buildInitialFields\(null, currentUserId\)/)
  assert.match(FORM_SRC, /nomRef\.current\?\.focus\(\)/)
  // Le champ Nom porte le ref consommé par le reset.
  assert.match(FORM_SRC, /<Input id="lf-nom" autoFocus ref=\{nomRef\}/)
})

test('VX224(a) : LeadForm accepte leadsQueue/onNavigateLead et calcule prev/next', () => {
  assert.match(FORM_SRC, /leadsQueue = null, onNavigateLead = null,/)
  assert.match(FORM_SRC, /const queueIndex = /)
  assert.match(FORM_SRC, /const prevInQueue = /)
  assert.match(FORM_SRC, /const nextInQueue = /)
})

test('VX224(a) : garde de saisie (isDirty) avant une navigation ◀▶/J-K', () => {
  assert.match(FORM_SRC, /const isDirty = JSON\.stringify\(fields\) !== cleanFieldsJSON/)
  assert.match(FORM_SRC, /const goToLead = \(target\) => \{/)
  assert.match(FORM_SRC, /Des modifications non enregistrées seront perdues/)
})

test('VX224(a) : raccourcis clavier J\\/K (façon Gmail), jamais en saisie', () => {
  assert.match(FORM_SRC, /import \{ isTypingTarget \} from '\.\.\/\.\.\/providers\/shortcuts'/)
  assert.match(FORM_SRC, /e\.key === 'j' \|\| e\.key === 'J'/)
  assert.match(FORM_SRC, /e\.key === 'k' \|\| e\.key === 'K'/)
})

test('VX224(a) : LeadsPage.jsx passe la liste filtrée EN MÉMOIRE (pas une re-requête)', () => {
  assert.match(PAGE_SRC, /leadsQueue=\{showForm \? filtered : null\}/)
  assert.match(PAGE_SRC, /onNavigateLead=\{showForm \? onOpenLead : null\}/)
})

test('VX224(c) : « Mes leads » ON par défaut pour le rôle normal, jamais écrasé si déjà persisté', () => {
  assert.match(PAGE_SRC, /roleTier === 'normal'/)
  assert.match(PAGE_SRC, /hasPersisted/)
  assert.match(PAGE_SRC, /mesLeads: true/)
  // myUsername résolu depuis Redux, jamais codé en dur.
  assert.match(PAGE_SRC, /myUsername: currentUser\?\.username/)
})

test('VX224(c) : filterLeads (stages.js) expose mesLeads sans casser owner (filtre manager)', () => {
  assert.match(STAGES_SRC, /mesLeads: false,/)
  assert.match(STAGES_SRC, /export function filterLeads\(leads, filters, \{ myUsername \} = \{\}\)/)
  assert.match(STAGES_SRC, /if \(f\.mesLeads && myUsername && \(l\.owner_nom \?\? ''\) !== myUsername\) return false/)
})
