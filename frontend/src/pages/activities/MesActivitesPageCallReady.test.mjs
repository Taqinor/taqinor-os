// QX25 — « Mes activités » is the literal daily call list but had no
// tel:/wa.me on any row. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/activities/MesActivitesPageCallReady.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'MesActivitesPage.jsx'), 'utf8')

test('QX25 : telHref/waHref dérivés depuis target_phone (serializer)', () => {
  assert.match(SRC, /const telHref = /)
  assert.match(SRC, /const waHref = /)
  assert.match(SRC, /telHref\(a\.target_phone\)/)
  assert.match(SRC, /waHref\(a\.target_phone\)/)
})

test('QX25 : une colonne « contact » rend les icônes tel/wa dans le tableau', () => {
  assert.match(SRC, /key: 'contact'/)
  assert.match(SRC, /href=\{tel\}/)
  assert.match(SRC, /href=\{wa\}/)
})

test('QX25 : ne casse rien quand aucun numéro n\'est disponible (colonne vide, pas d\'erreur)', () => {
  const start = SRC.indexOf("key: 'contact'")
  const block = SRC.slice(start, start + 900)
  assert.match(block, /if \(!tel && !wa\) return null/)
})
