// VX249(b) — VX93 pré-remplit le mode de paiement sans dire que c'est une
// SUPPOSITION. Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/FactureListVX249Suggested.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'FactureList.jsx'), 'utf8')

test('payMode : état "touché" distinct (pas de notion isEdit ici — un paiement est toujours une création)', () => {
  assert.match(SRC, /const \[payModeTouched, setPayModeTouched\] = useState\(false\)/)
})

test('choisir un mode retire le style "suggéré" (onValueChange marque touché)', () => {
  assert.match(SRC, /setPayMode\(v\); setPayModeTouched\(true\)/)
})

test('la classe vx-suggested-field + le micro-libellé au focus sont posés conditionnellement', () => {
  assert.match(SRC, /className=\{!payModeTouched \? 'vx-suggested-field' : undefined\}/)
  assert.match(SRC, /hint=\{!payModeTouched && payModeFocused \? 'Suggéré — modifiable' : undefined\}/)
})

test('ouvrir la modale de paiement ET "créer un autre" réinitialisent payModeTouched → false', () => {
  const occurrences = (SRC.match(/setPayModeTouched\(false\)/g) || []).length
  assert.ok(occurrences >= 2, 'payModeTouched doit repartir à false à openPayModal ET au reset créer-un-autre')
})
