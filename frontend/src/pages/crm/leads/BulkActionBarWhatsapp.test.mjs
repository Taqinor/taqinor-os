// WIR229/FG33 — panneau « WhatsApp en masse » de BulkActionBar : choix d'un
// modèle (ou texte libre) puis `prepare_whatsapp` (file de liens wa.me,
// AUCUN envoi automatique). Vérification de SOURCE (JSX, pas de node_modules
// installés dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/pages/crm/leads/BulkActionBarWhatsapp.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'BulkActionBar.jsx'), 'utf8')
const LEADS_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')

test('le menu « Plus » propose WhatsApp en masse', () => {
  assert.match(SRC, /toggle\('whatsapp'\)/)
  assert.match(SRC, /WhatsApp en masse/)
})

test('le panneau whatsapp liste messageTemplates et appelle prepare_whatsapp', () => {
  const panelBody = SRC.slice(
    SRC.indexOf("panel === 'whatsapp'"),
    SRC.indexOf("panel === 'perdu'"),
  )
  assert.match(panelBody, /messageTemplates\.map/)
  assert.match(panelBody, /run\('prepare_whatsapp', \{/)
  assert.match(panelBody, /template_id: waTemplateId \|\| undefined/)
  assert.match(panelBody, /body: waTemplateId \? undefined : waBody\.trim\(\)/)
  // Aucun envoi auto — le texte prévient explicitement.
  assert.match(panelBody, /aucun envoi automatique/i)
})

test('messageTemplates est un prop accepté par BulkActionBar (défaut [])', () => {
  assert.match(SRC, /messageTemplates = \[\]/)
})

test('LeadsPage traite prepare_whatsapp à part (jamais bulkResultMessage) et affiche la file un par un', () => {
  const runBulkBody = LEADS_SRC.slice(
    LEADS_SRC.indexOf('const runBulk = async'),
    LEADS_SRC.indexOf('const exportSelection'),
  )
  assert.match(runBulkBody, /if \(action === 'prepare_whatsapp'\)/)
  assert.match(runBulkBody, /setWaQueue\(data\.queue/)

  assert.match(LEADS_SRC, /data-testid="wa-bulk-queue"/)
  assert.match(LEADS_SRC, /target="_blank" rel="noopener noreferrer"/)
  assert.match(LEADS_SRC, /messageTemplates=\{messageTemplates\}/)
})
