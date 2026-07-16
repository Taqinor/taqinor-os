// QX22fe — Truthful « Envoyé » on the WhatsApp path: opening the preview modal
// must NEVER mark the quote sent; only the real wa.me click-through
// (openWhatsApp) may call the mutating whatsappDevis action. Verified against
// SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/DevisListWhatsappPreview.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')
const API_SRC = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')

const handleEnvoyerBody = SRC.slice(
  SRC.indexOf('const handleEnvoyer = async'),
  SRC.indexOf('const closeWaModal ='))

const openWhatsAppBody = SRC.slice(
  SRC.indexOf('const openWhatsApp = async'),
  SRC.indexOf('const openWhatsApp = async') + 700)

test('QX22 : ventesApi expose une action de PRÉVISUALISATION dédiée (lecture seule)', () => {
  assert.match(API_SRC, /whatsappPreviewDevis: \(id, payload = \{\}\) => api\.post\(`\/ventes\/devis\/\$\{id\}\/whatsapp-preview\/`/)
})

test('QX22 : ouvrir la modale (handleEnvoyer) appelle UNIQUEMENT le preview — jamais whatsappDevis', () => {
  assert.match(handleEnvoyerBody, /ventesApi\.whatsappPreviewDevis\(d\.id\)/)
  assert.doesNotMatch(handleEnvoyerBody, /ventesApi\.whatsappDevis\(/)
})

test('QX22 : fermer sans cliquer ne déclenche aucun appel réseau (closeWaModal est un simple reset d\'état)', () => {
  const closeBody = SRC.slice(SRC.indexOf('const closeWaModal ='), SRC.indexOf('const closeWaModal =') + 120)
  assert.doesNotMatch(closeBody, /ventesApi\./)
})

test('QX22 : le clic-through sur wa.me (openWhatsApp) appelle whatsappDevis — la vraie action d\'envoi', () => {
  assert.match(openWhatsAppBody, /ventesApi\.whatsappDevis\(waTarget\.id\)/)
  assert.match(openWhatsAppBody, /window\.open\(waData\.wa_url/)
})

test('QX22 : le bouton « Ouvrir WhatsApp » reflète l\'état d\'envoi en cours', () => {
  assert.match(SRC, /const \[waSending, setWaSending\] = useState\(false\)/)
  assert.match(SRC, /<Button onClick=\{openWhatsApp\} disabled=\{!waData\?\.wa_url\} loading=\{waSending\}>/)
})
