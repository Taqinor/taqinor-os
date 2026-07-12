// VX249(b) — VX93 pré-remplit le taux TVA sans dire que c'est une SUPPOSITION.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/stock/ProduitFormVX249Suggested.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'ProduitForm.jsx'), 'utf8')

test('tva : état "touché" distinct, "suggéré" = !isEdit && !touché', () => {
  assert.match(SRC, /const \[tvaTouched, setTvaTouched\] = useState\(false\)/)
  assert.match(SRC, /const tvaSuggested = !isEdit && !tvaTouched/)
})

test('choisir un taux retire le style "suggéré" (onValueChange marque touché)', () => {
  assert.match(SRC, /setField\('tva', v === '__none' \? '' : v\); setTvaTouched\(true\)/)
})

test('la classe vx-suggested-field + le micro-libellé au focus sont posés conditionnellement', () => {
  assert.match(SRC, /className=\{tvaSuggested \? 'vx-suggested-field' : undefined\}/)
  assert.match(SRC, /hint=\{tvaSuggested && tvaFocused \? 'Suggéré — modifiable' : undefined\}/)
})

test('"créer un autre" réinitialise tvaTouched → false pour le produit suivant', () => {
  assert.match(SRC, /setTvaTouched\(false\)/)
})
