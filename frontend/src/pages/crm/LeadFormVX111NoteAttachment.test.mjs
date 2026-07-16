// VX111 — [PRÉMISSE CORRIGÉE] Lier une pièce jointe à une NOTE du chatter
// lead + la remonter dans le flux mobile. Le vrai manque, étroit : (a) une
// pièce jointe n'était pas rattachable à une note (composer texte pur), (b)
// AttachmentsPanel reste atteignable en mobile (déjà vrai via le rail de
// navigation — vérifié ici, pas ajouté). Verified against SOURCE (no
// node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormVX111NoteAttachment.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const LEADFORM_SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')
const CHATTER_SRC = readFileSync(join(HERE, '..', '..', 'components', 'ChatterTimeline.jsx'), 'utf8')

test('VX111 : le composer Historique porte un bouton trombone (attacher à la note)', () => {
  assert.match(LEADFORM_SRC, /Attacher une pièce jointe à la note/)
  assert.match(LEADFORM_SRC, /noteFileInputRef\.current\?\.click\(\)/)
})

test('VX111 : postNote poste en multipart dès qu\'un fichier est attaché', () => {
  assert.match(LEADFORM_SRC, /if \(noteFile\) \{/)
  assert.match(LEADFORM_SRC, /form\.append\('file', noteFile\)/)
  assert.match(LEADFORM_SRC, /'Content-Type': 'multipart\/form-data'/)
})

test('VX111 : sans fichier, postNote reste un simple POST JSON (non-régression)', () => {
  assert.match(LEADFORM_SRC, /r = await api\.post\(`\/crm\/leads\/\$\{lead\.id\}\/noter\/`, \{ body \}\)/)
})

test('VX111 : la section « Pièces jointes » (AttachmentsPanel) reste inconditionnellement dans le rail (mobile atteignable)', () => {
  assert.match(LEADFORM_SRC, /\['pieces', 'Pièces jointes'\]/)
  assert.match(LEADFORM_SRC, /<Sec id="pieces" title="Pièces jointes">/)
  assert.match(LEADFORM_SRC, /<AttachmentsPanel model="crm\.lead" id=\{lead\.id\} \/>/)
})

test('VX111 : ChatterTimeline rend la pièce jointe d\'une note via href={a.attachment_url} (proxy Django serveur, jamais un lien MinIO construit côté client)', () => {
  assert.match(CHATTER_SRC, /a\.attachment_url/)
  assert.match(CHATTER_SRC, /a\.attachment_filename/)
  assert.match(CHATTER_SRC, /href=\{a\.attachment_url\}/)
})
