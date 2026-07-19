// QX31 — Speed-to-lead: first-touch timer on NEW-column kanban cards. LB13 —
// le minuteur FUSIONNE dans la ligne d'action unique : sur une carte NEW non
// contactée, cette ligne EST le badge SLA premier-contact
// (« ⏱ À contacter — il y a 12 min, non contacté »). Il n'apparaît que tant
// que le lead est en étape NEW (l'étape elle-même EST le signal « non
// contacté »). Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/views/LeadCardFirstTouchTimer.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

test('QX31 : minutesDepuis calcule les minutes écoulées depuis une date ISO', () => {
  assert.match(SRC, /const minutesDepuis = \(iso\) => \{/)
  assert.match(SRC, /Math\.floor\(\(Date\.now\(\) - d\.getTime\(\)\) \/ 60000\)/)
})

test('QX31 : formatDepuis produit un libellé FR compact (min/h/j)', () => {
  assert.match(SRC, /const formatDepuis = \(minutes\) => \{/)
  assert.match(SRC, /`il y a \$\{minutes\} min`/)
  assert.match(SRC, /`il y a \$\{heures\} h`/)
  assert.match(SRC, /`il y a \$\{jours\} j`/)
})

test('QX31 : le minuteur n\'est calculé que pour la colonne NEW', () => {
  assert.match(SRC, /const minutesNouveau = lead\.stage === 'NEW' \? minutesDepuis\(lead\.date_creation\) : null/)
})

test('QX31 : le badge SLA « À contacter — …, non contacté » est la ligne d\'action quand minutesNouveau est posé', () => {
  assert.match(SRC, /\) : minutesNouveau != null \? \(/)
  assert.match(SRC, /kb-sla/)
  assert.match(SRC, /À contacter — \{formatDepuis\(minutesNouveau\)\}, non contacté/)
})
