// LW3 — Perte de données #2/#4 + fuites inter-leads : l'état SATELLITE
// (waSelected/waPreview/waLangue, noteBody/noteFile/noteError, bill*,
// devisActionMsg, cardPaste, staleGuard.staleInfo) survivait à la navigation
// ◀▶/J-K entre leads (l'effet de resynchronisation L516-530 ne remettait à
// zéro que fields/errors/customData). Risque réel : WhatsApp du lead
// PRÉCÉDENT envoyé sous le nouveau lead, note classée sur le mauvais lead,
// facture inline patchée sur le mauvais lead, « Enregistrer quand même »
// force-sauvegardant le MAUVAIS enregistrement.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormLW3StateResetOnNav.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const FORM_SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8').replace(/\r\n/g, '\n')
const GUARD_SRC = readFileSync(join(HERE, '../../hooks/useStaleGuard.js'), 'utf8').replace(/\r\n/g, '\n')

function extractSyncEffect(src) {
  const start = src.indexOf('const fieldsSyncedFor = useRef(lead?.id ?? null)')
  assert.ok(start >= 0, 'effet de resynchronisation introuvable')
  const end = src.indexOf("}, [lead?.id])", start)
  assert.ok(end >= 0, 'fin de l\'effet introuvable')
  return src.slice(start, end + "}, [lead?.id])".length)
}

test('LW3 : useStaleGuard expose un reset() qui efface staleInfo ET le forçage à usage unique', () => {
  assert.match(GUARD_SRC, /const reset = useCallback\(\(\) => \{/)
  assert.match(GUARD_SRC, /forcedRef\.current = false/)
  assert.match(GUARD_SRC, /return \{ staleInfo, checkBeforeSave, dismiss, force, reset \}/)
})

test('LW3 : l\'effet de resynchronisation lead-change réinitialise tout l\'état satellite', () => {
  const effect = extractSyncEffect(FORM_SRC)
  // WhatsApp (sélection/aperçu/langue — vers la langue préférée du NOUVEAU lead).
  assert.match(effect, /setWaSelected\(new Set\(\)\)/)
  assert.match(effect, /setWaPreview\(null\)/)
  assert.match(effect, /setWaLangue\(lead\?\.langue_preferee \|\| 'fr'\)/)
  // Note en cours de rédaction (corps + pièce jointe + erreur).
  assert.match(effect, /setNoteBody\(''\)/)
  assert.match(effect, /setNoteFile\(null\)/)
  assert.match(effect, /setNoteError\(null\)/)
  // Édition inline de la facture.
  assert.match(effect, /setBillEditing\(false\)/)
  assert.match(effect, /setBillHiver\(/)
  assert.match(effect, /setBillEte\(/)
  assert.match(effect, /setBillError\(null\)/)
  // Message d'action devis + carte de visite collée.
  assert.match(effect, /setDevisActionMsg\(null\)/)
  assert.match(effect, /setCardPaste\(null\)/)
  // Garde de fraîcheur (staleGuard) — jamais une bannière/forçage qui
  // s'applique au MAUVAIS enregistrement après navigation.
  assert.match(effect, /staleGuard\.reset\(\)/)
})
