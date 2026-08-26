// WIR229/FG33 — panneau « WhatsApp en masse » (BulkActionBar/LeadsPage) :
// choix du modèle, `prepare_whatsapp` en masse, file de liens wa.me ouverts
// un par un (jamais un envoi automatique). Vérifié contre la SOURCE (pas de
// node_modules dans ce worktree/lane, patron VX95ForgivenessKanbanArchive) :
//   node --test src/pages/crm/leads/WIR229_bulk_whatsapp.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const BULK_BAR = readFileSync(join(HERE, 'BulkActionBar.jsx'), 'utf8')
const LEADS_PAGE = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('BulkActionBar : le panneau whatsapp liste les modèles reçus en prop et appelle prepare_whatsapp', () => {
  assert.match(BULK_BAR, /messageTemplates = \[\]/)
  const start = BULK_BAR.indexOf("panel === 'whatsapp'")
  assert.ok(start > 0)
  const block = BULK_BAR.slice(start, start + 700)
  assert.match(block, /messageTemplates\.map\(/)
  assert.match(block, /run\('prepare_whatsapp', \{ template_id: waTemplateId \}\)/)
  // Jamais un envoi automatique depuis ce panneau.
  assert.doesNotMatch(block, /window\.open\(/)
})

test('BulkActionBar : le menu « Plus » expose l’entrée WhatsApp en masse', () => {
  assert.match(BULK_BAR, /toggle\('whatsapp'\)/)
})

test('LeadsPage.runBulk : prepare_whatsapp range la file dans waQueue au lieu du bilan bulkMsg habituel', () => {
  const start = LEADS_PAGE.indexOf('const runBulk =')
  assert.ok(start > 0)
  const block = LEADS_PAGE.slice(start, start + 1200)
  assert.match(block, /action === 'prepare_whatsapp'/)
  assert.match(block, /setWaQueue\(data\?\.queue \?\? \[\]\)/)
})

test('LeadsPage : les modèles CRM sont chargés et transmis à BulkActionBar (choix du modèle avant envoi)', () => {
  assert.match(LEADS_PAGE, /crmApi\.getMessageTemplates\(\)/)
  assert.match(LEADS_PAGE, /messageTemplates=\{messageTemplates\}/)
})

test('LeadsPage : la file wa.me se rend en liens cliquables — jamais ouverts automatiquement', () => {
  const start = LEADS_PAGE.indexOf('waQueue &&')
  assert.ok(start > 0)
  const block = LEADS_PAGE.slice(start, start + 900)
  assert.match(block, /waQueue\.map\(/)
  assert.match(block, /href=\{q\.wa_url\}/)
  assert.match(block, /target="_blank"/)
  assert.doesNotMatch(block, /window\.open\(/)
})
