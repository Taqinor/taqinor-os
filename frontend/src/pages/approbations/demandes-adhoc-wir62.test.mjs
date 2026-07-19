// WIR62 — demandes d'approbation ad-hoc (XKB2) : automationApi expose enfin les
// types + demandes, et ApprobationsPage a un onglet « Demandes ad-hoc »
// (définir un type / soumettre / décider). Vérification de SOURCE (JSX, pas de
// node_modules dans ce lane — cf. pages/rapports-integrite.test.mjs).
//   node --test src/pages/approbations/demandes-adhoc-wir62.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const API = readFileSync(join(HERE, '..', '..', 'api', 'automationApi.js'), 'utf8')
const PAGE = readFileSync(join(HERE, 'ApprobationsPage.jsx'), 'utf8')

test('automationApi expose les types de demande (CRUD)', () => {
  assert.match(API, /getApprovalRequestTypes:/)
  assert.match(API, /saveApprovalRequestType:/)
  assert.match(API, /deleteApprovalRequestType:/)
})

test('automationApi expose les demandes + actions (create/approve/reject/demande-info/resoumettre)', () => {
  assert.match(API, /getApprovalRequests:[\s\S]*?approval-requests\//)
  assert.match(API, /createApprovalRequest:/)
  assert.match(API, /approveApprovalRequest:[\s\S]*?\/approve\//)
  assert.match(API, /rejectApprovalRequest:[\s\S]*?\/reject\//)
  assert.match(API, /demandeInfoApprovalRequest:[\s\S]*?demande-info/)
  assert.match(API, /resoumettreApprovalRequest:[\s\S]*?resoumettre/)
})

test('ApprobationsPage ajoute un onglet « Demandes ad-hoc »', () => {
  assert.match(PAGE, /<TabsTrigger value="demandes">Demandes ad-hoc<\/TabsTrigger>/)
  assert.match(PAGE, /<DemandesAdHocTab \/>/)
})

test('l’onglet couvre définir un type, soumettre, et décider', () => {
  assert.match(PAGE, /automationApi\.saveApprovalRequestType\(null,/)
  assert.match(PAGE, /automationApi\.createApprovalRequest\(\{/)
  assert.match(PAGE, /automationApi\.approveApprovalRequest\(id/)
  assert.match(PAGE, /automationApi\.rejectApprovalRequest\(id/)
})
