// ZSAL4 — Assistant de conversion lead → client (nouveau / lier / aucun).
// Vérification de SOURCE (même convention que SigneDialog.test.mjs — pas de
// node_modules installés dans ce lane, donc pas de rendu React réel ici).
//   node --test src/pages/crm/leads/ConvertirClientDialog.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ConvertirClientDialog.jsx'), 'utf8')
const LEADFORM_SRC = readFileSync(
  join(HERE, '..', 'LeadForm.jsx'), 'utf8')

test('les trois modes ZSAL4 sont proposés : nouveau / lier / aucun', () => {
  assert.match(SRC, /value: 'nouveau'/)
  assert.match(SRC, /value: 'lier'/)
  assert.match(SRC, /value: 'aucun'/)
})

test('mode lier exige un client choisi avant de confirmer (jamais un POST sans client_id)', () => {
  const confirmBody = SRC.slice(
    SRC.indexOf('const confirm = async'), SRC.indexOf('const leadNom'))
  assert.match(confirmBody, /if \(mode === 'lier' && !client\)/)
  assert.match(confirmBody, /payload\.client_id = client\.id/)
})

test('le lookup de conversion ne garde que les hits source=client (jamais un lead/fournisseur comme client_id)', () => {
  assert.match(SRC, /h\.source === 'client'/)
})

test('appelle crmApi.convertirLeadEnClient(leadId, {mode, client_id?})', () => {
  assert.match(SRC, /crmApi\.convertirLeadEnClient\(lead\.id, payload\)/)
})

test('LeadForm : le bouton « Convertir en client » est masqué si le lead a déjà un client', () => {
  assert.match(LEADFORM_SRC, /import ConvertirClientDialog from '\.\/leads\/ConvertirClientDialog'/)
  assert.match(LEADFORM_SRC, /isEdit && !liveLead\?\.client && \(/)
  assert.match(LEADFORM_SRC, /onClick=\{\(\) => setConvertOpen\(true\)\}/)
})

test('LeadForm : la conversion rafraîchit la fiche (refreshLead), pour faire disparaître le bouton', () => {
  assert.match(LEADFORM_SRC, /onConverted=\{refreshLead\}/)
})
