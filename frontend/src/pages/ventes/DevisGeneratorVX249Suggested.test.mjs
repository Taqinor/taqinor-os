// VX249(b) — VX93 pré-remplit le taux TVA d'une ligne AJOUTÉE sans dire que
// c'est une SUPPOSITION. Le champ réel vit dans DevisLineRow.jsx (extraction
// mémoïsée VX188) mais le drapeau `_tvaSuggested` est posé/retiré ICI
// (emptyLine()/setLine()), DevisGenerator.jsx reste le propriétaire de
// l'état. Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/ventes/DevisGeneratorVX249Suggested.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const GEN_SRC = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const ROW_SRC = readFileSync(join(HERE, 'DevisLineRow.jsx'), 'utf8')

test('emptyLine() pose _tvaSuggested=true (une ligne ajoutée à la main reçoit un taux SUPPOSÉ)', () => {
  const start = GEN_SRC.indexOf('const emptyLine = () => ({')
  assert.ok(start >= 0)
  const body = GEN_SRC.slice(start, start + 800)
  assert.match(body, /taux_tva: lireLastTva\(\)/)
  assert.match(body, /_tvaSuggested: true/)
})

test('withKeys() (lignes auto-quote/import) ne pose PAS _tvaSuggested (taux réel calculé, jamais une supposition)', () => {
  const start = GEN_SRC.indexOf('const withKeys = (rows) => rows.map(r => ({')
  const end = GEN_SRC.indexOf('}))', start)
  const body = GEN_SRC.slice(start, end)
  assert.doesNotMatch(body, /_tvaSuggested/)
})

test('setLine() retire _tvaSuggested UNIQUEMENT quand la clé modifiée est taux_tva', () => {
  const start = GEN_SRC.indexOf('const setLine = useCallback((key, k, v) => {')
  assert.ok(start >= 0)
  const body = GEN_SRC.slice(start, start + 400)
  assert.match(body, /_tvaSuggested: false/)
  assert.match(body, /k === 'taux_tva'/)
})

test("DevisLineRow.jsx applique vx-suggested-field + un title d'apprentissage passif (cellule étroite, pas de ligne de texte séparée)", () => {
  assert.match(ROW_SRC, /l\._tvaSuggested \? ' vx-suggested-field' : ''/)
  assert.match(ROW_SRC, /title=\{l\._tvaSuggested \? 'Suggéré — modifiable' : undefined\}/)
})
