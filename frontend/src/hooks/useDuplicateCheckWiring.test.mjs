// VX239 — Doublons : prévenir à la création CLIENT (part a). Vérifié contre
// la SOURCE (pas de node_modules dans ce worktree/lane, donc pas de rendu RTL
// possible), même convention que
// `pages/crm/leads/views/ListViewCallReady.test.mjs`.
//   node --test src/hooks/useDuplicateCheckWiring.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

// LW37 — le câblage VX239 a migré de LeadForm.jsx (fondue en adaptateur en LW13)
// vers SectionContact du cockpit ; LeadExpressModal/ClientForm/ClientQuick sont
// inchangés.
const SECTION_CONTACT = read('../features/crm/workspace/sections/SectionContact.jsx')
const LEAD_EXPRESS = read('../pages/crm/leads/LeadExpressModal.jsx')
const CLIENT_FORM = read('../pages/crm/ClientForm.jsx')
const CLIENT_QUICK = read('../pages/ventes/ClientQuickCreateModal.jsx')

test('VX239 : SectionContact utilise le hook extrait useDuplicateCheck (exclut son propre lead en édition)', () => {
  assert.match(SECTION_CONTACT, /import \{ useDuplicateCheck \} from '\.\.\/\.\.\/\.\.\/\.\.\/hooks\/useDuplicateCheck'/)
  assert.match(SECTION_CONTACT, /const dupMatches = useDuplicateCheck\(v\('telephone'\), v\('email'\), \{/)
  assert.match(SECTION_CONTACT, /exclude: mode === 'edit' \? leadId : undefined/)
})

test('VX239 : SectionContact/LeadExpressModal posent <PhoneHint> (extrait de ClientForm)', () => {
  assert.match(SECTION_CONTACT, /import PhoneHint from '\.\.\/\.\.\/\.\.\/\.\.\/components\/PhoneHint'/)
  assert.match(SECTION_CONTACT, /<PhoneHint value=\{v\('telephone'\)\} testId="lf-tel-hint" \/>/)
  assert.match(LEAD_EXPRESS, /import PhoneHint from '..\/..\/..\/components\/PhoneHint'/)
  assert.match(LEAD_EXPRESS, /<PhoneHint value=\{telephone\} testId="lem-tel-hint" \/>/)
})

test('VX239 : ClientForm pose useDuplicateCheck ET <PhoneHint> (jusqu\'ici limité à l\'autocomplete NOM)', () => {
  assert.match(CLIENT_FORM, /import \{ useDuplicateCheck \} from '..\/..\/hooks\/useDuplicateCheck'/)
  assert.match(CLIENT_FORM, /import PhoneHint from '..\/..\/components\/PhoneHint'/)
  assert.match(CLIENT_FORM, /const dupMatches = useDuplicateCheck\(fields\.telephone, fields\.email\)/)
  assert.match(CLIENT_FORM, /<PhoneHint value=\{fields\.telephone\} testId="cf-tel-hint" \/>/)
  assert.match(CLIENT_FORM, /dupMatches\.length > 0/)
})

test('VX239 : ClientQuickCreateModal pose useDuplicateCheck ET <PhoneHint>', () => {
  assert.match(CLIENT_QUICK, /import \{ useDuplicateCheck \} from '..\/..\/hooks\/useDuplicateCheck'/)
  assert.match(CLIENT_QUICK, /import PhoneHint from '..\/..\/components\/PhoneHint'/)
  assert.match(CLIENT_QUICK, /const dupMatches = useDuplicateCheck\(telephone, email\)/)
  assert.match(CLIENT_QUICK, /<PhoneHint value=\{telephone\} testId="cqc-tel-hint" \/>/)
})
