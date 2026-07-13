// VX237 — Collage intelligent : vérifie que `usePasteClean`/les parseurs sont
// bien POSÉS (onPaste) sur les champs listés par la tâche — vérifié contre la
// SOURCE (pas de node_modules dans ce worktree/lane, donc pas de rendu RTL
// possible), même convention que
// `pages/crm/leads/views/ListViewCallReady.test.mjs`.
//   node --test src/hooks/usePasteCleanWiring.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (rel) => readFileSync(join(HERE, rel), 'utf8')

const LEAD_FORM = read('../pages/crm/LeadForm.jsx')
const LEAD_EXPRESS = read('../pages/crm/leads/LeadExpressModal.jsx')
const CLIENT_FORM = read('../pages/crm/ClientForm.jsx')
const CLIENT_QUICK = read('../pages/ventes/ClientQuickCreateModal.jsx')
const DEVIS_GEN = read('../pages/ventes/DevisGenerator.jsx')
const FACTURE_FORM = read('../pages/ventes/FactureForm.jsx')

test('VX237 : LeadForm — Nom (carte), Téléphone, WhatsApp posent onPaste', () => {
  assert.match(LEAD_FORM, /import \{ usePasteClean, parsePastedPhone, parsePasteCard \} from '..\/..\/hooks\/usePasteClean'/)
  assert.match(LEAD_FORM, /onPaste=\{onNomPaste\}/)
  assert.match(LEAD_FORM, /onPaste=\{onTelephonePaste\}/)
  assert.match(LEAD_FORM, /onPaste=\{onWhatsappPaste\}/)
  // jamais une répartition automatique : bouton de confirmation présent.
  assert.match(LEAD_FORM, /Répartir/)
})

test('VX237 : LeadExpressModal — Nom (carte) + Téléphone posent onPaste', () => {
  assert.match(LEAD_EXPRESS, /onPaste=\{onNomPaste\}/)
  assert.match(LEAD_EXPRESS, /onPaste=\{onTelephonePaste\}/)
  assert.match(LEAD_EXPRESS, /Répartir/)
})

test('VX237 : ClientForm — Téléphone pose onPaste', () => {
  assert.match(CLIENT_FORM, /onPaste=\{onTelephonePaste\}/)
})

test('VX237 : ClientQuickCreateModal — Téléphone pose onPaste', () => {
  assert.match(CLIENT_QUICK, /onPaste=\{onTelephonePaste\}/)
})

test('VX237 : DevisGenerator — Facture Hiver/Été/réelle posent onPaste (montant)', () => {
  assert.match(DEVIS_GEN, /onPaste=\{onHiverPaste\}/)
  assert.match(DEVIS_GEN, /onPaste=\{onEtePaste\}/)
  assert.match(DEVIS_GEN, /onPaste=\{onRealBillPaste\}/)
})

test('VX237 : FactureForm — Prix HT de ligne pose onPaste (montant)', () => {
  const idx = FACTURE_FORM.indexOf('data-label="Prix HT (DH)"')
  assert.ok(idx > 0)
  const block = FACTURE_FORM.slice(idx, idx + 700)
  assert.match(block, /onPaste=\{e => \{/)
  assert.match(block, /parsePastedAmount/)
})
