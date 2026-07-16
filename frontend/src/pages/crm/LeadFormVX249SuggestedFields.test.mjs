// VX249(b) — VX93 pré-remplit owner/ville sans dire que c'est une SUPPOSITION.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormVX249SuggestedFields.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8')

test('owner/ville : état "touché" distinct, "suggéré" = !isEdit && !touché', () => {
  assert.match(SRC, /const \[ownerTouched, setOwnerTouched\] = useState\(false\)/)
  assert.match(SRC, /const \[villeTouched, setVilleTouched\] = useState\(false\)/)
  assert.match(SRC, /const ownerSuggested = !isEdit && !ownerTouched/)
  assert.match(SRC, /const villeSuggested = !isEdit && !villeTouched/)
})

test('une modification retire le style "suggéré" (touched → true au onChange/onValueChange)', () => {
  assert.match(SRC, /set\('ville', e\.target\.value\); setVilleTouched\(true\)/)
  assert.match(SRC, /set\('owner', id \?\? ''\); setOwnerTouched\(true\)/)
})

test('la classe vx-suggested-field est posée conditionnellement (jamais permanente)', () => {
  assert.match(SRC, /className=\{villeSuggested \? 'vx-suggested-field' : undefined\}/)
  assert.match(SRC, /ownerSuggested \? 'vx-suggested-field inline-block rounded-full' : undefined/)
})

test('micro-libellé "Suggéré — modifiable" affiché SEULEMENT si suggéré ET focalisé', () => {
  assert.match(SRC, /hint=\{villeSuggested && villeFocused \? 'Suggéré — modifiable' : undefined\}/)
  assert.match(SRC, /\{ownerSuggested && ownerFocused && \(/)
})

test('un changement de lead (VX224) ET "créer un autre" réinitialisent touched → false', () => {
  const occurrences = (SRC.match(/setOwnerTouched\(false\)/g) || []).length
  assert.ok(occurrences >= 2, 'ownerTouched doit repartir à false au changement de lead ET au reset créer-un-autre')
  const villeOccurrences = (SRC.match(/setVilleTouched\(false\)/g) || []).length
  assert.ok(villeOccurrences >= 2)
})
