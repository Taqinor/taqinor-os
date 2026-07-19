// LB16 — tagColor tokenisé : les 10 paires de couleurs de pastilles de tag
// vivent dans design/tokens.css (--tag-N-bg/--tag-N-fg, clair+sombre AA) ;
// `tagColor()` garde sa signature ({bg, color}) et renvoie des `var(--tag-N-…)`,
// plus AUCUN hex. Hash déterministe conservé (mêmes buckets qu'avant). Module
// pur → import réel en node --test.
//   node --test src/features/crm/stagesTagColor.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { tagColor } from './stages.js'

const HERE = dirname(fileURLToPath(import.meta.url))

test('LB16 : tagColor renvoie des tokens var(--tag-N-…), jamais de hex', () => {
  for (const tag of ['solaire', 'chaud', 'B2B', 'reda', 'meriem', 'urgent', 'VIP', 'x', '', 'agricole']) {
    const { bg, color } = tagColor(tag)
    assert.match(bg, /^var\(--tag-([1-9]|10)-bg\)$/)
    assert.match(color, /^var\(--tag-([1-9]|10)-fg\)$/)
    assert.doesNotMatch(bg, /#[0-9a-fA-F]/)
    assert.doesNotMatch(color, /#[0-9a-fA-F]/)
  }
})

test('LB16 : le bucket bg et fg d\'un tag partagent le même index N', () => {
  for (const tag of ['solaire', 'B2B', 'urgent', 'meriem']) {
    const { bg, color } = tagColor(tag)
    const nBg = bg.match(/--tag-(\d+)-bg/)[1]
    const nFg = color.match(/--tag-(\d+)-fg/)[1]
    assert.equal(nBg, nFg)
  }
})

test('LB16 : tagColor est déterministe (même tag → même couleur)', () => {
  assert.deepEqual(tagColor('solaire'), tagColor('solaire'))
  assert.deepEqual(tagColor('B2B'), tagColor('B2B'))
})

test('LB16 : la source stages.js ne contient plus les anciens hex de palette', () => {
  const src = readFileSync(join(HERE, 'stages.js'), 'utf8')
  assert.doesNotMatch(src, /TAG_PALETTE/)
  assert.doesNotMatch(src, /TAG_TEXT/)
  assert.doesNotMatch(src, /#[0-9a-fA-F]{6}/)
})
