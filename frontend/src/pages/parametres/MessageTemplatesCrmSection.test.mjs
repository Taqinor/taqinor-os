// XSAL17 — {lien_rdv} exposé dans l'aide de l'éditeur de modèles de messages
// CRM (crm.MessageTemplate). Vérification de SOURCE (JSX, pas de node_modules
// installés dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/pages/parametres/MessageTemplatesCrmSection.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'MessageTemplatesCrmSection.jsx'), 'utf8')
const LEADS_SRC = readFileSync(join(HERE, 'LeadsSection.jsx'), 'utf8')

test('{lien_rdv} figure dans la liste des placeholders documentés (XSAL17)', () => {
  assert.match(SRC, /PLACEHOLDERS = \['\{prenom\}', '\{ville\}', '\{lien\}', '\{lien_rdv\}'\]/)
  assert.match(SRC, /\{'\{lien_rdv\}'\}/)
})

test('utilise les méthodes crmApi déjà existantes (aucune nouvelle route front)', () => {
  assert.match(SRC, /crmApi\.getMessageTemplates\(\)/)
  assert.match(SRC, /crmApi\.saveMessageTemplate\(/)
  assert.match(SRC, /crmApi\.deleteMessageTemplate\(/)
})

test('suppression demande confirmation avant d\'appeler deleteMessageTemplate', () => {
  const delBody = SRC.slice(SRC.indexOf('const delTemplate ='), SRC.indexOf('return ('))
  assert.match(delBody, /window\.confirm\(/)
})

test('LeadsSection monte MessageTemplatesCrmSection', () => {
  assert.match(LEADS_SRC, /import MessageTemplatesCrmSection from '\.\/MessageTemplatesCrmSection'/)
  assert.match(LEADS_SRC, /<MessageTemplatesCrmSection \/>/)
})
